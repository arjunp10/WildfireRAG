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
from spread.compute import get_spread_geojson

load_dotenv()

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
CHROMA_DIR = os.environ.get("CHROMA_DIR", "rag/chroma_db")
DB_PATH = os.environ.get("DB_PATH", "firerag.db")

_SYSTEM_PROMPT = """\
You are a wildfire analysis assistant for FireRAG. You have access to the following live datasets:
- Confirmed wildfire perimeters 2000–2026 (named fires, acreage, state, cause)
- Real-time satellite fire detections (FIRMS/VIIRS, updated daily)
- Current NWS weather conditions per 1° grid cell (temperature, humidity, wind, Fosberg FWI)
- 7-day NWS fire weather forecast per grid cell (peak FWI over next 7 days)
- Fire risk index per grid cell (60% peak FWI + 40% 26-year ignition history, scored 0–100%)
- Active fire spread predictions (24h projected spread ellipses based on wind direction and FWI)
- Recent wildfire news articles

Relevant data retrieved for this question:
{context}

Instructions:
- Answer concisely, ideally under 200 words.
- Lead with dataset facts; supplement with general knowledge only for well-known fires.
- When referencing weather or risk data, cite the specific values (e.g. FWI, temperature, risk score).
- Never apologise for using accurate general knowledge. Never say a fire "isn't in the dataset" \
  if it is a well-known event — it may be stored under a slightly different name.
- If asked about current conditions, spread zones, or risk, use the [WEATHER], [RISK], and \
  [SPREAD] context sections provided."""

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



@app.get("/spread/current")
def spread_current():
    """GeoJSON FeatureCollection of 24-hour fire spread ellipses for active fire clusters."""
    return get_spread_geojson(DB_PATH)


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


def _cell_polygon(lat: float, lon: float, half: float = 0.5) -> dict:
    """Return a GeoJSON Polygon for a 1°×1° grid cell centred at (lat, lon)."""
    return {
        "type": "Polygon",
        "coordinates": [[
            [lon - half, lat - half],
            [lon + half, lat - half],
            [lon + half, lat + half],
            [lon - half, lat + half],
            [lon - half, lat - half],
        ]],
    }


@app.get("/risk/grid")
def risk_grid_endpoint():
    """
    GeoJSON FeatureCollection of 7-day fire risk predictions.
    Each feature is a 1°×1° polygon coloured by risk_score (0-1).
    risk_score = 0.6 × fwi_score (7-day peak FWI) + 0.4 × hist_score (26yr ignition history).
    """
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
            "geometry": _cell_polygon(row["lat"], row["lon"]),
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


# Rough bounding boxes (min_lat, max_lat, min_lon, max_lon) for US states
_STATE_BBOX: dict[str, tuple[float, float, float, float]] = {
    "AK": (54.0, 71.5, -168.0, -130.0), "AL": (30.1, 35.0, -88.5, -84.9),
    "AR": (33.0, 36.5, -94.6, -89.6),   "AZ": (31.3, 37.0, -114.8, -109.0),
    "CA": (32.5, 42.0, -124.5, -114.1), "CO": (36.9, 41.0, -109.1, -102.0),
    "CT": (41.0, 42.1, -73.7, -71.8),   "DE": (38.4, 39.8, -75.8, -75.0),
    "FL": (24.4, 31.0, -87.6, -80.0),   "GA": (30.4, 35.0, -85.6, -80.8),
    "HI": (18.9, 22.2, -160.2, -154.8), "IA": (40.4, 43.5, -96.6, -90.1),
    "ID": (41.9, 49.0, -117.2, -111.0), "IL": (36.9, 42.5, -91.5, -87.5),
    "IN": (37.8, 41.8, -88.1, -84.8),   "KS": (36.9, 40.0, -102.1, -94.6),
    "KY": (36.5, 39.1, -89.6, -81.9),   "LA": (28.9, 33.0, -94.0, -89.0),
    "MA": (41.2, 42.9, -73.5, -69.9),   "MD": (37.9, 39.7, -79.5, -75.0),
    "ME": (43.1, 47.5, -71.1, -66.9),   "MI": (41.7, 48.3, -90.4, -82.4),
    "MN": (43.5, 49.4, -97.2, -89.5),   "MO": (35.9, 40.6, -95.8, -89.1),
    "MS": (30.2, 35.0, -91.7, -88.1),   "MT": (44.4, 49.0, -116.1, -104.0),
    "NC": (33.8, 36.6, -84.3, -75.5),   "ND": (45.9, 49.0, -104.1, -96.6),
    "NE": (40.0, 43.0, -104.1, -95.3),  "NH": (42.7, 45.3, -72.6, -70.7),
    "NJ": (38.9, 41.4, -75.6, -73.9),   "NM": (31.3, 37.0, -109.1, -103.0),
    "NV": (35.0, 42.0, -120.0, -114.0), "NY": (40.5, 45.0, -79.8, -71.9),
    "OH": (38.4, 42.0, -84.8, -80.5),   "OK": (33.6, 37.0, -103.0, -94.4),
    "OR": (41.9, 46.3, -124.6, -116.5), "PA": (39.7, 42.3, -80.5, -74.7),
    "RI": (41.1, 42.0, -71.9, -71.1),   "SC": (32.0, 35.2, -83.4, -78.5),
    "SD": (42.5, 45.9, -104.1, -96.4),  "TN": (34.9, 36.7, -90.3, -81.6),
    "TX": (25.8, 36.5, -106.6, -93.5),  "UT": (37.0, 42.0, -114.1, -109.0),
    "VA": (36.5, 39.5, -83.7, -75.2),   "VT": (42.7, 45.0, -73.4, -71.5),
    "WA": (45.5, 49.0, -124.8, -116.9), "WI": (42.5, 47.1, -92.9, -86.2),
    "WV": (37.2, 40.6, -82.6, -77.7),   "WY": (41.0, 45.0, -111.1, -104.1),
}


