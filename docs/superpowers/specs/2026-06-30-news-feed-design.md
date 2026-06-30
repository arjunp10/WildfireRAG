# WildfireRAG Phase 5 Design — News Feed

**Date:** 2026-06-30
**Status:** Approved

## Overview

Phase 5 adds a wildfire news feed to FireRAG. Articles are fetched from News API (newsapi.org), stored in SQLite, embedded into a dedicated ChromaDB collection, and displayed in a glass-morphism left panel on the globe dashboard. The RAG chatbox is updated to retrieve from both historical fire data and current news articles, so Claude can synthesize answers that combine historical patterns with breaking news.

## Architecture

```
newsapi.org
    ↓ data/news.py (fetch daily)
articles table (SQLite, deduped by URL)
    ↓ rag/build_news_index.py (run after fetch)
"wildfire-news" ChromaDB collection
    ↓
api/main.py /chat — queries both collections:
    top-3 from "wildfire-regions" (historical)
  + top-2 from "wildfire-news" (current articles)
    → Claude synthesizes combined answer

api/main.py GET /news → latest 15 articles from SQLite
    ↓
app/src/NewsPanel.jsx — fixed left panel, overlays globe
```

## File Structure

```
data/
└── news.py                      # News API fetcher (new)
rag/
└── build_news_index.py          # articles → ChromaDB (new)
app/src/
└── NewsPanel.jsx                # left panel UI (new)
data/db.py                       # modified: add articles table
rag/retriever.py                 # modified: add query_news()
api/main.py                      # modified: GET /news, /chat dual retrieval
app/src/App.jsx                  # modified: add <NewsPanel />
.env.example                     # modified: add NEWS_API_KEY
```

## articles Table

Added to `firerag.db` via migration in `data/db.py`:

```sql
CREATE TABLE IF NOT EXISTS articles (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    title        TEXT NOT NULL,
    description  TEXT,
    url          TEXT NOT NULL UNIQUE,
    source       TEXT,
    published_at TEXT,
    fetched_at   TEXT
)
```

Deduplication is enforced by the `UNIQUE` constraint on `url`. Inserts use `INSERT OR IGNORE`.

## data/news.py

**Purpose:** Fetch wildfire news from News API and store in SQLite.

**Interface:**
```python
def fetch_articles(db_path: str, api_key: str, hours: int = 48) -> int:
    """Fetch wildfire articles from last `hours` hours. Returns count of new articles inserted."""
```

**News API call:**
```
GET https://newsapi.org/v2/everything
  ?q=wildfire OR "forest fire"
  &language=en
  &sortBy=publishedAt
  &from=<ISO datetime, now - hours>
  &pageSize=100
  &apiKey=<api_key>
```

**Insert pattern:** `INSERT OR IGNORE INTO articles (title, description, url, source, published_at, fetched_at) VALUES (?, ?, ?, ?, ?, ?)`

**CLI:**
```bash
python3 data/news.py [--db firerag.db] [--hours 48]
```
Prints: `Fetched N new articles.`

**Environment:** `NEWS_API_KEY` loaded from root `.env` via `python-dotenv`.

**Error handling:** If the API returns a non-200 status or `status: "error"`, raise `RuntimeError` with the API's `message` field.

**Tests:** `tests/test_news.py`
- `test_returns_count` — returns integer >= 0
- `test_deduplication` — calling twice with same mock response inserts 0 new articles on second call
- `test_inserts_fields` — spot-check title, url, source are stored correctly
- (mock `requests.get` — no real API calls in tests)

## rag/build_news_index.py

**Purpose:** Embed all articles from SQLite into ChromaDB collection `"wildfire-news"`.

**Document format** (one per article):
```
[SOURCE] TITLE. DESCRIPTION. Published: PUBLISHED_AT.
```
Example:
```
[Reuters] California wildfire forces 10,000 to evacuate. Fast-moving blaze near Sacramento grows to 5,000 acres. Published: 2026-06-30T14:23:00Z.
```

**ChromaDB:** persistent client at same `rag/chroma_db/` directory. Collection name: `"wildfire-news"`. Delete and recreate on each run (idempotent). Same `all-MiniLM-L6-v2` embedding model via `SentenceTransformerEmbeddingFunction`.

**CLI:**
```bash
python3 -m rag.build_news_index [--db firerag.db] [--chroma-dir rag/chroma_db]
```
Prints: `Indexed N news articles.`

**Tests:** `tests/test_build_news_index.py`
- `test_returns_count` — returns integer >= 1
- `test_collection_has_documents` — ChromaDB count matches return value
- `test_document_format` — spot-check one doc contains source in brackets and "Published:"
- `test_idempotent` — calling twice produces same count

## rag/retriever.py — additions

Add alongside existing `query_similar`:

