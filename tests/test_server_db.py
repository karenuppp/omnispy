"""Tests for server config and database layer."""

from pathlib import Path

import pytest

from server.config import ServerSettings
from server.db import Database


def test_server_config_defaults():
    settings = ServerSettings()
    assert settings.db_path == "omnispy.db"


@pytest.fixture
def db(tmp_path: Path) -> Database:
    _db = Database(str(tmp_path / "test.db"))
    _db.connect()
    yield _db
    _db.close()


class TestTaskCRUD:
    def test_create_and_get(self, db):
        task = db.create_task({
            "name": "测试任务",
            "type": "keyword",
            "keywords": "AI,GPT",
            "schedule": "0 9 * * *",
        })
        assert task["id"] > 0
        assert task["name"] == "测试任务"
        got = db.get_task(task["id"])
        assert got["name"] == "测试任务"

    def test_list_tasks(self, db):
        db.create_task({"name": "A", "type": "keyword", "keywords": "a", "schedule": "0 9 * * *"})
        db.create_task({"name": "B", "type": "user", "users": "user1", "schedule": "0 9 * * *"})
        tasks, total = db.list_tasks()
        assert total >= 2
        assert len(tasks) >= 2

    def test_list_tasks_pagination(self, db):
        for i in range(5):
            db.create_task({"name": f"T{i}", "type": "keyword", "keywords": "x", "schedule": "0 9 * * *"})
        page1, total = db.list_tasks(page=1, size=2)
        assert len(page1) == 2
        assert total == 5

    def test_update_task(self, db):
        task = db.create_task({"name": "Old", "type": "keyword", "keywords": "a", "schedule": "0 9 * * *"})
        updated = db.update_task(task["id"], {"name": "New"})
        assert updated["name"] == "New"

    def test_toggle_task(self, db):
        task = db.create_task({"name": "T", "type": "keyword", "keywords": "a", "schedule": "0 9 * * *"})
        assert task["enabled"] == 1
        toggled = db.toggle_task(task["id"])
        assert toggled["enabled"] == 0
        toggled_again = db.toggle_task(task["id"])
        assert toggled_again["enabled"] == 1

    def test_delete_task(self, db):
        task = db.create_task({"name": "Del", "type": "keyword", "keywords": "a", "schedule": "0 9 * * *"})
        assert db.delete_task(task["id"])
        assert db.get_task(task["id"]) is None

    def test_delete_non_existent(self, db):
        assert not db.delete_task(99999)


class TestRunCRUD:
    def test_create_finish_list(self, db):
        task = db.create_task({"name": "R", "type": "keyword", "keywords": "a", "schedule": "0 9 * * *"})
        run_id = db.create_run(task["id"])
        assert run_id > 0
        db.finish_run(run_id, "success")
        runs, total = db.list_runs(task["id"])
        assert total == 1
        assert runs[0]["status"] == "success"
        assert runs[0]["finished_at"] is not None


class TestTweetsCRUD:
    def test_insert_and_list_by_run(self, db):
        task = db.create_task({"name": "Tw", "type": "keyword", "keywords": "a", "schedule": "0 9 * * *"})
        run_id = db.create_run(task["id"])
        db.insert_tweets([
            {"id": "123", "text": "hello", "author": "user1", "time": "2026-07-04T10:00:00Z", "url": "https://x.com/i/status/123"},
            {"id": "456", "text": "world", "author": "user2", "time": "2026-07-04T11:00:00Z", "url": "https://x.com/i/status/456"},
        ], run_id, task["id"])
        tweets, total = db.list_tweets_by_run(run_id)
        assert total == 2
        assert tweets[0]["text"] == "world"  # sorted by time DESC

    def test_duplicate_tweet_id_same_task(self, db):
        task = db.create_task({"name": "Dup", "type": "keyword", "keywords": "a", "schedule": "0 9 * * *"})
        run1 = db.create_run(task["id"])
        run2 = db.create_run(task["id"])
        db.insert_tweets([{"id": "123", "text": "first", "author": "u", "time": "2026-01-01T00:00:00Z", "url": ""}], run1, task["id"])
        db.insert_tweets([{"id": "123", "text": "second", "author": "u", "time": "2026-01-01T00:00:00Z", "url": ""}], run2, task["id"])
        tweets, total = db.list_tweets_by_run(run1)
        assert total == 1  # first insert wins
        tweets, total = db.list_tweets_by_run(run2)
        assert total == 0  # duplicate ignored

    def test_list_tweets_by_task(self, db):
        task = db.create_task({"name": "BT", "type": "keyword", "keywords": "a", "schedule": "0 9 * * *"})
        run1 = db.create_run(task["id"])
        run2 = db.create_run(task["id"])
        db.insert_tweets([{"id": "1", "text": "a", "author": "u", "time": "2026-07-04T10:00:00Z", "url": ""}], run1, task["id"])
        db.insert_tweets([{"id": "2", "text": "b", "author": "u", "time": "2026-07-04T11:00:00Z", "url": ""}], run2, task["id"])
        tweets, total = db.list_tweets_by_task(task["id"])
        assert total == 2


class TestSearchLog:
    def test_log_and_stats(self, db):
        db.log_search("keyword", "AI,GPT", "", 10)
        db.log_search("user", "", "elonmusk", 3)
        stats = db.get_stats()
        assert stats["total_tasks"] >= 0  # just ensures it runs
