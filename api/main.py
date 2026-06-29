import os

import anthropic
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from rag.retriever import query_similar

load_dotenv()

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
CHROMA_DIR = os.environ.get("CHROMA_DIR", "rag/chroma_db")

_SYSTEM_PROMPT = """\
You are a wildfire analysis assistant for WildfireRAG. You have access to historical fire data \
for the United States. Answer questions about fire risk, patterns, and history concisely and clearly.

Relevant historical fire data (retrieved by similarity):
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
    question: str
    history: list[Message] = []


class ChatResponse(BaseModel):
    answer: str


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    if not ANTHROPIC_API_KEY:
        raise HTTPException(status_code=500, detail="ANTHROPIC_API_KEY not set. Add it to .env.")
    if not os.path.exists(CHROMA_DIR):
        raise HTTPException(
            status_code=500,
            detail=f"ChromaDB not found at '{CHROMA_DIR}'. Run: python3 rag/build_index.py",
        )

    context_docs = query_similar(req.question, CHROMA_DIR, k=5)
    context = "\n".join(f"- {doc}" for doc in context_docs)
    system_prompt = _SYSTEM_PROMPT.format(context=context)

    history = req.history[-6:]
    messages = [{"role": m.role, "content": m.content} for m in history]
    messages.append({"role": "user", "content": req.question})

    try:
        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=512,
            system=system_prompt,
            messages=messages,
        )
        return ChatResponse(answer=response.content[0].text)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Claude API error: {e}")
