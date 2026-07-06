"""Tests for task CRUD routes."""

import pytest
from fastapi.testclient import TestClient

from server.app import create_app


@pytest.fixture
def client():
    app = create_app()
    with TestClient(app) as c:
        yield c


class TestTaskRoutes:
    def test_list_tasks_empty(self, client):
        resp = client.get("/api/tasks")
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "total" in data

    def test_create_task(self, client):
        resp = client.post("/api/tasks", json={
            "name": "Test Task",
            "type": "keyword",
            "keywords": "AI,GPT",
            "schedule": "0 9 * * *",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "Test Task"
        assert data["id"] > 0

    def test_get_task_not_found(self, client):
        resp = client.get("/api/tasks/99999")
        assert resp.status_code == 404

    def test_get_task(self, client):
        created = client.post("/api/tasks", json={
            "name": "Get Me", "type": "user", "users": "elonmusk", "schedule": "0 9 * * *",
        }).json()
        resp = client.get(f"/api/tasks/{created['id']}")
        assert resp.status_code == 200
        assert resp.json()["name"] == "Get Me"

    def test_update_task(self, client):
        created = client.post("/api/tasks", json={
            "name": "Old", "type": "keyword", "keywords": "a", "schedule": "0 9 * * *",
        }).json()
        resp = client.put(f"/api/tasks/{created['id']}", json={"name": "New"})
        assert resp.status_code == 200
        assert resp.json()["name"] == "New"

    def test_delete_task(self, client):
        created = client.post("/api/tasks", json={
            "name": "Del", "type": "keyword", "keywords": "a", "schedule": "0 9 * * *",
        }).json()
        resp = client.delete(f"/api/tasks/{created['id']}")
        assert resp.status_code == 200
        assert client.get(f"/api/tasks/{created['id']}").status_code == 404

    def test_toggle_task(self, client):
        created = client.post("/api/tasks", json={
            "name": "Tog", "type": "keyword", "keywords": "a", "schedule": "0 9 * * *",
        }).json()
        assert created["enabled"] == 1
        resp = client.post(f"/api/tasks/{created['id']}/toggle")
        assert resp.json()["enabled"] == 0
        resp = client.post(f"/api/tasks/{created['id']}/toggle")
        assert resp.json()["enabled"] == 1

    def test_create_validation(self, client):
        resp = client.post("/api/tasks", json={"name": "", "type": "invalid", "schedule": ""})
        assert resp.status_code == 422

    def test_trigger_run(self, client):
        created = client.post("/api/tasks", json={
            "name": "Run", "type": "keyword", "keywords": "AI", "schedule": "0 9 * * *",
        }).json()
        resp = client.post(f"/api/tasks/{created['id']}/run")
        assert resp.status_code == 200
        data = resp.json()
        assert "tweets" in data
