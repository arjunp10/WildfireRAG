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
