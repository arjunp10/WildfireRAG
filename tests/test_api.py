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
