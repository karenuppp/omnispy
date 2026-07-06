"""Tests for search and results routes."""

import pytest
from fastapi.testclient import TestClient

from server.app import create_app


@pytest.fixture
def client():
    app = create_app()
    with TestClient(app) as c:
        yield c


class TestSearchRoute:
    def test_manual_search_keyword(self, client):
        resp = client.post("/api/search", json={
            "type": "keyword", "keywords": "AI", "limit": 5,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "tweets" in data
        assert "count" in data

    def test_manual_search_user(self, client):
        resp = client.post("/api/search", json={
            "type": "user", "users": "elonmusk", "limit": 1,
        })
        assert resp.status_code == 200

    def test_manual_search_validation(self, client):
        resp = client.post("/api/search", json={"type": "invalid"})
        assert resp.status_code == 422

    def test_manual_search_no_params(self, client):
        resp = client.post("/api/search", json={"type": "keyword", "keywords": "", "users": ""})
        assert resp.status_code == 200
        assert resp.json()["count"] == 0


class TestResultsRoutes:
    def test_stats(self, client):
        resp = client.get("/api/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert "total_tasks" in data

    def test_list_runs_not_found(self, client):
        resp = client.get("/api/tasks/99999/runs")
        assert resp.status_code == 404

    def test_list_runs_empty(self, client):
        task = client.post("/api/tasks", json={
            "name": "R", "type": "keyword", "keywords": "a", "schedule": "0 9 * * *",
        }).json()
        resp = client.get(f"/api/tasks/{task['id']}/runs")
        assert resp.status_code == 200
        assert resp.json()["total"] == 0

    def test_list_run_tweets_not_found(self, client):
        resp = client.get("/api/runs/99999/tweets")
        assert resp.status_code == 200

    def test_list_task_tweets_not_found(self, client):
        resp = client.get("/api/tasks/99999/tweets")
        assert resp.status_code == 404
