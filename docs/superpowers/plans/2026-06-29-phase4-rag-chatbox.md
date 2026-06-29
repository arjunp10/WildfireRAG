# Phase 4 RAG Chatbox Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a conversational RAG chatbox to the WildfireRAG globe that answers wildfire pattern questions by retrieving historical fire summaries from ChromaDB and synthesizing answers via Claude.

**Architecture:** `rag/build_index.py` aggregates 4.6M historical fire records into ~500 region-month text summaries and indexes them in a local ChromaDB collection. `api/main.py` (FastAPI) retrieves top-5 similar summaries for each user question and calls Claude (`claude-haiku-4-5-20251001`) to generate an answer. `app/src/ChatBox.jsx` is a glass-morphism panel fixed to the bottom-right of the globe that POSTs questions to the API and displays the conversation.

**Tech Stack:** Python — FastAPI 0.115.0, uvicorn 0.30.6, anthropic 0.40.0, chromadb 0.5.23, sentence-transformers 3.3.1, langchain-community 0.3.8. React — fetch (built-in, no new deps).

## Global Constraints

- ChromaDB collection name: `"wildfire-regions"`
- Embedding model: `sentence-transformers/all-MiniLM-L6-v2` (used identically in build_index and retriever)
- ChromaDB persist path: `rag/chroma_db/` (gitignored)
- Claude model: `claude-haiku-4-5-20251001`, max_tokens 512
- API port: 8000; CORS origin: `http://localhost:5173`
- `query_similar` signature: `def query_similar(question: str, chroma_dir: str, k: int = 5) -> list[str]`
- Document format exactly: `"Grid cell (lat={cell_lat}, lon={cell_lon}), Month={month_name} (month {N}): {count} fires ({min_yr}-{max_yr}). Avg brightness: {avg_b:.1f}. Avg FRP: {avg_frp:.1f} MW."`
- ChatBox: `position: fixed`, `bottom: 24px`, `right: 24px`, `width: 380px`, `height: 520px`
- Welcome message: `"Ask me about wildfire patterns — try 'Why is fire risk high in Northern California?' or 'What months are most dangerous in Texas?'"`
- max history sent to API: last 6 messages
- Working directory for all commands: `/Users/arjunpol/FireRAG`

---

### Task 1: RAG Index Builder

**Files:**
- Create: `rag/__init__.py`
- Create: `rag/build_index.py`
- Create: `tests/test_build_index.py`
- Modify: `requirements.txt`
- Modify: `.gitignore`

**Interfaces:**
- Produces: `build_index(db_path: str, chroma_dir: str) -> int` — indexes region-month summaries into ChromaDB, returns count of documents indexed.

---

- [ ] **Step 1: Add new dependencies to requirements.txt**

Open `requirements.txt` and append:

```
fastapi==0.115.0
uvicorn==0.30.6
anthropic==0.40.0
chromadb==0.5.23
sentence-transformers==3.3.1
langchain-community==0.3.8
```

Install them:

```bash
pip install fastapi==0.115.0 uvicorn==0.30.6 anthropic==0.40.0 chromadb==0.5.23 "sentence-transformers==3.3.1" "langchain-community==0.3.8"
```

Expected: packages install without errors (sentence-transformers downloads ~90 MB model on first use, not at install time).

- [ ] **Step 2: Add rag/chroma_db/ to .gitignore**

Open `.gitignore` and append:

```
rag/chroma_db/
```

- [ ] **Step 3: Create rag/__init__.py**

```bash
mkdir -p rag
touch rag/__init__.py
```

- [ ] **Step 4: Write the failing tests**

Create `tests/test_build_index.py`:

