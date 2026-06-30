# Phase 5 News Feed Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a wildfire news feed that fetches articles from News API, stores them in SQLite, indexes them in ChromaDB, serves them via FastAPI, and displays them in a glass-morphism left panel on the globe dashboard — with the RAG chatbox updated to retrieve from both historical data and current news.

**Architecture:** `data/news.py` fetches from newsapi.org and stores in an `articles` SQLite table (deduped by URL). `rag/build_news_index.py` embeds articles into a `"wildfire-news"` ChromaDB collection. `api/main.py` gains `GET /news` (latest 15 articles) and updates `POST /chat` to query both ChromaDB collections (top-3 historical + top-2 news) before calling Claude. `app/src/NewsPanel.jsx` is a fixed left panel that fetches and displays articles.

**Tech Stack:** Python — requests (already installed), sqlite3 (stdlib), chromadb, sentence-transformers. React — built-in fetch, no new packages.

## Global Constraints

- News API endpoint: `https://newsapi.org/v2/everything?q=wildfire OR "forest fire"&language=en&sortBy=publishedAt&from=<ISO>&pageSize=100`
- `articles` table: `id, title, description, url (UNIQUE), source, published_at, fetched_at`
- Dedup: `INSERT OR IGNORE` on `url`
- `fetch_articles` signature: `fetch_articles(db_path: str, api_key: str, hours: int = 48) -> int`
- News ChromaDB collection name: `"wildfire-news"` (add `NEWS_COLLECTION = "wildfire-news"` to `rag/config.py`)
- News document format exactly: `"[SOURCE] TITLE. DESCRIPTION. Published: PUBLISHED_AT."`
- `query_news` signature: `query_news(question: str, chroma_dir: str, k: int = 2) -> list[str]`
- `GET /news`: returns latest 15 articles from `DB_PATH` ordered by `published_at DESC`; returns `[]` on `sqlite3.OperationalError`
- `/chat` dual retrieval: `query_similar(k=3)` prefixed `[HISTORICAL]` + `query_news(k=2)` prefixed `[NEWS]`; if `query_news` raises any exception, proceed with historical-only (no 500)
- System prompt context line: `"Relevant data (historical fire records and recent news):"`
- `DB_PATH = os.environ.get("DB_PATH", "firerag.db")` in `api/main.py`
- NewsPanel: `position: fixed, left: 0, top: 0, width: 300px, height: 100vh`
- NewsPanel background: `rgba(15,15,25,0.85)`, `backdropFilter: blur(12px)`, `border-right: 1px solid rgba(255,255,255,0.1)`
- Source chip: `background: rgba(239,68,68,0.2)`, `border: 1px solid rgba(239,68,68,0.3)`, `color: #fca5a5`, `fontSize: 10px`
- Click card: `window.open(article.url, '_blank', 'noopener,noreferrer')`
- `NEWS_API_KEY` from root `.env` via `python-dotenv`
- Working directory for all commands: `/Users/arjunpol/FireRAG`

---

### Task 1: News API Fetcher + articles Table

**Files:**
- Modify: `data/db.py`
- Create: `data/news.py`
- Create: `tests/test_news.py`
- Modify: `.env.example`

**Interfaces:**
- Produces: `fetch_articles(db_path: str, api_key: str, hours: int = 48) -> int`; `articles` table in SQLite with columns `id, title, description, url, source, published_at, fetched_at`

---

- [ ] **Step 1: Add articles table to data/db.py**

Open `data/db.py` and add the `articles` DDL to the `_DDL` string, after `fires_predictions`:

