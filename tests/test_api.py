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


def test_chat_strips_leading_assistant_history():
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text="Answer here.")]

    with patch("rag.retriever.query_similar", return_value=["doc1"]), \
         patch("anthropic.Anthropic") as mock_anthropic:
        mock_anthropic.return_value.messages.create.return_value = mock_response
        client = _get_client()
        resp = client.post("/chat", json={
            "question": "What causes fires?",
            "history": [{"role": "assistant", "content": "Welcome message here"}]
        })
        assert resp.status_code == 200
        # Verify Claude was called with no leading assistant turn
        call_args = mock_anthropic.return_value.messages.create.call_args
        called_messages = call_args[1]["messages"]
        assert called_messages[0]["role"] == "user"


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