```python
import sqlite3
import pytest
import chromadb
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction

from rag.build_index import build_index


@pytest.fixture
def sample_db(tmp_path):
    db = str(tmp_path / "test.db")
    conn = sqlite3.connect(db)
    conn.execute("""
        CREATE TABLE fires_historical (
            id INTEGER PRIMARY KEY,
            latitude REAL, longitude REAL,
            brightness REAL, frp REAL,
            acq_date TEXT, acq_time TEXT,
            confidence TEXT, satellite TEXT,
            ingested_at TEXT
        )
    """)
    conn.executemany("""
        INSERT INTO fires_historical
            (latitude, longitude, brightness, frp, acq_date, acq_time, confidence, satellite, ingested_at)
        VALUES (?, ?, ?, ?, ?, '0000', 'high', 'N', '2026-06-29')
    """, [
        (37.0, -120.0, 320.0, 35.0, '2005-07-15'),
        (37.0, -120.0, 330.0, 40.0, '2006-07-20'),
        (35.0, -119.0, 310.0, 25.0, '2005-08-10'),
        (35.0, -119.0, 305.0, 22.0, '2007-08-05'),
    ])
    conn.commit()
    conn.close()
    return db


def test_returns_count(sample_db, tmp_path):
    count = build_index(db_path=sample_db, chroma_dir=str(tmp_path / "chroma"))
    assert isinstance(count, int)
    assert count >= 1


def test_collection_has_documents(sample_db, tmp_path):
    chroma_dir = str(tmp_path / "chroma")
    count = build_index(db_path=sample_db, chroma_dir=chroma_dir)
    client = chromadb.PersistentClient(path=chroma_dir)
    col = client.get_collection("wildfire-regions")
    assert col.count() == count


def test_document_format(sample_db, tmp_path):
    chroma_dir = str(tmp_path / "chroma")
    build_index(db_path=sample_db, chroma_dir=chroma_dir)
    ef = SentenceTransformerEmbeddingFunction(model_name="all-MiniLM-L6-v2")
    client = chromadb.PersistentClient(path=chroma_dir)
    col = client.get_collection("wildfire-regions", embedding_function=ef)
    result = col.get(limit=1)
    doc = result["documents"][0]
    assert "Grid cell" in doc
    assert "fires" in doc
    assert "Avg brightness" in doc
    assert "Avg FRP" in doc


def test_idempotent(sample_db, tmp_path):
    chroma_dir = str(tmp_path / "chroma")
    count1 = build_index(db_path=sample_db, chroma_dir=chroma_dir)
    count2 = build_index(db_path=sample_db, chroma_dir=chroma_dir)
    assert count1 == count2
```

- [ ] **Step 5: Run tests to confirm they fail**

```bash
python3 -m pytest tests/test_build_index.py -v
```

Expected: `ImportError: cannot import name 'build_index' from 'rag.build_index'`

- [ ] **Step 6: Implement rag/build_index.py**

Create `rag/build_index.py`:

```python
import argparse
import sqlite3

import chromadb
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction

_MONTHS = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]

_EMBED_MODEL = "all-MiniLM-L6-v2"
_COLLECTION = "wildfire-regions"
_BATCH_SIZE = 100


def build_index(db_path: str = "firerag.db", chroma_dir: str = "rag/chroma_db") -> int:
    ef = SentenceTransformerEmbeddingFunction(model_name=_EMBED_MODEL)
    client = chromadb.PersistentClient(path=chroma_dir)

    try:
        client.delete_collection(_COLLECTION)
    except Exception:
        pass
    collection = client.create_collection(_COLLECTION, embedding_function=ef)

    conn = sqlite3.connect(db_path)
    rows = conn.execute("""
        SELECT
            round(latitude  * 2) / 2 AS cell_lat,
            round(longitude * 2) / 2 AS cell_lon,
            CAST(strftime('%m', acq_date) AS INTEGER) AS month,
            COUNT(*)                  AS fire_count,
            AVG(brightness)           AS avg_brightness,
            AVG(frp)                  AS avg_frp,
            MIN(strftime('%Y', acq_date)) AS min_year,
            MAX(strftime('%Y', acq_date)) AS max_year
        FROM fires_historical
        GROUP BY cell_lat, cell_lon, month
    """).fetchall()
    conn.close()

    docs, ids = [], []
    for i, (cell_lat, cell_lon, month, fire_count, avg_b, avg_frp, min_yr, max_yr) in enumerate(rows):
        month_name = _MONTHS[int(month) - 1]
        doc = (
            f"Grid cell (lat={cell_lat}, lon={cell_lon}), "
            f"Month={month_name} (month {int(month)}): {fire_count} fires ({min_yr}-{max_yr}). "
            f"Avg brightness: {avg_b:.1f}. Avg FRP: {avg_frp:.1f} MW."
        )
        docs.append(doc)
        ids.append(f"region-{i}")

    for start in range(0, len(docs), _BATCH_SIZE):
        collection.add(
            documents=docs[start:start + _BATCH_SIZE],
            ids=ids[start:start + _BATCH_SIZE],
        )

    return len(docs)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default="firerag.db")
    parser.add_argument("--chroma-dir", default="rag/chroma_db")
    args = parser.parse_args()
    n = build_index(db_path=args.db, chroma_dir=args.chroma_dir)
    print(f"Indexed {n} region-month documents.")


if __name__ == "__main__":
    main()
```