def _bbox_conditions(states: list[str]) -> tuple[str, list]:
    """Build SQL WHERE fragment for lat/lon bounding box of given states."""
    if not states:
        return "", []
    boxes = [_STATE_BBOX[s] for s in states if s in _STATE_BBOX]
    if not boxes:
        return "", []
    clauses, params = [], []
    for min_lat, max_lat, min_lon, max_lon in boxes:
        clauses.append("(lat BETWEEN ? AND ? AND lon BETWEEN ? AND ?)")
        params.extend([min_lat, max_lat, min_lon, max_lon])
    return f"AND ({' OR '.join(clauses)})", params


def _get_weather_context(states: list[str], limit: int = 6) -> list[str]:
    """Top weather grid cells by forecast FWI for the queried region."""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        bbox_sql, bbox_params = _bbox_conditions(states)
        rows = conn.execute(f"""
            SELECT lat, lon, temp_f, humidity_pct, wind_speed_mph, wind_dir_deg,
                   fosberg_index, COALESCE(forecast_fwi, fosberg_index) AS peak_fwi, fetched_at
            FROM weather_grid
            WHERE fetched_at IS NOT NULL {bbox_sql}
            ORDER BY peak_fwi DESC
            LIMIT {limit}
        """, bbox_params).fetchall()
        conn.close()
    except sqlite3.OperationalError:
        return []

    docs = []
    compass = ["N","NNE","NE","ENE","E","ESE","SE","SSE","S","SSW","SW","WSW","W","WNW","NW","NNW"]
    for r in rows:
        wind_dir = compass[round((r["wind_dir_deg"] or 0) / 22.5) % 16] if r["wind_dir_deg"] else "unknown"
        docs.append(
            f"Weather at {r['lat']:.1f}°N, {r['lon']:.1f}°W: "
            f"Temp {r['temp_f']:.0f}°F, humidity {r['humidity_pct']:.0f}%, "
            f"wind {r['wind_speed_mph']:.0f} mph {wind_dir}, "
            f"current FWI {r['fosberg_index']:.1f}, 7-day peak FWI {r['peak_fwi']:.1f}. "
            f"(Updated {r['fetched_at'][:10] if r['fetched_at'] else 'unknown'})"
        )
    return docs


def _get_risk_context(states: list[str], limit: int = 6) -> list[str]:
    """Top risk index cells for the current month in the queried region."""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        bbox_sql, bbox_params = _bbox_conditions(states)
        rows = conn.execute(f"""
            SELECT lat, lon, fwi_score, hist_score, risk_score, month
            FROM risk_grid
            WHERE 1=1 {bbox_sql}
            ORDER BY risk_score DESC
            LIMIT {limit}
        """, bbox_params).fetchall()
        conn.close()
    except sqlite3.OperationalError:
        return []

    docs = []
    for r in rows:
        docs.append(
            f"Risk index at {r['lat']:.1f}°N, {r['lon']:.1f}°W: "
            f"{r['risk_score']*100:.0f}% overall risk "
            f"(fire weather {r['fwi_score']*100:.0f}%, historical frequency {r['hist_score']*100:.0f}%) "
            f"for month {r['month']}."
        )
    return docs