```python
_DDL = """
CREATE TABLE IF NOT EXISTS fires_realtime (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    latitude    REAL,
    longitude   REAL,
    brightness  REAL,
    acq_date    TEXT,
    acq_time    TEXT,
    confidence  TEXT,
    satellite   TEXT,
    ingested_at TEXT
);

CREATE TABLE IF NOT EXISTS weather (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    latitude    REAL,
    longitude   REAL,
    temperature REAL,
    humidity    REAL,
    wind_speed  REAL,
    wind_dir    REAL,
    timestamp   TEXT,
    ingested_at TEXT
);

CREATE TABLE IF NOT EXISTS fires_historical (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    latitude    REAL,
    longitude   REAL,
    brightness  REAL,
    frp         REAL,
    acq_date    TEXT,
    acq_time    TEXT,
    confidence  TEXT,
    satellite   TEXT,
    ingested_at TEXT
);

CREATE TABLE IF NOT EXISTS fires_predictions (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    latitude         REAL,
    longitude        REAL,
    fire_probability REAL,
    prediction_date  TEXT,
    model_version    TEXT,
    ingested_at      TEXT
);

CREATE TABLE IF NOT EXISTS articles (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    title        TEXT NOT NULL,
    description  TEXT,
    url          TEXT NOT NULL UNIQUE,
    source       TEXT,
    published_at TEXT,
    fetched_at   TEXT
);
"""
```

- [ ] **Step 2: Add NEWS_API_KEY to .env.example**

Open `.env.example` and append:
```
NEWS_API_KEY=your_newsapi_key_here
```

- [ ] **Step 3: Write the failing tests**

Create `tests/test_news.py`:

```python
import sqlite3
import pytest
from unittest.mock import patch, MagicMock

from data.news import fetch_articles

_MOCK_RESPONSE = {
    "status": "ok",
    "totalResults": 2,
    "articles": [
        {
            "source": {"name": "Reuters"},
            "title": "California wildfire forces 10,000 to evacuate",
            "description": "A fast-moving blaze near Sacramento grows to 5,000 acres.",
            "url": "https://reuters.com/article/1",
            "publishedAt": "2026-06-30T10:00:00Z",
        },
        {
            "source": {"name": "AP News"},
            "title": "Oregon forest fire spreads overnight",
            "description": "Crews battle blaze in southern Oregon.",
            "url": "https://apnews.com/article/2",
            "publishedAt": "2026-06-30T08:00:00Z",
        },
    ],
}


@pytest.fixture
def db(tmp_path):
    path = str(tmp_path / "test.db")
    conn = sqlite3.connect(path)
    conn.execute("""
        CREATE TABLE articles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT,
            url TEXT NOT NULL UNIQUE,
            source TEXT,
            published_at TEXT,
            fetched_at TEXT
        )
    """)
    conn.commit()
    conn.close()
    return path


def _mock_get(response_data):
    mock = MagicMock()
    mock.status_code = 200
    mock.json.return_value = response_data
    return mock


def test_returns_count(db):
    with patch("requests.get", return_value=_mock_get(_MOCK_RESPONSE)):
        count = fetch_articles(db_path=db, api_key="test-key")
    assert isinstance(count, int)
    assert count == 2


def test_deduplication(db):
    with patch("requests.get", return_value=_mock_get(_MOCK_RESPONSE)):
        count1 = fetch_articles(db_path=db, api_key="test-key")
        count2 = fetch_articles(db_path=db, api_key="test-key")
    assert count1 == 2
    assert count2 == 0  # same URLs → INSERT OR IGNORE → 0 new


def test_inserts_fields(db):
    with patch("requests.get", return_value=_mock_get(_MOCK_RESPONSE)):
        fetch_articles(db_path=db, api_key="test-key")
    conn = sqlite3.connect(db)
    row = conn.execute("SELECT title, url, source FROM articles WHERE url = ?",
                       ("https://reuters.com/article/1",)).fetchone()
    conn.close()
    assert row[0] == "California wildfire forces 10,000 to evacuate"
    assert row[1] == "https://reuters.com/article/1"
    assert row[2] == "Reuters"


def test_raises_on_api_error(db):
    error_resp = {"status": "error", "message": "apiKeyInvalid"}
    with patch("requests.get", return_value=_mock_get(error_resp)):
        with pytest.raises(RuntimeError, match="apiKeyInvalid"):
            fetch_articles(db_path=db, api_key="bad-key")
```