```python
_NEWS_COLLECTION = "wildfire-news"
_news_clients: dict[str, chromadb.PersistentClient] = {}

def query_news(question: str, chroma_dir: str, k: int = 2) -> list[str]:
    """Return top-k news article texts most similar to question."""
```

Same caching pattern as `query_similar` — module-level embedding function, dict-cached client per `chroma_dir`.

**Tests:** `tests/test_retriever.py` — add:
- `test_query_news_returns_list` — fixture with 3 news docs, returns list
- `test_query_news_returns_k_results` — returns exactly k results

## api/main.py — additions

**`GET /news`**
```python
class ArticleOut(BaseModel):
    title: str
    description: str | None
    url: str
    source: str | None
    published_at: str | None

@app.get("/news", response_model=list[ArticleOut])
def get_news():
    """Return latest 15 articles ordered by published_at DESC."""
```
Reads from `firerag.db` (path `DB_PATH = os.environ.get("DB_PATH", "firerag.db")`). Returns empty list if table doesn't exist yet.

**`POST /chat` update**

Replace single-collection retrieval with dual retrieval:
```python
historical_docs = query_similar(req.question, CHROMA_DIR, k=3)
news_docs = query_news(req.question, CHROMA_DIR, k=2)

context_parts = []
for doc in historical_docs:
    context_parts.append(f"[HISTORICAL] {doc}")
for doc in news_docs:
    context_parts.append(f"[NEWS] {doc}")
context = "\n".join(f"- {part}" for part in context_parts)
```

If `query_news` fails (collection doesn't exist yet — user hasn't run `build_news_index`), catch the exception and proceed with historical-only context. Do not return 500.

**Updated system prompt** — change the context description line to:
```
Relevant data (historical fire records and recent news):
```

## app/src/NewsPanel.jsx

**Purpose:** Fixed left panel showing latest wildfire news articles.

**Layout:**
- `position: fixed`, `left: 0`, `top: 0`, `width: 300px`, `height: 100vh`
- `background: rgba(15,15,25,0.85)`, `backdropFilter: blur(12px)`
- `border-right: 1px solid rgba(255,255,255,0.1)`
- `display: flex`, `flex-direction: column`
- `zIndex: 1000`, `fontFamily: system-ui`, `color: #e2e8f0`

**Header:**
- `padding: 16px`, `borderBottom: 1px solid rgba(255,255,255,0.08)`
- "Live News" left, 📰 right, `fontWeight: 600`

**Articles list:**
- `flex: 1`, `overflowY: auto`, `padding: 8px`
- Each card: `padding: 12px`, `marginBottom: 4px`, `borderRadius: 8px`, `cursor: pointer`
- Hover: `background: rgba(255,255,255,0.06)`
- Source chip: `background: rgba(239,68,68,0.2)`, `border: 1px solid rgba(239,68,68,0.3)`, `borderRadius: 4px`, `padding: 2px 6px`, `fontSize: 10px`, `color: #fca5a5`
- Headline: `fontSize: 13px`, `fontWeight: 600`, `lineHeight: 1.4`, max 2 lines (`overflow: hidden`, `display: -webkit-box`, `-webkit-line-clamp: 2`, `-webkit-box-orient: vertical`)
- Snippet: `fontSize: 11px`, `color: #94a3b8`, `marginTop: 4px`, max 3 lines (same clamp pattern)
- Time: relative format ("2h ago", "just now") using `published_at`, `fontSize: 10px`, `color: #64748b`, `marginTop: 4px`

**State:** `articles` array, `loading` bool, `error` string|null

**Data fetch:** `GET http://localhost:8000/news` on mount. On error, show inline message: "Could not load news."

**Click:** `window.open(article.url, '_blank', 'noopener,noreferrer')`

**Loading state:** 5 skeleton cards — grey animated placeholders while fetching.

**No props required.**

## app/src/App.jsx changes

Add `<NewsPanel />` as a sibling to `<GlobeMap>` and `<ChatBox>` inside the React Fragment. No layout changes to globe or chatbox — NewsPanel overlays the left edge.

```jsx
return (
  <>
    <GlobeMap mapboxToken={token} />
    <NewsPanel />
    <ChatBox />
  </>
)
```

## Environment & Dependencies

**Root `.env.example` addition:**
```
NEWS_API_KEY=your_newsapi_key_here
```

**No new Python packages** — uses `requests` (already in requirements.txt).

**No new npm packages** — uses built-in `fetch`.

## Workflow

```bash
# Fetch articles (run daily)
python3 data/news.py

# Re-embed after fetch
python3 -m rag.build_news_index

# Start API + frontend as before
uvicorn api.main:app --reload --port 8000
cd app && npm run dev
```

## Out of Scope

- Scheduled automatic fetch (cron job / background task)
- Article full-text scraping (headline + description only)
- Filtering news by geographic region
- Marking articles as read
- Push notifications for breaking news
