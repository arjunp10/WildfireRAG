# WildfireRAG Phase 4 Design — RAG Chatbox

**Date:** 2026-06-29
**Status:** Approved

## Overview

Phase 4 adds a conversational RAG chatbox overlaid on the Mapbox 3D globe. Users ask natural language questions about wildfire patterns ("Why is fire risk high in Northern California?", "What's the fire pattern here in July?"). The system retrieves similar historical fire summaries from a ChromaDB vector store, passes them as context to Claude, and streams the answer back into the chatbox panel.

## Architecture

```
firerag.db
    ↓ rag/build_index.py (run once)
rag/chroma_db/          ← persisted ChromaDB collection (~500 region-month docs)
    ↓
rag/retriever.py        ← query wrapper (returns top-k similar region summaries)
    ↓
api/main.py             ← FastAPI: POST /chat, GET /health (CORS for localhost:5173)
    ↓ HTTP (localhost:8000)
app/src/ChatBox.jsx     ← React glass-morphism panel overlaid on globe
```

Workflow:
1. Run `python3 rag/build_index.py` once to build the vector index.
2. Run `uvicorn api.main:app --reload --port 8000` to start the backend.
3. Run `npm run dev` in `app/` as before for the frontend.

## File Structure

```
rag/
├── __init__.py
├── build_index.py       # one-time indexer: fires_historical → ChromaDB
└── retriever.py         # ChromaDB query wrapper
api/
├── __init__.py
└── main.py              # FastAPI app
app/src/
└── ChatBox.jsx          # React chat panel (new)
app/src/App.jsx          # modified: add <ChatBox />
.env.example             # modified: add ANTHROPIC_API_KEY
requirements.txt         # modified: add new deps
.gitignore               # modified: add rag/chroma_db/
```

## rag/build_index.py

**Purpose:** One-time script that aggregates `fires_historical` into region-month summaries and indexes them into ChromaDB.

**Aggregation query:** Group `fires_historical` by `(round(latitude*2)/2, round(longitude*2)/2, strftime('%m', acq_date))`. For each group compute: fire count, average brightness, average FRP, min/max acq_date year range.

**Document format** (one per group):
```
Grid cell (lat=37.0, lon=-120.5), Month=July (month 7): 1847 fires (2001-2020).
Avg brightness: 339.2. Avg FRP: 42.1 MW.
```

**Embedding model:** `sentence-transformers/all-MiniLM-L6-v2` (local, no API key required).

**ChromaDB:** persistent client at `rag/chroma_db/`, collection name `"wildfire-regions"`. If the collection already exists, delete and recreate it (idempotent).

**CLI:**
```bash
python3 rag/build_index.py [--db firerag.db] [--chroma-dir rag/chroma_db]
```
Prints: `Indexed N region-month documents.`

**Tests:** `tests/test_build_index.py`
- `test_returns_count` — returns integer >= 1
- `test_collection_has_documents` — ChromaDB collection count matches return value
- `test_document_format` — spot-check one document contains "Grid cell" and "fires"
- `test_idempotent` — calling twice produces same count (no duplicates)

## rag/retriever.py

**Purpose:** Thin wrapper around ChromaDB query. Loads the persisted collection and returns the top-k most similar document texts for a given query string.

**Interface:**
```python
def query_similar(question: str, chroma_dir: str, k: int = 5) -> list[str]:
    """Return top-k region-month summary texts most similar to question."""
```

Uses the same `all-MiniLM-L6-v2` embedding function as `build_index.py`.

**Tests:** `tests/test_retriever.py`
- `test_returns_list` — returns a list
- `test_returns_k_results` — returns exactly k results when k < collection size
- `test_results_are_strings` — all items are non-empty strings

## api/main.py

**Purpose:** FastAPI backend bridging retrieval and Claude.

**Startup:** Load ChromaDB collection from `rag/chroma_db/` (path from env var `CHROMA_DIR`, default `"rag/chroma_db"`). Fail fast with a clear error if the directory doesn't exist (user forgot to run `build_index.py`).

**CORS:** Allow origin `http://localhost:5173`, methods `["POST", "GET"]`, headers `["Content-Type"]`.

**Endpoints:**

`GET /health`
- Response: `{"status": "ok"}`

`POST /chat`
- Request body:
  ```json
  {
    "question": "Why is fire risk high in Northern California?",
    "history": [
      {"role": "user", "content": "..."},
      {"role": "assistant", "content": "..."}
    ]
  }
  ```
  `history` is optional, max last 6 messages used.
