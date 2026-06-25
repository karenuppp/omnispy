"""Tests for the FastAPI /query endpoint.

Replaces `omnispy.agents.router.run` with a stub so the test doesn't need
a running Ollama instance.
"""

from fastapi.testclient import TestClient

from omnispy.api import app
from omnispy import api as api_module


def _client_with_run(monkeypatch, stub):
    monkeypatch.setattr(api_module, "run", stub)
    return TestClient(app)


def test_query_endpoint_returns_answer(monkeypatch):
    def stub(q):
        return f"echo: {q}"

    client = _client_with_run(monkeypatch, stub)
    resp = client.post("/query", json={"q": "抓 @elonmusk 最近 5 条推文"})

    assert resp.status_code == 200
    assert resp.json() == {"answer": "echo: 抓 @elonmusk 最近 5 条推文"}


def test_query_endpoint_rejects_missing_field():
    client = TestClient(app)
    resp = client.post("/query", json={})
    assert resp.status_code == 422


def test_query_endpoint_rejects_wrong_type():
    client = TestClient(app)
    resp = client.post("/query", json={"q": 123})
    assert resp.status_code == 422


def test_healthz():
    client = TestClient(app)
    resp = client.get("/healthz")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}