- [ ] **Step 4: Run tests to confirm they fail**

```bash
python3 -m pytest tests/test_news.py -v
```

Expected: `ImportError: cannot import name 'fetch_articles' from 'data.news'`

- [ ] **Step 5: Implement data/news.py**

Create `data/news.py`:

```python
import argparse
import os
import sqlite3
from datetime import datetime, timedelta, timezone

import requests
from dotenv import load_dotenv

load_dotenv()

_API_URL = "https://newsapi.org/v2/everything"

_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS articles (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    title        TEXT NOT NULL,
    description  TEXT,
    url          TEXT NOT NULL UNIQUE,
    source       TEXT,
    published_at TEXT,
    fetched_at   TEXT
)
"""


def fetch_articles(db_path: str, api_key: str, hours: int = 48) -> int:
    from_dt = (datetime.now(timezone.utc) - timedelta(hours=hours)).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
    resp = requests.get(
        _API_URL,
        params={
            "q": 'wildfire OR "forest fire"',
            "language": "en",
            "sortBy": "publishedAt",
            "from": from_dt,
            "pageSize": 100,
            "apiKey": api_key,
        },
    )
    if resp.status_code != 200:
        raise RuntimeError(f"News API HTTP {resp.status_code}")
    data = resp.json()
    if data.get("status") == "error":
        raise RuntimeError(f"News API error: {data.get('message', 'unknown')}")

    fetched_at = datetime.now(timezone.utc).isoformat()
    conn = sqlite3.connect(db_path)
    conn.execute(_CREATE_TABLE)

    count = 0
    for article in data.get("articles", []):
        title = (article.get("title") or "").strip()
        if not title or title == "[Removed]":
            continue
        cursor = conn.execute(
            """INSERT OR IGNORE INTO articles
               (title, description, url, source, published_at, fetched_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                title,
                article.get("description"),
                article.get("url", ""),
                (article.get("source") or {}).get("name"),
                article.get("publishedAt"),
                fetched_at,
            ),
        )
        count += cursor.rowcount

    conn.commit()
    conn.close()
    return count


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default="firerag.db")
    parser.add_argument("--hours", type=int, default=48)
    args = parser.parse_args()
    api_key = os.environ.get("NEWS_API_KEY", "")
    if not api_key:
        raise SystemExit("NEWS_API_KEY not set. Add it to .env.")
    n = fetch_articles(db_path=args.db, api_key=api_key, hours=args.hours)
    print(f"Fetched {n} new articles.")


if __name__ == "__main__":
    main()
```

- [ ] **Step 6: Run tests to confirm they pass**

```bash
python3 -m pytest tests/test_news.py -v
```

Expected: `4 passed`

- [ ] **Step 7: Commit**

```bash
git add data/db.py data/news.py tests/test_news.py .env.example
git commit -m "feat: news api fetcher and articles table"
```

---

### Task 2: News ChromaDB Index

**Files:**
- Modify: `rag/config.py`
- Create: `rag/build_news_index.py`
- Create: `tests/test_build_news_index.py`

**Interfaces:**
- Consumes: `articles` table from Task 1; `EMBED_MODEL`, `NEWS_COLLECTION` from `rag/config.py`
- Produces: `build_news_index(db_path: str, chroma_dir: str) -> int`; ChromaDB collection `"wildfire-news"` at `chroma_dir`

---

- [ ] **Step 1: Add NEWS_COLLECTION to rag/config.py**

Replace the contents of `rag/config.py` with:

```python
EMBED_MODEL = "all-MiniLM-L6-v2"
COLLECTION_NAME = "wildfire-regions"
NEWS_COLLECTION = "wildfire-news"
```

- [ ] **Step 2: Write the failing tests**

Create `tests/test_build_news_index.py`:

```python
import sqlite3
import pytest
import chromadb
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction

from rag.build_news_index import build_news_index


@pytest.fixture
def sample_db(tmp_path):
    db = str(tmp_path / "test.db")
    conn = sqlite3.connect(db)
    conn.execute("""
        CREATE TABLE articles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT,
            url TEXT NOT NULL UNIQUE,
            source TEXT,
            published_at TEXT,
            fetched_at TEXT
        )
    """)
    conn.executemany(
        "INSERT INTO articles (title, description, url, source, published_at, fetched_at) VALUES (?, ?, ?, ?, ?, ?)",
        [
            ("California fire forces evacuation", "Blaze grows near Sacramento.", "https://example.com/1", "Reuters", "2026-06-30T10:00:00Z", "2026-06-30T12:00:00Z"),
            ("Oregon forest fire spreads", "Crews battle southern Oregon blaze.", "https://example.com/2", "AP News", "2026-06-30T08:00:00Z", "2026-06-30T12:00:00Z"),
        ],
    )
    conn.commit()
    conn.close()
    return db


def test_returns_count(sample_db, tmp_path):
    count = build_news_index(db_path=sample_db, chroma_dir=str(tmp_path / "chroma"))
    assert isinstance(count, int)
    assert count == 2


def test_collection_has_documents(sample_db, tmp_path):
    chroma_dir = str(tmp_path / "chroma")
    count = build_news_index(db_path=sample_db, chroma_dir=chroma_dir)
    client = chromadb.PersistentClient(path=chroma_dir)
    col = client.get_collection("wildfire-news")
    assert col.count() == count


def test_document_format(sample_db, tmp_path):
    chroma_dir = str(tmp_path / "chroma")
    build_news_index(db_path=sample_db, chroma_dir=chroma_dir)
    ef = SentenceTransformerEmbeddingFunction(model_name="all-MiniLM-L6-v2")
    client = chromadb.PersistentClient(path=chroma_dir)
    col = client.get_collection("wildfire-news", embedding_function=ef)
    result = col.get(limit=1)
    doc = result["documents"][0]
    assert doc.startswith("[")
    assert "Published:" in doc


def test_idempotent(sample_db, tmp_path):
    chroma_dir = str(tmp_path / "chroma")
    count1 = build_news_index(db_path=sample_db, chroma_dir=chroma_dir)
    count2 = build_news_index(db_path=sample_db, chroma_dir=chroma_dir)
    assert count1 == count2
```

- [ ] **Step 3: Run tests to confirm they fail**

```bash
python3 -m pytest tests/test_build_news_index.py -v
```

Expected: `ImportError: cannot import name 'build_news_index' from 'rag.build_news_index'`

- [ ] **Step 4: Implement rag/build_news_index.py**

Create `rag/build_news_index.py`:

```python
import argparse
import sqlite3

import chromadb
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction

from rag.config import EMBED_MODEL, NEWS_COLLECTION

_BATCH_SIZE = 100


def build_news_index(db_path: str = "firerag.db", chroma_dir: str = "rag/chroma_db") -> int:
    ef = SentenceTransformerEmbeddingFunction(model_name=EMBED_MODEL)
    client = chromadb.PersistentClient(path=chroma_dir)

    try:
        client.delete_collection(NEWS_COLLECTION)
    except Exception:
        pass
    collection = client.create_collection(NEWS_COLLECTION, embedding_function=ef)

    conn = sqlite3.connect(db_path)
    rows = conn.execute(
        "SELECT title, description, url, source, published_at FROM articles"
    ).fetchall()
    conn.close()

    docs, ids = [], []
    for i, (title, description, url, source, published_at) in enumerate(rows):
        source_label = source or "Unknown"
        desc_part = f" {description}" if description else ""
        date_part = f" Published: {published_at}." if published_at else ""
        doc = f"[{source_label}] {title}.{desc_part}{date_part}"
        docs.append(doc)
        ids.append(f"news-{i}")

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
    n = build_news_index(db_path=args.db, chroma_dir=args.chroma_dir)
    print(f"Indexed {n} news articles.")


if __name__ == "__main__":
    main()
```

- [ ] **Step 5: Run tests to confirm they pass**

```bash
python3 -m pytest tests/test_build_news_index.py -v
```