- [ ] **Step 7: Run tests to confirm they pass**

```bash
python3 -m pytest tests/test_build_index.py -v
```

Expected: `4 passed` (first run downloads ~90 MB model — this is normal and only happens once).

- [ ] **Step 8: Commit**

```bash
git add rag/__init__.py rag/build_index.py tests/test_build_index.py requirements.txt .gitignore
git commit -m "feat: rag index builder — region-month aggregates into chromadb"
```

---

### Task 2: RAG Retriever

**Files:**
- Create: `rag/retriever.py`
- Create: `tests/test_retriever.py`

**Interfaces:**
- Consumes: ChromaDB collection `"wildfire-regions"` at a `chroma_dir` path (written by Task 1's `build_index`).
- Produces: `query_similar(question: str, chroma_dir: str, k: int = 5) -> list[str]`

---

- [ ] **Step 1: Write the failing tests**

Create `tests/test_retriever.py`:

```python
import pytest
import chromadb
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction

from rag.retriever import query_similar


@pytest.fixture
def chroma_dir(tmp_path):
    ef = SentenceTransformerEmbeddingFunction(model_name="all-MiniLM-L6-v2")
    client = chromadb.PersistentClient(path=str(tmp_path / "chroma"))
    col = client.create_collection("wildfire-regions", embedding_function=ef)
    col.add(
        documents=[
            "Grid cell (lat=37.0, lon=-120.0), Month=July (month 7): 100 fires (2005-2020). Avg brightness: 320.0. Avg FRP: 35.0 MW.",
            "Grid cell (lat=35.0, lon=-119.0), Month=August (month 8): 50 fires (2005-2020). Avg brightness: 310.0. Avg FRP: 25.0 MW.",
            "Grid cell (lat=34.0, lon=-118.0), Month=September (month 9): 75 fires (2005-2020). Avg brightness: 315.0. Avg FRP: 30.0 MW.",
            "Grid cell (lat=36.0, lon=-121.0), Month=October (month 10): 30 fires (2005-2020). Avg brightness: 305.0. Avg FRP: 20.0 MW.",
            "Grid cell (lat=38.0, lon=-122.0), Month=November (month 11): 20 fires (2005-2020). Avg brightness: 300.0. Avg FRP: 15.0 MW.",
            "Grid cell (lat=39.0, lon=-123.0), Month=December (month 12): 10 fires (2005-2020). Avg brightness: 295.0. Avg FRP: 10.0 MW.",
        ],
        ids=["r0", "r1", "r2", "r3", "r4", "r5"],
    )
    return str(tmp_path / "chroma")


def test_returns_list(chroma_dir):
    result = query_similar("fire risk in California", chroma_dir, k=3)
    assert isinstance(result, list)


def test_returns_k_results(chroma_dir):
    result = query_similar("fire patterns in summer", chroma_dir, k=3)
    assert len(result) == 3


def test_results_are_strings(chroma_dir):
    result = query_similar("wildfire history", chroma_dir, k=2)
    assert all(isinstance(r, str) and len(r) > 0 for r in result)
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
python3 -m pytest tests/test_retriever.py -v
```

Expected: `ImportError: cannot import name 'query_similar' from 'rag.retriever'`

- [ ] **Step 3: Implement rag/retriever.py**

Create `rag/retriever.py`:

```python
import chromadb
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction

_EMBED_MODEL = "all-MiniLM-L6-v2"
_COLLECTION = "wildfire-regions"


def query_similar(question: str, chroma_dir: str, k: int = 5) -> list[str]:
    ef = SentenceTransformerEmbeddingFunction(model_name=_EMBED_MODEL)
    client = chromadb.PersistentClient(path=chroma_dir)
    collection = client.get_collection(_COLLECTION, embedding_function=ef)
    results = collection.query(query_texts=[question], n_results=k)
    return results["documents"][0]
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
python3 -m pytest tests/test_retriever.py -v
```

Expected: `3 passed`

- [ ] **Step 5: Commit**

```bash
git add rag/retriever.py tests/test_retriever.py
git commit -m "feat: rag retriever — chromadb query wrapper"
```

---

### Task 3: FastAPI Backend

**Files:**
- Create: `api/__init__.py`
- Create: `api/main.py`
- Create: `tests/test_api.py`
- Modify: `.env.example`

**Interfaces:**
- Consumes: `query_similar(question, chroma_dir, k=5)` from `rag.retriever` (Task 2).
- Produces:
  - `GET /health` → `{"status": "ok"}`
  - `POST /chat` body `{question: str, history: [{role, content}]}` → `{"answer": str}`

---

- [ ] **Step 1: Create api/__init__.py**

```bash
mkdir -p api
touch api/__init__.py
```

- [ ] **Step 2: Write the failing tests**

Create `tests/test_api.py`:

```python
import pytest
from unittest.mock import patch, MagicMock


@pytest.fixture(autouse=True)
def env_and_path(monkeypatch, tmp_path):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    monkeypatch.setenv("CHROMA_DIR", str(tmp_path / "chroma"))
    # make the chroma dir exist so the startup check passes
    (tmp_path / "chroma").mkdir()


def _get_client():
    import importlib
    import api.main as m
    importlib.reload(m)
    from fastapi.testclient import TestClient
    return TestClient(m.app)


def test_health_endpoint():
    client = _get_client()
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_chat_missing_question():
    client = _get_client()
    resp = client.post("/chat", json={})
    assert resp.status_code == 422


def test_chat_returns_answer():
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text="Fire risk is high due to dry conditions.")]

    with patch("rag.retriever.query_similar", return_value=["doc1", "doc2"]), \
         patch("anthropic.Anthropic") as mock_anthropic:
        mock_anthropic.return_value.messages.create.return_value = mock_response
        client = _get_client()
        resp = client.post("/chat", json={"question": "Why is fire risk high?"})
        assert resp.status_code == 200
        assert "answer" in resp.json()
        assert len(resp.json()["answer"]) > 0
```

- [ ] **Step 3: Run tests to confirm they fail**

```bash
python3 -m pytest tests/test_api.py -v
```

Expected: `ImportError` or `ModuleNotFoundError: No module named 'api.main'`

- [ ] **Step 4: Implement api/main.py**

Create `api/main.py`:

```python
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
```

- [ ] **Step 5: Update .env.example**

Open `.env.example` and add:

```
FIRMS_MAP_KEY=your_key_here
ANTHROPIC_API_KEY=your_anthropic_key_here
```

- [ ] **Step 6: Run tests to confirm they pass**

```bash
python3 -m pytest tests/test_api.py -v
```

Expected: `3 passed`

- [ ] **Step 7: Commit**

```bash
git add api/__init__.py api/main.py tests/test_api.py .env.example
git commit -m "feat: fastapi backend — /chat and /health endpoints"
```

---

### Task 4: ChatBox UI + App.jsx Integration

**Files:**
- Create: `app/src/ChatBox.jsx`
- Modify: `app/src/App.jsx`

**Interfaces:**
- Consumes: `POST http://localhost:8000/chat` from Task 3.
- Produces: `<ChatBox />` — no props required.

---

- [ ] **Step 1: Create app/src/ChatBox.jsx**

```jsx
import { useState, useEffect, useRef } from 'react'

const WELCOME =
  "Ask me about wildfire patterns — try 'Why is fire risk high in Northern California?' or 'What months are most dangerous in Texas?'"

export default function ChatBox() {
  const [messages, setMessages] = useState([{ role: 'assistant', content: WELCOME }])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const messagesEndRef = useRef(null)

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, loading])

  const send = async () => {
    const question = input.trim()
    if (!question || loading) return
    setInput('')
    setError(null)
    const next = [...messages, { role: 'user', content: question }]
    setMessages(next)
    setLoading(true)
    try {
      const res = await fetch('http://localhost:8000/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question, history: messages.slice(-6) }),
      })
      if (!res.ok) throw new Error(`Server error ${res.status}`)
      const data = await res.json()
      setMessages(m => [...m, { role: 'assistant', content: data.answer }])
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  const onKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      send()
    }
  }

  return (
    <div style={{
      position: 'fixed', bottom: 24, right: 24,
      width: 380, height: 520,
      background: 'rgba(15,15,25,0.85)',
      backdropFilter: 'blur(12px)',
      border: '1px solid rgba(255,255,255,0.1)',
      borderRadius: 16,
      boxShadow: '0 8px 32px rgba(0,0,0,0.4)',
      display: 'flex', flexDirection: 'column',
      fontFamily: 'system-ui', fontSize: 13, color: '#e2e8f0',
      zIndex: 1000,
    }}>
      <div style={{
        padding: '12px 16px',
        borderBottom: '1px solid rgba(255,255,255,0.08)',
        display: 'flex', justifyContent: 'space-between', alignItems: 'center',
        fontWeight: 600, letterSpacing: 0.5,
      }}>
        <span>WildfireRAG</span>
        <span>🔥</span>
      </div>

      <div style={{
        flex: 1, overflowY: 'auto', padding: 12,
        display: 'flex', flexDirection: 'column', gap: 8,
      }}>
        {messages.map((m, i) => (
          <div key={i} style={{
            display: 'flex',
            justifyContent: m.role === 'user' ? 'flex-end' : 'flex-start',
          }}>
            <div style={{
              maxWidth: '80%', padding: '8px 12px',
              background: m.role === 'user' ? 'rgba(239,68,68,0.2)' : 'rgba(255,255,255,0.06)',
              border: m.role === 'user' ? '1px solid rgba(239,68,68,0.3)' : 'none',
              borderRadius: m.role === 'user' ? '12px 12px 2px 12px' : '12px 12px 12px 2px',
              lineHeight: 1.5, whiteSpace: 'pre-wrap',
            }}>
              {m.content}
            </div>
          </div>
        ))}
        {loading && (
          <div style={{ display: 'flex', justifyContent: 'flex-start' }}>
            <div style={{
              padding: '8px 12px',
              background: 'rgba(255,255,255,0.06)',
              borderRadius: '12px 12px 12px 2px',
              letterSpacing: 4,
            }}>●●●</div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      <div style={{ padding: 12, borderTop: '1px solid rgba(255,255,255,0.08)' }}>
        {error && (
          <div style={{ color: '#ef4444', fontSize: 12, marginBottom: 8 }}>{error}</div>
        )}
        <div style={{ display: 'flex', gap: 8 }}>
          <textarea
            rows={2}
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={onKeyDown}
            placeholder="Ask about fire patterns..."
            style={{
              flex: 1,
              background: 'rgba(255,255,255,0.08)',
              border: '1px solid rgba(255,255,255,0.12)',
              borderRadius: 8,
              color: '#e2e8f0',
              padding: '8px 10px',
              resize: 'none',
              fontFamily: 'system-ui',
              fontSize: 13,
              outline: 'none',
            }}
          />
          <button
            onClick={send}
            disabled={loading || !input.trim()}
            style={{
              background: loading || !input.trim() ? 'rgba(239,68,68,0.4)' : '#ef4444',
              color: 'white',
              border: 'none',
              borderRadius: 8,
              padding: '8px 14px',
              cursor: loading || !input.trim() ? 'not-allowed' : 'pointer',
              fontWeight: 600,
              fontSize: 13,
              alignSelf: 'flex-end',
            }}
          >
            Send
          </button>
        </div>
      </div>
    </div>
  )
}
```

- [ ] **Step 2: Update app/src/App.jsx**

Replace the contents of `app/src/App.jsx` with:

```jsx
import GlobeMap from './GlobeMap.jsx'
import ChatBox from './ChatBox.jsx'

const token = import.meta.env.VITE_MAPBOX_TOKEN

export default function App() {
  if (!token) {
    return (
      <div style={{
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        height: '100vh', fontFamily: 'system-ui', color: '#ef4444',
        fontSize: '16px',
      }}>
        Missing VITE_MAPBOX_TOKEN — add it to app/.env
      </div>
    )
  }
  return (
    <>
      <GlobeMap mapboxToken={token} />
      <ChatBox />
    </>
  )
}
```

- [ ] **Step 3: Verify the Vite build succeeds**

```bash
cd app && npx vite build 2>&1 | tail -5
```

Expected: `✓ built in X.XXs`

- [ ] **Step 4: Commit**

```bash
git add app/src/ChatBox.jsx app/src/App.jsx
git commit -m "feat: glass-morphism chatbox ui integrated into globe"
```

---

## Running the Full System

After all tasks are complete:

```bash
# Terminal 1 — build the vector index (one time, ~30s)
python3 rag/build_index.py

# Terminal 2 — start the API backend
uvicorn api.main:app --reload --port 8000

# Terminal 3 — start the frontend
python3 export_data.py
cd app && npm run dev
```

Add `ANTHROPIC_API_KEY=sk-ant-...` to your root `.env` file before starting the API.

Open `http://localhost:5173` — the globe loads with the chatbox panel in the bottom-right.
