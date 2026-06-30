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