Expected: `4 passed`

- [ ] **Step 6: Commit**

```bash
git add rag/config.py rag/build_news_index.py tests/test_build_news_index.py
git commit -m "feat: news chromadb index builder"
```

---

### Task 3: Retriever + API Updates

**Files:**
- Modify: `rag/retriever.py`
- Modify: `api/main.py`
- Modify: `tests/test_retriever.py`
- Modify: `tests/test_api.py`

**Interfaces:**
- Consumes: `NEWS_COLLECTION` from `rag/config.py` (Task 2); existing `query_similar`, `CHROMA_DIR`, `ANTHROPIC_API_KEY` from prior tasks
- Produces: `query_news(question: str, chroma_dir: str, k: int = 2) -> list[str]`; `GET /news -> list[ArticleOut]`; updated `/chat` with dual retrieval

---

- [ ] **Step 1: Update rag/retriever.py — add query_news**

Replace the full contents of `rag/retriever.py` with:

```python
import chromadb
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction

from rag.config import COLLECTION_NAME, EMBED_MODEL, NEWS_COLLECTION

_ef = SentenceTransformerEmbeddingFunction(model_name=EMBED_MODEL)
_clients: dict[str, chromadb.PersistentClient] = {}


def _get_client(chroma_dir: str) -> chromadb.PersistentClient:
    if chroma_dir not in _clients:
        _clients[chroma_dir] = chromadb.PersistentClient(path=chroma_dir)
    return _clients[chroma_dir]


def query_similar(question: str, chroma_dir: str, k: int = 5) -> list[str]:
    collection = _get_client(chroma_dir).get_collection(COLLECTION_NAME, embedding_function=_ef)
    results = collection.query(query_texts=[question], n_results=k)
    return results["documents"][0]


def query_news(question: str, chroma_dir: str, k: int = 2) -> list[str]:
    collection = _get_client(chroma_dir).get_collection(NEWS_COLLECTION, embedding_function=_ef)
    results = collection.query(query_texts=[question], n_results=k)
    return results["documents"][0]
```

- [ ] **Step 2: Add retriever tests**

Open `tests/test_retriever.py` and add at the end:

```python
@pytest.fixture
def news_chroma_dir(tmp_path):
    ef = SentenceTransformerEmbeddingFunction(model_name="all-MiniLM-L6-v2")
    client = chromadb.PersistentClient(path=str(tmp_path / "chroma_news"))
    col = client.create_collection("wildfire-news", embedding_function=ef)
    col.add(
        documents=[
            "[Reuters] California wildfire forces evacuation. Blaze near Sacramento. Published: 2026-06-30T10:00:00Z.",
            "[AP News] Oregon forest fire spreads overnight. Crews battle southern blaze. Published: 2026-06-30T08:00:00Z.",
            "[BBC] Texas drought worsens fire risk. Dry conditions across the state. Published: 2026-06-30T06:00:00Z.",
        ],
        ids=["n0", "n1", "n2"],
    )
    return str(tmp_path / "chroma_news")


def test_query_news_returns_list(news_chroma_dir):
    from rag.retriever import query_news
    result = query_news("fire news", news_chroma_dir, k=2)
    assert isinstance(result, list)


def test_query_news_returns_k_results(news_chroma_dir):
    from rag.retriever import query_news
    result = query_news("California wildfire", news_chroma_dir, k=2)
    assert len(result) == 2
```

- [ ] **Step 3: Run retriever tests**

```bash
python3 -m pytest tests/test_retriever.py -v
```

Expected: `5 passed` (3 existing + 2 new)

- [ ] **Step 4: Update api/main.py**

Replace the full contents of `api/main.py` with:

```python
import os
import sqlite3

import anthropic
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from rag.retriever import query_news, query_similar

load_dotenv()

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
CHROMA_DIR = os.environ.get("CHROMA_DIR", "rag/chroma_db")
DB_PATH = os.environ.get("DB_PATH", "firerag.db")

_SYSTEM_PROMPT = """\
You are a wildfire analysis assistant for WildfireRAG. You have access to historical fire data \
for the United States. Answer questions about fire risk, patterns, and history concisely and clearly.

Relevant data (historical fire records and recent news):
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

    context_parts = [f"[HISTORICAL] {doc}" for doc in historical_docs]
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
```

