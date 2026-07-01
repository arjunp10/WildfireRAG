import os
import sqlite3

import anthropic
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from rag.retriever import query_firms, query_news, query_similar

load_dotenv()

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
CHROMA_DIR = os.environ.get("CHROMA_DIR", "rag/chroma_db")
DB_PATH = os.environ.get("DB_PATH", "firerag.db")

_SYSTEM_PROMPT = """\
You are a wildfire analysis assistant for WildfireRAG. You have access to historical fire data, \
real-time active fire detections, and recent news for the United States. \
Answer questions about fire risk, patterns, history, and current conditions concisely and clearly.

Relevant data (historical records, active fire detections, and recent news):
{context}

Base your answer on this data. If the data doesn't cover the user's question, say so briefly. \
Keep answers under 150 words."""

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


@app.get("/health")
def health():
    return {"status": "ok"}


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
                SUM(CASE WHEN confidence = 'high' THEN 1 ELSE 0 END) as high_confidence
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

    historical_docs = query_similar(req.question, CHROMA_DIR, k=3)
    try:
        news_docs = query_news(req.question, CHROMA_DIR, k=2)
    except Exception:
        news_docs = []
    try:
        firms_docs = query_firms(req.question, CHROMA_DIR, k=3)
    except Exception:
        firms_docs = []

    context_parts = [f"[HISTORICAL] {doc}" for doc in historical_docs]
    context_parts += [f"[ACTIVE FIRES] {doc}" for doc in firms_docs]
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
