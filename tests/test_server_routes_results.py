"""Tests for results routes."""

import pytest
from fastapi.testclient import TestClient

from server.app import create_app


@pytest.fixture
def client():
    app = create_app()
    with TestClient(app) as c:
        yield c


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

    def test_list_run_tweets(self, client):
        resp = client.get("/api/runs/99999/tweets")
        assert resp.status_code == 200
        assert "items" in resp.json()

    def test_list_task_tweets_not_found(self, client):
        resp = client.get("/api/tasks/99999/tweets")
        assert resp.status_code == 404