- [ ] **Step 5: Add API tests**

Open `tests/test_api.py` and add at the end (after the existing tests):

```python
def test_news_endpoint_empty_when_no_table():
    import importlib
    import api.main as m
    with patch.dict("os.environ", {"DB_PATH": "/nonexistent/db.sqlite", "ANTHROPIC_API_KEY": "sk-test"}), \
         patch("os.path.exists", return_value=True):
        importlib.reload(m)
        from fastapi.testclient import TestClient
        client = TestClient(m.app)
        resp = client.get("/news")
        assert resp.status_code == 200
        assert resp.json() == []


def test_news_endpoint_returns_articles(tmp_path):
    import sqlite3 as _sqlite3
    db = str(tmp_path / "test.db")
    conn = _sqlite3.connect(db)
    conn.execute("""CREATE TABLE articles (id INTEGER PRIMARY KEY, title TEXT, description TEXT,
                    url TEXT UNIQUE, source TEXT, published_at TEXT, fetched_at TEXT)""")
    conn.execute("INSERT INTO articles VALUES (1, 'Fire in CA', 'Big blaze', 'http://x.com/1', 'Reuters', '2026-06-30T10:00:00Z', '2026-06-30T12:00:00Z')")
    conn.commit()
    conn.close()

    import importlib
    import api.main as m
    with patch.dict("os.environ", {"DB_PATH": db, "ANTHROPIC_API_KEY": "sk-test"}), \
         patch("os.path.exists", return_value=True):
        importlib.reload(m)
        from fastapi.testclient import TestClient
        client = TestClient(m.app)
        resp = client.get("/news")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["title"] == "Fire in CA"
        assert data[0]["source"] == "Reuters"
```

- [ ] **Step 6: Run all API tests**

```bash
python3 -m pytest tests/test_api.py -v
```

Expected: `6 passed` (4 existing + 2 new)

- [ ] **Step 7: Commit**

```bash
git add rag/retriever.py api/main.py tests/test_retriever.py tests/test_api.py
git commit -m "feat: query_news retriever, GET /news endpoint, dual retrieval in /chat"
```

---

### Task 4: NewsPanel UI + App.jsx

**Files:**
- Create: `app/src/NewsPanel.jsx`
- Modify: `app/src/App.jsx`

**Interfaces:**
- Consumes: `GET http://localhost:8000/news` from Task 3
- Produces: `<NewsPanel />` — no props required

---

- [ ] **Step 1: Create app/src/NewsPanel.jsx**

```jsx
import { useState, useEffect } from 'react'

function timeAgo(dateStr) {
  if (!dateStr) return ''
  const diff = Date.now() - new Date(dateStr).getTime()
  const minutes = Math.floor(diff / 60000)
  if (minutes < 1) return 'just now'
  if (minutes < 60) return `${minutes}m ago`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours}h ago`
  return `${Math.floor(hours / 24)}d ago`
}

function SkeletonCard() {
  return (
    <div style={{ padding: 12, marginBottom: 4 }}>
      <div style={{ height: 10, background: 'rgba(255,255,255,0.08)', borderRadius: 4, marginBottom: 8, width: '40%' }} />
      <div style={{ height: 13, background: 'rgba(255,255,255,0.08)', borderRadius: 4, marginBottom: 4 }} />
      <div style={{ height: 13, background: 'rgba(255,255,255,0.08)', borderRadius: 4, width: '75%' }} />
    </div>
  )
}

