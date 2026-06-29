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