def _get_spread_context(states: list[str], limit: int = 5) -> list[str]:
    """Active fire spread predictions for the queried region."""
    try:
        geojson = get_spread_geojson(DB_PATH)
    except Exception:
        return []

    compass = ["N","NNE","NE","ENE","E","ESE","SE","SSE","S","SSW","SW","WSW","W","WNW","NW","NNW"]
    docs = []
    for feat in geojson.get("features", [])[:limit]:
        p = feat["properties"]
        # Filter by state bbox if requested
        if states:
            boxes = [_STATE_BBOX[s] for s in states if s in _STATE_BBOX]
            in_region = any(
                b[0] <= p["center_lat"] <= b[1] and b[2] <= p["center_lon"] <= b[3]
                for b in boxes
            )
            if not in_region:
                continue
        wind_dir = compass[round((p["wind_dir"] or 0) / 22.5) % 16]
        docs.append(
            f"Active fire cluster at {p['center_lat']:.2f}°N, {p['center_lon']:.2f}°W: "
            f"{p['detections']} satellite detections, avg brightness {p['brightness']:.0f} K. "
            f"Wind {p['wind_mph']:.0f} mph from {wind_dir}, FWI {p['fwi']:.1f}. "
            f"24-hour spread projection: {p['spread_km']:.0f} km downwind."
        )
    return docs


def _get_active_fires_context(states: list[str]) -> list[str]:
    """Summary of recent FIRMS detections: total count, top clusters, date range."""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        bbox_sql, bbox_params = _bbox_conditions(states)
        summary = conn.execute(f"""
            SELECT COUNT(*) AS total,
                   SUM(CASE WHEN confidence='h' THEN 1 ELSE 0 END) AS high_conf,
                   MIN(acq_date) AS earliest, MAX(acq_date) AS latest
            FROM fires_realtime
            WHERE 1=1 {bbox_sql}
        """, bbox_params).fetchone()

        # Top 5 hottest detections
        hot = conn.execute(f"""
            SELECT latitude, longitude, brightness, acq_date, confidence
            FROM fires_realtime
            WHERE 1=1 {bbox_sql}
            ORDER BY brightness DESC LIMIT 5
        """, bbox_params).fetchall()
        conn.close()
    except sqlite3.OperationalError:
        return []

    if not summary or summary["total"] == 0:
        return []

    docs = [
        f"Active fire detections: {summary['total']} total "
        f"({summary['high_conf']} high-confidence), "
        f"dates {summary['earliest']} to {summary['latest']}."
    ]
    for r in hot:
        docs.append(
            f"Hot detection at {r['latitude']:.2f}°N, {r['longitude']:.2f}°W: "
            f"brightness {r['brightness']:.0f} K, confidence {r['confidence'].upper()}, "
            f"detected {r['acq_date']}."
        )
    return docs


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

    # Direct SQL: largest confirmed fires for region/year (hybrid retrieval)
    top_fire_docs = _get_top_fires(states, year, limit=8)
    semantic_texts = set(perimeter_docs)
    unique_top = [d for d in top_fire_docs if d not in semantic_texts]

    # Live data: weather, risk index, spread zones, active fire summary
    weather_docs   = _get_weather_context(states)
    risk_docs      = _get_risk_context(states)
    spread_docs    = _get_spread_context(states)
    active_summary = _get_active_fires_context(states)

    context_parts  = [f"[HISTORICAL] {d}" for d in historical_docs]
    context_parts += [f"[ACTIVE FIRES] {d}" for d in active_summary]
    context_parts += [f"[ACTIVE FIRES] {d}" for d in firms_docs]
    context_parts += [f"[CONFIRMED FIRES] {d}" for d in perimeter_docs]
    context_parts += [f"[CONFIRMED FIRES] {d}" for d in unique_top]
    context_parts += [f"[WEATHER] {d}" for d in weather_docs]
    context_parts += [f"[RISK] {d}" for d in risk_docs]
    context_parts += [f"[SPREAD] {d}" for d in spread_docs]
    context_parts += [f"[NEWS] {d}" for d in news_docs]
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