export default function NewsPanel() {
  const [articles, setArticles] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    fetch('http://localhost:8000/news')
      .then(r => {
        if (!r.ok) throw new Error(`Server error ${r.status}`)
        return r.json()
      })
      .then(data => setArticles(data))
      .catch(() => setError('Could not load news.'))
      .finally(() => setLoading(false))
  }, [])

  return (
    <div style={{
      position: 'fixed', left: 0, top: 0,
      width: 300, height: '100vh',
      background: 'rgba(15,15,25,0.85)',
      backdropFilter: 'blur(12px)',
      borderRight: '1px solid rgba(255,255,255,0.1)',
      display: 'flex', flexDirection: 'column',
      fontFamily: 'system-ui', color: '#e2e8f0',
      zIndex: 1000,
    }}>
      <div style={{
        padding: '16px',
        borderBottom: '1px solid rgba(255,255,255,0.08)',
        display: 'flex', justifyContent: 'space-between', alignItems: 'center',
        fontWeight: 600, fontSize: 14,
      }}>
        <span>Live News</span>
        <span>📰</span>
      </div>

      <div style={{ flex: 1, overflowY: 'auto', padding: 8 }}>
        {loading && Array.from({ length: 5 }).map((_, i) => <SkeletonCard key={i} />)}

        {error && (
          <div style={{ padding: 12, color: '#94a3b8', fontSize: 12 }}>{error}</div>
        )}

        {!loading && !error && articles.length === 0 && (
          <div style={{ padding: 12, color: '#94a3b8', fontSize: 12 }}>
            No articles yet. Run: python3 data/news.py
          </div>
        )}

        {articles.map((article, i) => (
          <div
            key={i}
            onClick={() => window.open(article.url, '_blank', 'noopener,noreferrer')}
            style={{
              padding: 12, marginBottom: 4, borderRadius: 8,
              cursor: 'pointer',
              transition: 'background 0.15s',
            }}
            onMouseEnter={e => e.currentTarget.style.background = 'rgba(255,255,255,0.06)'}
            onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
          >
            <div style={{ marginBottom: 6, display: 'flex', alignItems: 'center', gap: 6 }}>
              <span style={{
                background: 'rgba(239,68,68,0.2)',
                border: '1px solid rgba(239,68,68,0.3)',
                borderRadius: 4, padding: '2px 6px',
                fontSize: 10, color: '#fca5a5',
                whiteSpace: 'nowrap', overflow: 'hidden',
                maxWidth: 120, textOverflow: 'ellipsis',
              }}>
                {article.source || 'Unknown'}
              </span>
              <span style={{ fontSize: 10, color: '#64748b' }}>
                {timeAgo(article.published_at)}
              </span>
            </div>
            <div style={{
              fontSize: 13, fontWeight: 600, lineHeight: 1.4,
              overflow: 'hidden', display: '-webkit-box',
              WebkitLineClamp: 2, WebkitBoxOrient: 'vertical',
            }}>
              {article.title}
            </div>
            {article.description && (
              <div style={{
                fontSize: 11, color: '#94a3b8', marginTop: 4,
                overflow: 'hidden', display: '-webkit-box',
                WebkitLineClamp: 3, WebkitBoxOrient: 'vertical',
                lineHeight: 1.5,
              }}>
                {article.description}
              </div>
            )}
          </div>
        ))}
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
import NewsPanel from './NewsPanel.jsx'

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
      <NewsPanel />
      <ChatBox />
    </>
  )
}
```

- [ ] **Step 3: Verify Vite build**

```bash
cd app && npx vite build 2>&1 | tail -5
```

Expected: `✓ built in X.XXs`

- [ ] **Step 4: Commit**

```bash
git add app/src/NewsPanel.jsx app/src/App.jsx
git commit -m "feat: news panel left sidebar integrated into globe dashboard"
```

---

## Running the Full System

```bash
# Fetch articles (needs NEWS_API_KEY in .env)
python3 data/news.py

# Re-index news into ChromaDB
python3 -m rag.build_news_index

# Start API
uvicorn api.main:app --reload --port 8000

# Start frontend
python3 export_data.py && cd app && npm run dev
```

Open `http://localhost:5173` — left panel shows live news, chatbox now answers with both historical data and current articles.
