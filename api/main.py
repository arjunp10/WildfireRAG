import os
import re
import sqlite3

import anthropic
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from rag.geo import build_where, extract_geo
from rag.retriever import query_firms, query_news, query_perimeters, query_similar

load_dotenv()

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
CHROMA_DIR = os.environ.get("CHROMA_DIR", "rag/chroma_db")
DB_PATH = os.environ.get("DB_PATH", "firerag.db")

_SYSTEM_PROMPT = """\
You are a wildfire analysis assistant for WildfireRAG. You have access to confirmed wildfire \
perimeter records (2000-2026, named fires with acreage), real-time active fire detections, \
historical fire statistics, and recent news for the United States.

Relevant data from the dataset:
{context}

Instructions:
- Answer concisely, under 150 words.
- Prioritize information from the dataset above. You may supplement with your own knowledge \
  for well-known fires (e.g. large named fires that are widely documented) but clearly distinguish \
  dataset facts from general knowledge.
- Never say a fire "isn't in my dataset" if it appears on the map or is a well-known event — \
  the dataset may have it under a slightly different name or with a missing year field.
- Do not apologize for using accurate general knowledge to fill gaps."""

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


class Message(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    question: str = Field(..., min_length=1)
    history: list[Message] = []


class ChatResponse(BaseModel):
    answer: str


class ArticleOut(BaseModel):
    title: str
    description: str | None
    url: str
    source: str | None
    published_at: str | None


def _get_top_fires(states: list[str], year: int | None, limit: int = 8) -> list[str]:
    """Direct SQL: largest confirmed fires for the detected state(s)/year. Bypasses semantic search."""
    if not states and year is None:
        return []
    try:
        conn = sqlite3.connect(DB_PATH)
        conditions = ["acres >= 100"]
        params: list = []
        if states:
            placeholders = ",".join("?" * len(states))
            conditions.append(f"state IN ({placeholders})")
            params.extend(states)
        if year is not None:
            conditions.append("COALESCE(fire_year, CAST(substr(discovery_date,1,4) AS INTEGER)) = ?")
            params.append(year)
        rows = conn.execute(
            f"""
            SELECT fire_name,
                   COALESCE(fire_year, CAST(substr(discovery_date,1,4) AS INTEGER)) AS yr,
                   state, acres, agency, discovery_date, cause
            FROM fire_perimeters
            WHERE {" AND ".join(conditions)}
            ORDER BY acres DESC
            LIMIT {limit}
            """,
            params,
        ).fetchall()
        conn.close()
    except sqlite3.OperationalError:
        return []

    docs = []
    for name, yr, state, acres, agency, date, cause in rows:
        parts = [f"[CONFIRMED WILDFIRE] {name or 'Unknown'} ({yr}){', ' + state if state else ''}."]
        parts.append(f"{acres:,.0f} acres burned.")
        if agency:
            parts.append(f"Agency: {agency}.")
        if date:
            parts.append(f"Discovered: {date}.")
        if cause:
            parts.append(f"Cause: {cause}.")
        docs.append(" ".join(parts))
    return docs


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/weather/grid")
def weather_grid(
    min_lat: float | None = None,
    max_lat: float | None = None,
    min_lon: float | None = None,
    max_lon: float | None = None,
):
    """
    GeoJSON FeatureCollection of weather grid points with fire-weather properties.
    Optional bbox params (min_lat, max_lat, min_lon, max_lon) to subset the grid.
    Each feature has properties: temp_f, humidity_pct, wind_speed_mph, wind_dir_deg,
    fosberg_index, fetched_at.
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row

        conditions = ["fetched_at IS NOT NULL"]
        params: list = []

        if min_lat is not None:
            conditions.append("lat >= ?"); params.append(min_lat)
        if max_lat is not None:
            conditions.append("lat <= ?"); params.append(max_lat)
        if min_lon is not None:
            conditions.append("lon >= ?"); params.append(min_lon)
        if max_lon is not None:
            conditions.append("lon <= ?"); params.append(max_lon)

        rows = conn.execute(
            f"""
            SELECT lat, lon, temp_f, humidity_pct, wind_speed_mph,
                   wind_dir_deg, fosberg_index, fetched_at
            FROM weather_grid
            WHERE {" AND ".join(conditions)}
            ORDER BY lat, lon
            """,
            params,
        ).fetchall()
        conn.close()
    except sqlite3.OperationalError:
        rows = []

    features = [
        {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [row["lon"], row["lat"]]},
            "properties": {
                "temp_f":         row["temp_f"],
                "humidity_pct":   row["humidity_pct"],
                "wind_speed_mph": row["wind_speed_mph"],
                "wind_dir_deg":   row["wind_dir_deg"],
                "fosberg_index":  row["fosberg_index"],
                "fetched_at":     row["fetched_at"],
            },
        }
        for row in rows
    ]

    return {"type": "FeatureCollection", "features": features}


@app.get("/risk/grid")
def risk_grid_endpoint():
    """GeoJSON FeatureCollection of fire risk predictions per 1°×1° cell."""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        rows = conn.execute("""
            SELECT lat, lon, fwi_score, hist_score, risk_score, month, computed_at
            FROM risk_grid
            ORDER BY lat, lon
        """).fetchall()
        conn.close()
    except sqlite3.OperationalError:
        rows = []

    features = [
        {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [row["lon"], row["lat"]]},
            "properties": {
                "fwi_score":   row["fwi_score"],
                "hist_score":  row["hist_score"],
                "risk_score":  row["risk_score"],
                "month":       row["month"],
                "computed_at": row["computed_at"],
            },
        }
        for row in rows
    ]
    return {"type": "FeatureCollection", "features": features}


@app.get("/news", response_model=list[ArticleOut])
def get_news():
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT title, description, url, source, published_at FROM articles ORDER BY published_at DESC LIMIT 15"
        ).fetchall()
        conn.close()
        return [dict(row) for row in rows]
    except sqlite3.OperationalError:
        return []


@app.get("/stats")
def get_stats():
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        row = conn.execute("""
            SELECT
                COUNT(*) as total_fires,
                MAX(acq_date) as last_date,
                SUM(CASE WHEN confidence = 'h' THEN 1 ELSE 0 END) as high_confidence
            FROM fires_realtime
        """).fetchone()
        conn.close()
        return {
            "total_fires": row["total_fires"] if row else 0,
            "last_date": row["last_date"] if row else None,
            "high_confidence": row["high_confidence"] if row else 0,
        }
    except sqlite3.OperationalError:
        return {"total_fires": 0, "last_date": None, "high_confidence": 0}


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    if not ANTHROPIC_API_KEY:
        raise HTTPException(status_code=500, detail="ANTHROPIC_API_KEY not set. Add it to .env.")
    if not os.path.exists(CHROMA_DIR):
        raise HTTPException(
            status_code=500,
            detail=f"ChromaDB not found at '{CHROMA_DIR}'. Run: python3 -m rag.build_index",
        )

    states, year = extract_geo(req.question)
    geo_where = build_where(states, year)
    # For active fire queries, year filtering doesn't apply (firms is real-time)
    state_only_where = build_where(states, None)

    historical_docs = query_similar(req.question, CHROMA_DIR, k=5, where=geo_where)
    try:
        news_docs = query_news(req.question, CHROMA_DIR, k=2)
    except Exception:
        news_docs = []
    try:
        firms_docs = query_firms(req.question, CHROMA_DIR, k=3, where=state_only_where)
    except Exception:
        firms_docs = []
    try:
        perimeter_docs = query_perimeters(req.question, CHROMA_DIR, k=5, where=geo_where)
    except Exception:
        perimeter_docs = []

    # Direct SQL lookup: top fires by acreage for the detected region/year.
    # This ensures large named fires (e.g. Biscuit Fire) are always surfaced
    # even when semantic similarity doesn't rank them first.
    top_fire_docs = _get_top_fires(states, year, limit=8)

    # Deduplicate: drop SQL results that are already covered by semantic results
    semantic_texts = set(perimeter_docs)
    unique_top = [d for d in top_fire_docs if d not in semantic_texts]

    context_parts = [f"[HISTORICAL] {doc}" for doc in historical_docs]
    context_parts += [f"[ACTIVE FIRES] {doc}" for doc in firms_docs]
    context_parts += [f"[CONFIRMED FIRES] {doc}" for doc in perimeter_docs]
    context_parts += [f"[CONFIRMED FIRES] {doc}" for doc in unique_top]
    context_parts += [f"[NEWS] {doc}" for doc in news_docs]
    context = "\n".join(f"- {part}" for part in context_parts)
    system_prompt = _SYSTEM_PROMPT.format(context=context)

    history = req.history[-6:]
    msgs = [{"role": m.role, "content": m.content} for m in history]
    while msgs and msgs[0]["role"] != "user":
        msgs.pop(0)
    msgs.append({"role": "user", "content": req.question})

    try:
        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=512,
            system=system_prompt,
            messages=msgs,
        )
        return ChatResponse(answer=response.content[0].text)
    except anthropic.APIError as e:
        raise HTTPException(status_code=500, detail=f"Claude API error: {e}")