- Logic:
  1. Call `query_similar(question, chroma_dir, k=5)` to get context docs.
  2. Build system prompt (see below).
  3. Call `anthropic.Anthropic().messages.create(model="claude-haiku-4-5-20251001", max_tokens=512, system=system_prompt, messages=[...history, {role: user, content: question}])`.
  4. Return `{"answer": response.content[0].text}`.
- Error: if Claude call fails, return HTTP 500 with `{"detail": "Claude API error: <message>"}`.

**System prompt:**
```
You are a wildfire analysis assistant for WildfireRAG. You have access to historical fire data
for the United States. Answer questions about fire risk, patterns, and history concisely and clearly.

Relevant historical fire data (retrieved by similarity):
{context}

Base your answer on this data. If the data doesn't cover the user's question, say so briefly.
Keep answers under 150 words.
```

**Environment variables** (loaded via `python-dotenv` from root `.env`):
- `ANTHROPIC_API_KEY` — required, fail fast if missing
- `CHROMA_DIR` — optional, default `"rag/chroma_db"`

**Run:**
```bash
uvicorn api.main:app --reload --port 8000
```

**Tests:** `tests/test_api.py`
- `test_health_endpoint` — GET /health returns 200 and `{"status": "ok"}`
- `test_chat_missing_question` — POST /chat with empty body returns 422
- (No Claude API call in tests — mock `anthropic.Anthropic`)

## app/src/ChatBox.jsx

**Purpose:** Glass-morphism chat panel fixed to the bottom-right of the globe.

**Layout:**
- `position: fixed`, `bottom: 24px`, `right: 24px`
- `width: 380px`, `height: 520px`
- `background: rgba(15, 15, 25, 0.85)`, `backdropFilter: blur(12px)`
- `border: 1px solid rgba(255, 255, 255, 0.1)`, `borderRadius: 16px`
- `boxShadow: 0 8px 32px rgba(0, 0, 0, 0.4)`
- Font: `system-ui`, size 13px, color `#e2e8f0`

**Header:** "WildfireRAG" label left, fire emoji right. `borderBottom: 1px solid rgba(255,255,255,0.08)`, padding 12px 16px.

**Messages area:** scrollable, flex-column, gap 8px, padding 12px.
- User messages: right-aligned, `background: rgba(239,68,68,0.2)`, `border: 1px solid rgba(239,68,68,0.3)`, `borderRadius: 12px 12px 2px 12px`, max-width 80%.
- Assistant messages: left-aligned, `background: rgba(255,255,255,0.06)`, `borderRadius: 12px 12px 12px 2px`, max-width 80%.
- Typing indicator: three animated dots (`●●●`) shown while awaiting response, left-aligned, same style as assistant.

**Input area:** `borderTop: 1px solid rgba(255,255,255,0.08)`, padding 12px.
- Textarea: `background: rgba(255,255,255,0.08)`, `borderRadius: 8px`, `color: #e2e8f0`, `border: 1px solid rgba(255,255,255,0.12)`, resize none, 2 rows.
- Send button: `background: #ef4444`, `color: white`, `borderRadius: 8px`, padding 8px 14px. Disabled while loading.
- Enter sends; Shift+Enter inserts newline.

**State:** `messages` array `[{role, content}]`, `loading` bool, `error` string|null.

**API call:** `POST http://localhost:8000/chat` with `{question, history: messages.slice(-6)}`. On error, set `error` state and show inline below input in `#ef4444`.

**Welcome message:** On mount, pre-populate messages with one assistant message:
> "Ask me about wildfire patterns — try 'Why is fire risk high in Northern California?' or 'What months are most dangerous in Texas?'"

## App.jsx changes

Add `<ChatBox />` as a sibling to `<GlobeMap mapboxToken={mapboxToken} />` inside the existing top-level div. No layout changes to the globe. `ChatBox` needs no props.

## Environment & Dependencies

**Root `.env`** (gitignored):
```
FIRMS_MAP_KEY=...
ANTHROPIC_API_KEY=sk-ant-...
```

**Root `.env.example`** (committed):
```
FIRMS_MAP_KEY=your_key_here
ANTHROPIC_API_KEY=your_anthropic_key_here
```

**`requirements.txt` additions:**
```
fastapi==0.115.0
uvicorn==0.30.6
anthropic==0.40.0
chromadb==0.5.23
sentence-transformers==3.3.1
langchain-community==0.3.8
```

**`.gitignore` addition:**
```
rag/chroma_db/
```

## Out of Scope

- Streaming responses (responses returned as complete JSON, not SSE)
- Authentication on the API
- Deployment (Phase 5)
- Mobile layout for the chatbox
- Map-click context (clicking a fire dot does not pre-populate the chat)
