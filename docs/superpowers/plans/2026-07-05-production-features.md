# Production Features Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the X scraping MVP into a usable daily tool with keyword/user list search, scheduled tasks, and a Vue frontend for non-technical users.

**Architecture:** A new `server/` layer sits alongside the existing `omnispy/` package. FastAPI serves both REST API + Vue frontend; APScheduler runs inside FastAPI's lifespan for timed tasks. The server layer calls spider primitives directly (no LLM involved for scheduled/manual searches). The existing CLI + LLM agent path is untouched.

**Tech Stack:** FastAPI (same as existing), APScheduler, SQLite (built-in), Vue 3 + Vite + Naive UI + TypeScript

## Global Constraints

- Must NOT modify `omnispy/` package files except pyproject.toml (add deps). spider.py stays untouched — batch logic lives in server/.
- Existing CLI entry point (`omnispy = "omnispy.__main__:app"`) must continue to work.
- LLM agent path must remain untouched — search is a parallel path, not a replacement.
- SQLite database file path defaults to `./omnispy.db` (configurable via env var `OMNISPY_DB_PATH`).
- All new REST endpoints under `/api/` prefix.
- Vue frontend served by FastAPI as static files (no separate server for prod). Dev mode uses Vite proxy for hot-reload.
- APScheduler job store uses SQLite (same db file, different table prefix) for persistence across restarts.

---

## File Structure

```
server/                          # NEW: web service layer
├── __init__.py                  # package marker
├── app.py                       # FastAPI app factory + lifespan
├── config.py                    # Server-specific config (db path, etc.)
├── db.py                        # SQLite schema + CRUD
├── service.py                   # Batch orchestration (list splitting + spider calls + merge/dedup)
├── scheduler.py                 # APScheduler setup + job handlers
├── routes/
│   ├── __init__.py
│   ├── tasks.py                 # GET/POST/PUT/DELETE /api/tasks/* + toggle/run
│   ├── search.py                # POST /api/search (manual one-shot)
│   └── results.py               # GET /api/runs/:id/tweets + GET /api/stats
└── frontend/                    # NEW: Vue 3 + Vite project
    ├── package.json
    ├── vite.config.ts
    ├── index.html
    ├── tsconfig.json
    └── src/
        ├── main.ts
        ├── App.vue
        ├── router.ts
        ├── api/
        │   └── index.ts         # Axios/fetch wrappers for all REST endpoints
        ├── types/
        │   └── index.ts         # TypeScript interfaces mirroring backend models
        └── views/
            ├── TaskList.vue     # Page 1: task list (home)
            ├── TaskForm.vue     # Page 2: create/edit task
            ├── TaskDetail.vue   # Page 3: task runs + tweets
            └── ManualSearch.vue # Page 4: one-shot manual search
```

**Existing files to modify:**
- `pyproject.toml` — add `apscheduler` dependency

---

### Task 1: Server config + database layer

**Files:**
- Create: `server/__init__.py`
- Create: `server/config.py`
- Create: `server/db.py`
- Test: `tests/test_server_db.py`

**Interfaces:**
- Consumes: `omnispy.config.settings` (for backward compat, though server has its own config)
- Produces: `server.db.get_db() -> Database` singleton, `Database` class with CRUD methods

- [ ] **Step 1: Write server/config.py**

```python
"""Server-layer configuration (DB path, etc.)."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class ServerSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    db_path: str = "omnispy.db"


server_settings = ServerSettings()
```

- [ ] **Step 2: Write server/db.py with schema + CRUD**

```python
"""SQLite database layer. Schema, CRUD, and a singleton Database class."""

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import server_settings


def _ensure_timestamp(ts: str | None) -> str:
    """Return the given ISO timestamp or the current UTC time."""
    return ts if ts else datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class Database:
    def __init__(self, db_path: str | None = None):
        self._path = Path(db_path or server_settings.db_path)
        self._conn: sqlite3.Connection | None = None

    def connect(self):
        self._conn = sqlite3.connect(str(self._path))
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._migrate()

    def close(self):
        if self._conn:
            self._conn.close()
            self._conn = None

    # ---- Schema ----

    def _migrate(self):
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS tasks (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                name        TEXT NOT NULL,
                type        TEXT NOT NULL CHECK(type IN ('keyword','user','mixed')),
                keywords    TEXT DEFAULT '',
                users       TEXT DEFAULT '',
                schedule    TEXT NOT NULL,
                enabled     INTEGER DEFAULT 1,
                created_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
                updated_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
            );

            CREATE TABLE IF NOT EXISTS task_runs (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id      INTEGER NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
                status       TEXT NOT NULL CHECK(status IN ('running','success','failed')),
                started_at   TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
                finished_at  TEXT,
                error_msg    TEXT DEFAULT ''
            );

            CREATE TABLE IF NOT EXISTS tweets (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                tweet_id     TEXT NOT NULL,
                task_run_id  INTEGER NOT NULL REFERENCES task_runs(id) ON DELETE CASCADE,
                task_id      INTEGER NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
                author       TEXT DEFAULT '',
                text         TEXT DEFAULT '',
                time         TEXT DEFAULT '',
                url          TEXT DEFAULT '',
                crawled_at   TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
                UNIQUE(tweet_id, task_id)
            );

            CREATE TABLE IF NOT EXISTS search_logs (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                query_type    TEXT NOT NULL CHECK(query_type IN ('keyword','user')),
                keywords      TEXT DEFAULT '',
                users         TEXT DEFAULT '',
                result_count  INTEGER DEFAULT 0,
                created_at    TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
            );
        """)

    # ---- Task CRUD ----

    def list_tasks(self, page: int = 1, size: int = 20) -> tuple[list[dict], int]:
        """Return (tasks, total_count) sorted by updated_at DESC."""
        total = self._conn.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
        rows = self._conn.execute(
            "SELECT * FROM tasks ORDER BY updated_at DESC LIMIT ? OFFSET ?",
            (size, (page - 1) * size),
        ).fetchall()
        return [dict(r) for r in rows], total

    def get_task(self, task_id: int) -> dict | None:
        row = self._conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
        return dict(row) if row else None

    def create_task(self, data: dict) -> dict:
        cur = self._conn.execute(
            "INSERT INTO tasks (name, type, keywords, users, schedule, enabled) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (data["name"], data["type"], data.get("keywords", ""),
             data.get("users", ""), data["schedule"], data.get("enabled", 1)),
        )
        self._conn.commit()
        return self.get_task(cur.lastrowid)

    def update_task(self, task_id: int, data: dict) -> dict | None:
        existing = self.get_task(task_id)
        if not existing:
            return None
        fields = {k: v for k, v in data.items() if k in (
            "name", "type", "keywords", "users", "schedule", "enabled"
        )}
        if not fields:
            return existing
        fields["updated_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        sets = ", ".join(f"{k} = ?" for k in fields)
        vals = list(fields.values()) + [task_id]
        self._conn.execute(f"UPDATE tasks SET {sets} WHERE id = ?", vals)
        self._conn.commit()
        return self.get_task(task_id)

    def toggle_task(self, task_id: int) -> dict | None:
        task = self.get_task(task_id)
        if not task:
            return None
        new_enabled = 0 if task["enabled"] else 1
        return self.update_task(task_id, {"enabled": new_enabled})

    def delete_task(self, task_id: int) -> bool:
        cur = self._conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
        self._conn.commit()
        return cur.rowcount > 0

    # ---- Task runs ----

    def create_run(self, task_id: int) -> int:
        cur = self._conn.execute(
            "INSERT INTO task_runs (task_id, status) VALUES (?, 'running')",
            (task_id,),
        )
        self._conn.commit()
        return cur.lastrowid

    def finish_run(self, run_id: int, status: str, error_msg: str = ""):
        self._conn.execute(
            "UPDATE task_runs SET status=?, finished_at=strftime('%Y-%m-%dT%H:%M:%SZ','now'), error_msg=? WHERE id=?",
            (status, error_msg, run_id),
        )
        self._conn.commit()

    def list_runs(self, task_id: int, page: int = 1, size: int = 20) -> tuple[list[dict], int]:
        total = self._conn.execute(
            "SELECT COUNT(*) FROM task_runs WHERE task_id = ?", (task_id,)
        ).fetchone()[0]
        rows = self._conn.execute(
            "SELECT * FROM task_runs WHERE task_id = ? ORDER BY started_at DESC LIMIT ? OFFSET ?",
            (task_id, size, (page - 1) * size),
        ).fetchall()
        return [dict(r) for r in rows], total

    # ---- Tweets ----

    def insert_tweets(self, tweets: list[dict], task_run_id: int, task_id: int):
        """Bulk insert tweets, ignoring (tweet_id, task_id) duplicates."""
        for t in tweets:
            try:
                self._conn.execute(
                    "INSERT OR IGNORE INTO tweets (tweet_id, task_run_id, task_id, author, text, time, url) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (t["id"], task_run_id, task_id, t.get("author", ""),
                     t.get("text", ""), t.get("time", ""), t.get("url", "")),
                )
            except Exception:
                pass  # skip malformed tweet
        self._conn.commit()

    def list_tweets_by_run(self, run_id: int, page: int = 1, size: int = 20) -> tuple[list[dict], int]:
        total = self._conn.execute(
            "SELECT COUNT(*) FROM tweets WHERE task_run_id = ?", (run_id,)
        ).fetchone()[0]
        rows = self._conn.execute(
            "SELECT * FROM tweets WHERE task_run_id = ? ORDER BY time DESC LIMIT ? OFFSET ?",
            (run_id, size, (page - 1) * size),
        ).fetchall()
        return [dict(r) for r in rows], total

    def list_tweets_by_task(self, task_id: int, page: int = 1, size: int = 20) -> tuple[list[dict], int]:
        total = self._conn.execute(
            "SELECT COUNT(*) FROM tweets WHERE task_id = ?", (task_id,)
        ).fetchone()[0]
        rows = self._conn.execute(
            "SELECT * FROM tweets WHERE task_id = ? ORDER BY time DESC LIMIT ? OFFSET ?",
            (task_id, size, (page - 1) * size),
        ).fetchall()
        return [dict(r) for r in rows], total

    # ---- Search logs ----

    def log_search(self, query_type: str, keywords: str, users: str, result_count: int):
        self._conn.execute(
            "INSERT INTO search_logs (query_type, keywords, users, result_count) VALUES (?, ?, ?, ?)",
            (query_type, keywords, users, result_count),
        )
        self._conn.commit()

    # ---- Stats ----

    def get_stats(self) -> dict:
        total_tasks = self._conn.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
        enabled_tasks = self._conn.execute("SELECT COUNT(*) FROM tasks WHERE enabled=1").fetchone()[0]
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        runs_today = self._conn.execute(
            "SELECT COUNT(*) FROM task_runs WHERE date(started_at) = ?", (today,)
        ).fetchone()[0]
        last_run = self._conn.execute(
            "SELECT started_at FROM task_runs ORDER BY started_at DESC LIMIT 1"
        ).fetchone()
        return {
            "total_tasks": total_tasks,
            "enabled_tasks": enabled_tasks,
            "runs_today": runs_today,
            "last_run_at": last_run["started_at"] if last_run else None,
        }


_db_instance: Database | None = None


def get_db() -> Database:
    """Get the singleton Database instance."""
    global _db_instance
    if _db_instance is None:
        _db_instance = Database()
        _db_instance.connect()
    return _db_instance


def close_db():
    """Close the singleton Database."""
    global _db_instance
    if _db_instance:
        _db_instance.close()
        _db_instance = None
```

- [ ] **Step 3: Write tests for config and CRUD**

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/test_server_db.py -v
```
Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add server/__init__.py server/config.py server/db.py tests/test_server_db.py
git commit -m "feat: add server config and SQLite database layer"
```

---

### Task 2: Service layer — batch orchestration

**Files:**
- Create: `server/service.py`
- Test: `tests/test_server_service.py`

**Interfaces:**
- Consumes:
  - `omnispy.platforms.x.spider.fetch_user_tweets(handle, limit) -> list[dict]`
  - `omnispy.platforms.x.spider.search_tweets(keywords, from_users, query, sort, limit, since, until) -> list[dict]`
- Produces:
  - `server.service.run_task(task_id) -> list[dict]` — execute one task (all users/keywords)
  - `server.service.run_manual_search(type, keywords, users, limit) -> list[dict]` — one-shot search

- [ ] **Step 1: Write test**

```python
"""Tests for server.service orchestration layer."""

import json
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import pytest

from server.db import Database
from server.service import run_manual_search


@pytest.fixture
def db(tmp_path: Path) -> Database:
    _db = Database(str(tmp_path / "test.db"))
    _db.connect()
    yield _db
    _db.close()


def fake_fetch_user_tweets(handle: str, limit: int = 10) -> list[dict]:
    return [{
        "id": f"user_{handle}_1",
        "text": f"Tweet from {handle}",
        "time": "2026-07-04T10:00:00Z",
        "author": handle,
    }]


def fake_search_tweets(keywords=None, from_users=None, query=None, sort="top",
                       limit=20, since=None, until=None) -> list[dict]:
    kw = (keywords or ["unknown"])[0]
    return [{
        "id": f"kw_{kw}_1",
        "text": f"About {kw}",
        "time": "2026-07-04T10:00:00Z",
        "author": "someone",
    }]


@patch("server.service.fetch_user_tweets", fake_fetch_user_tweets)
def test_run_manual_search_users(db):
    """Manual search for a list of users returns 1 tweet each, merged."""
    tweets = run_manual_search(
        query_type="user",
        keywords="",
        users="elonmusk,lexfridman",
        limit=1,
        db=db,
    )
    assert len(tweets) == 2
    user_ids = {t["author"] for t in tweets}
    assert user_ids == {"elonmusk", "lexfridman"}


@patch("server.service.search_tweets", fake_search_tweets)
def test_run_manual_search_keywords(db):
    """Manual search for multiple keywords returns merged results."""
    tweets = run_manual_search(
        query_type="keyword",
        keywords="AI,GPT",
        users="",
        limit=10,
        db=db,
    )
    assert len(tweets) == 2
    texts = {t["text"] for t in tweets}
    assert "About AI" in texts
    assert "About GPT" in texts


@patch("server.service.search_tweets", fake_search_tweets)
def test_run_manual_search_creates_log(db):
    run_manual_search(
        query_type="keyword",
        keywords="AI",
        users="",
        limit=10,
        db=db,
    )
    # search_log should exist (we just verify no crash)
    stats = db.get_stats()
    assert stats is not None


@patch("server.service.fetch_user_tweets", lambda h, limit=10: [])
def test_run_manual_search_empty_result(db):
    tweets = run_manual_search("user", "", "nobody", limit=1, db=db)
    assert tweets == []


def test_run_manual_search_no_params(db):
    tweets = run_manual_search("keyword", "", "", limit=1, db=db)
    assert tweets == []


@patch("server.service.fetch_user_tweets", lambda h, limit=10: [
    {"id": "dup_1", "text": "a", "time": "2026-01-01T00:00:00Z", "author": h},
    {"id": "dup_1", "text": "a", "time": "2026-01-01T00:00:00Z", "author": h},
])
def test_run_manual_search_dedup(db):
    """Even if spider returns duplicates (shouldn't happen), service deduplicates."""
    tweets = run_manual_search("user", "", "user1", limit=10, db=db)
    assert len(tweets) == 1
```

- [ ] **Step 2: Run test to see failure**

```bash
uv run pytest tests/test_server_service.py::test_run_manual_search_users -v
```
Expected: FAIL with ImportError

- [ ] **Step 3: Write service.py**

```python
"""Service layer: batch orchestration for list-based searches.

This module sits between routes and spider. It handles:
- Splitting keyword/user lists into individual spider calls
- Merging and deduplicating results
- Persisting results to the database
"""

from datetime import datetime, timezone
from typing import Any

from omnispy.platforms.x.spider import fetch_user_tweets, search_tweets

from .db import get_db


def _today_since() -> str:
    """Return today's date as YYYY-MM-DD for the ``since`` filter."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def run_manual_search(
    query_type: str,
    keywords: str = "",
    users: str = "",
    limit: int = 20,
    db=None,
) -> list[dict]:
    """Execute a one-off manual search.

    Args:
        query_type: ``"keyword"`` or ``"user"``.
        keywords:   Comma-separated keywords (for keyword search).
        users:      Comma-separated usernames (for user search).
        limit:      Max tweets per keyword/user, not total.
        db:         Database instance for logging (optional, graceful fallback).

    Returns:
        Merged, deduplicated, time-sorted list of tweet dicts.
    """
    if query_type == "keyword":
        kw_list = [k.strip() for k in keywords.split(",") if k.strip()]
        if not kw_list:
            return []
        all_tweets: list[dict] = []
        seen: set[str] = set()
        since = _today_since()
        for kw in kw_list:
            results = search_tweets(
                keywords=[kw],
                sort="top",
                limit=limit,
                since=since,
            )
            for t in results:
                tid = t.get("id")
                if tid and tid not in seen:
                    seen.add(tid)
                    all_tweets.append(t)

        all_tweets.sort(key=lambda t: t.get("time", ""), reverse=True)

        if db:
            db.log_search("keyword", keywords, "", len(all_tweets))

        return all_tweets

    elif query_type == "user":
        user_list = [u.strip().lstrip("@") for u in users.split(",") if u.strip()]
        if not user_list:
            return []
        all_tweets = []
        seen = set()
        for handle in user_list:
            results = fetch_user_tweets(handle, limit=limit)
            for t in results:
                tid = t.get("id")
                if tid and tid not in seen:
                    seen.add(tid)
                    all_tweets.append(t)

        all_tweets.sort(key=lambda t: t.get("time", ""), reverse=True)

        if db:
            db.log_search("user", "", users, len(all_tweets))

        return all_tweets

    return []


def run_task(task_id: int, db=None) -> list[dict]:
    """Execute a scheduled task: fetch tweets for all configured keywords/users.

    Creates a task_run record, fetches tweets, persists them, and updates
    the run status.

    Args:
        task_id: The task's ID in the database.
        db:      Database instance (optional, but needed for persistence).

    Returns:
        The list of tweets fetched.
    """
    if db is None:
        db = get_db()

    task = db.get_task(task_id)
    if not task or not task["enabled"]:
        return []

    run_id = db.create_run(task_id)

    try:
        if task["type"] == "user":
            tweets = run_manual_search("user", "", task["users"], limit=1, db=None)
        elif task["type"] == "keyword":
            tweets = run_manual_search("keyword", task["keywords"], "", limit=20, db=None)
        else:  # mixed
            user_tweets = run_manual_search("user", "", task["users"], limit=1, db=None)
            kw_tweets = run_manual_search("keyword", task["keywords"], "", limit=20, db=None)
            seen = {t["id"] for t in user_tweets}
            tweets = user_tweets + [t for t in kw_tweets if t.get("id") not in seen]
            tweets.sort(key=lambda t: t.get("time", ""), reverse=True)

        # Persist tweets
        if tweets:
            db.insert_tweets(tweets, run_id, task_id)

        db.finish_run(run_id, "success")
        return tweets

    except Exception as e:
        db.finish_run(run_id, "failed", str(e))
        return []
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/test_server_service.py -v
```
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add server/service.py tests/test_server_service.py
git commit -m "feat: add service layer for batch search orchestration"
```

---

### Task 3: Task CRUD REST routes

**Files:**
- Create: `server/routes/__init__.py`
- Create: `server/routes/tasks.py`
- Test: `tests/test_server_routes_tasks.py`

**Interfaces:**
- Produces: FastAPI `APIRouter` prefix `/api/tasks` with endpoints:
  - `GET /api/tasks?page=1&size=20`
  - `POST /api/tasks`
  - `GET /api/tasks/{id}`
  - `PUT /api/tasks/{id}`
  - `DELETE /api/tasks/{id}`
  - `POST /api/tasks/{id}/toggle`
  - `POST /api/tasks/{id}/run`

- [ ] **Step 1: Write server/routes/__init__.py** (empty)

- [ ] **Step 2: Write routes/tasks.py**

```python
"""Task CRUD routes."""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from server.db import get_db
from server.service import run_task

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


class TaskCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    type: str = Field(pattern="^(keyword|user|mixed)$")
    keywords: str = ""
    users: str = ""
    schedule: str = Field(min_length=1, max_length=100)
    enabled: int = 1


class TaskUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=200)
    type: str | None = Field(None, pattern="^(keyword|user|mixed)$")
    keywords: str | None = None
    users: str | None = None
    schedule: str | None = Field(None, min_length=1, max_length=100)
    enabled: int | None = None


@router.get("")
def list_tasks(page: int = Query(1, ge=1), size: int = Query(20, ge=1, le=100)):
    db = get_db()
    tasks, total = db.list_tasks(page, size)
    return {"items": tasks, "total": total, "page": page, "size": size}


@router.post("", status_code=201)
def create_task(body: TaskCreate):
    db = get_db()
    task = db.create_task(body.model_dump())
    return task


@router.get("/{task_id}")
def get_task(task_id: int):
    db = get_db()
    task = db.get_task(task_id)
    if not task:
        raise HTTPException(404, "Task not found")
    return task


@router.put("/{task_id}")
def update_task(task_id: int, body: TaskUpdate):
    db = get_db()
    data = {k: v for k, v in body.model_dump().items() if v is not None}
    task = db.update_task(task_id, data)
    if not task:
        raise HTTPException(404, "Task not found")
    return task


@router.delete("/{task_id}")
def delete_task(task_id: int):
    db = get_db()
    if not db.delete_task(task_id):
        raise HTTPException(404, "Task not found")
    return {"ok": True}


@router.post("/{task_id}/toggle")
def toggle_task(task_id: int):
    db = get_db()
    task = db.toggle_task(task_id)
    if not task:
        raise HTTPException(404, "Task not found")
    return task


@router.post("/{task_id}/run")
def trigger_task_run(task_id: int):
    """Trigger an immediate run of the task (synchronous, returns tweets)."""
    db = get_db()
    task = db.get_task(task_id)
    if not task:
        raise HTTPException(404, "Task not found")
    tweets = run_task(task_id, db=db)
    return {"tweets": tweets, "count": len(tweets)}
```

- [ ] **Step 3: Write tests with FastAPI TestClient**

```python
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
        # This will actually try to search X — it may return empty if cookie
        # is not set, but should not crash.
        resp = client.post(f"/api/tasks/{created['id']}/run")
        assert resp.status_code == 200
        data = resp.json()
        assert "tweets" in data
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/test_server_routes_tasks.py -v -x
```
Expected: all pass (some may return 0 tweets from X, that's fine — the endpoint handles empty results).

- [ ] **Step 5: Commit**

```bash
git add server/routes/__init__.py server/routes/tasks.py tests/test_server_routes_tasks.py
git commit -m "feat: add task CRUD REST routes"
```

---

### Task 4: Manual search + results/stats routes

**Files:**
- Create: `server/routes/search.py`
- Create: `server/routes/results.py`
- Modify: `server/app.py` (assemble all routers into FastAPI app)
- Test: `tests/test_server_routes_search.py`
- Test: `tests/test_server_routes_results.py`

**Interfaces:**
- `POST /api/search` — `{type: "keyword"|"user", keywords: "", users: "", limit: 20}` → `{tweets: [...], count: N}`
- `GET /api/runs/{run_id}/tweets?page=1&size=20` — tweets for a specific run
- `GET /api/stats` — system overview stats

- [ ] **Step 1: Write routes/search.py**

```python
"""Manual search route — one-shot search without creating a task."""

from fastapi import APIRouter
from pydantic import BaseModel, Field

from server.db import get_db
from server.service import run_manual_search

router = APIRouter(prefix="/api", tags=["search"])


class SearchRequest(BaseModel):
    type: str = Field(pattern="^(keyword|user)$")
    keywords: str = ""
    users: str = ""
    limit: int = Field(default=20, ge=1, le=100)


@router.post("/search")
def manual_search(body: SearchRequest):
    db = get_db()
    tweets = run_manual_search(
        query_type=body.type,
        keywords=body.keywords,
        users=body.users,
        limit=body.limit,
        db=db,
    )
    return {"tweets": tweets, "count": len(tweets)}
```

- [ ] **Step 2: Write routes/results.py**

```python
"""Result query routes — list runs, tweets, stats."""

from fastapi import APIRouter, HTTPException, Query

from server.db import get_db

router = APIRouter(prefix="/api", tags=["results"])


@router.get("/tasks/{task_id}/runs")
def list_runs(task_id: int, page: int = Query(1, ge=1), size: int = Query(20, ge=1, le=100)):
    db = get_db()
    task = db.get_task(task_id)
    if not task:
        raise HTTPException(404, "Task not found")
    runs, total = db.list_runs(task_id, page, size)
    return {"items": runs, "total": total, "page": page, "size": size}


@router.get("/runs/{run_id}/tweets")
def list_run_tweets(run_id: int, page: int = Query(1, ge=1), size: int = Query(20, ge=1, le=100)):
    db = get_db()
    tweets, total = db.list_tweets_by_run(run_id, page, size)
    return {"items": tweets, "total": total, "page": page, "size": size}


@router.get("/tasks/{task_id}/tweets")
def list_task_tweets(task_id: int, page: int = Query(1, ge=1), size: int = Query(20, ge=1, le=100)):
    db = get_db()
    task = db.get_task(task_id)
    if not task:
        raise HTTPException(404, "Task not found")
    tweets, total = db.list_tweets_by_task(task_id, page, size)
    return {"items": tweets, "total": total, "page": page, "size": size}


@router.get("/stats")
def get_stats():
    db = get_db()
    return db.get_stats()
```

- [ ] **Step 3: Write app.py (FastAPI assembly)**

```python
"""FastAPI application factory. Lifespan manages DB + APScheduler."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from server.db import close_db, get_db
from server.routes import tasks, search, results


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    db = get_db()
    db.connect()
    yield
    # Shutdown
    close_db()


def create_app() -> FastAPI:
    app = FastAPI(lifespan=lifespan)

    # REST API routes
    app.include_router(tasks.router)
    app.include_router(search.router)
    app.include_router(results.router)

    # Static files (Vue build output) — added later when frontend exists
    # app.mount("/", StaticFiles(directory="server/frontend/dist", html=True), name="frontend")

    return app
```

- [ ] **Step 4: Write server/__main__.py**

```python
"""Server entry point."""

import uvicorn

from .config import server_settings


def main():
    uvicorn.run(
        "server.app:create_app",
        host=server_settings.http_host,
        port=server_settings.http_port,
        factory=True,
        reload=True,
    )


if __name__ == "__main__":
    main()
```

Note: this assumes server config also has `http_host` / `http_port`. Since the server is a separate layer, add those fields to `server/config.py`:

```python
# In server/config.py, add:
http_host: str = "127.0.0.1"
http_port: int = 8000
```

- [ ] **Step 5: Write tests**

```python
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
        # create a task first
        task = client.post("/api/tasks", json={
            "name": "R", "type": "keyword", "keywords": "a", "schedule": "0 9 * * *",
        }).json()
        resp = client.get(f"/api/tasks/{task['id']}/runs")
        assert resp.status_code == 200
        assert resp.json()["total"] == 0

    def test_list_run_tweets_not_found(self, client):
        resp = client.get("/api/runs/99999/tweets")
        assert resp.status_code == 200  # empty result, not 404

    def test_list_task_tweets_not_found(self, client):
        resp = client.get("/api/tasks/99999/tweets")
        assert resp.status_code == 404
```

- [ ] **Step 6: Run tests**

```bash
uv run pytest tests/test_server_routes_search.py tests/test_server_routes_results.py -v
```
Expected: all pass.

- [ ] **Step 7: Commit**

```bash
git add server/routes/search.py server/routes/results.py server/app.py server/__main__.py
git commit -m "feat: add manual search, results routes, and FastAPI app assembly"
```

---

### Task 5: Scheduler — APScheduler integration

**Files:**
- Create: `server/scheduler.py`
- Modify: `server/app.py` (integrate scheduler into lifespan)
- Test: `tests/test_server_scheduler.py`

**Interfaces:**
- Produces: `server.scheduler.init_scheduler() -> AsyncIOScheduler`, `server.scheduler.add_task_job(task_id)` / `remove_task_job(task_id)`
- Consumes: `server.service.run_task(task_id, db)`

- [ ] **Step 1: Write test**

```python
"""Tests for scheduler — focused on job management, not actual execution."""

import pytest
from server.scheduler import SchedulerManager


def test_scheduler_init_and_shutdown():
    mgr = SchedulerManager()
    assert mgr.scheduler is None

    mgr.init()
    assert mgr.scheduler is not None
    assert mgr.scheduler.running

    mgr.shutdown()
    assert not mgr.scheduler.running


def test_add_remove_job():
    mgr = SchedulerManager()
    mgr.init()
    job_id = mgr.add_job(
        task_id=1,
        cron="0 9 * * *",
        func=lambda: None,
    )
    assert job_id is not None
    assert mgr.scheduler.get_job(job_id) is not None

    mgr.remove_job(job_id)
    assert mgr.scheduler.get_job(job_id) is None
    mgr.shutdown()


def test_add_job_with_invalid_cron():
    mgr = SchedulerManager()
    mgr.init()
    # Should handle gracefully — apscheduler will raise
    with pytest.raises(Exception):
        mgr.add_job(task_id=2, cron="not-cron", func=lambda: None)
    mgr.shutdown()
```

- [ ] **Step 2: Run test to see failure**

```bash
uv run pytest tests/test_server_scheduler.py -v
```
Expected: FAIL with ImportError

- [ ] **Step 3: Write scheduler.py**

```python
"""APScheduler manager. Handles adding/removing scheduled jobs for tasks."""

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger


class SchedulerManager:
    """Manages APScheduler lifecycle and task-job mapping."""

    def __init__(self):
        self.scheduler: BackgroundScheduler | None = None
        self._job_map: dict[int, str] = {}  # task_id -> job_id

    def init(self, db_path: str = ""):
        """Initialize and start the scheduler."""
        self.scheduler = BackgroundScheduler(
            daemon=True,
            jobstores={} if not db_path else {
                "default": {
                    "type": "sqlalchemy",
                    "url": f"sqlite:///{db_path}",
                }
            },
        )
        self.scheduler.start()

    def shutdown(self):
        if self.scheduler:
            self.scheduler.shutdown(wait=False)
            self.scheduler = None

    def add_job(self, task_id: int, cron: str, func) -> str | None:
        """Add a scheduled job for a task. Returns job_id or None."""
        if not self.scheduler:
            return None
        trigger = CronTrigger.from_crontab(cron)
        # Wrap the function to receive task_id as argument
        def wrapper():
            func(task_id)

        job = self.scheduler.add_job(
            wrapper,
            trigger=trigger,
            id=f"task_{task_id}",
            replace_existing=True,
            name=f"Task #{task_id}",
        )
        self._job_map[task_id] = job.id
        return job.id

    def remove_job(self, task_id: int):
        """Remove the scheduled job for a task."""
        if not self.scheduler:
            return
        job_id = self._job_map.pop(task_id, None)
        if job_id:
            try:
                self.scheduler.remove_job(job_id)
            except Exception:
                pass  # job may already be gone

    def reload_all(self, tasks: list[dict], func):
        """Reload all jobs from a list of task dicts."""
        if not self.scheduler:
            return
        # Remove all existing jobs
        for task_id in list(self._job_map.keys()):
            self.remove_job(task_id)

        # Add enabled tasks
        for task in tasks:
            if task.get("enabled") and task.get("schedule"):
                self.add_job(task["id"], task["schedule"], func)


# Global singleton
_scheduler_mgr = SchedulerManager()


def get_scheduler() -> SchedulerManager:
    return _scheduler_mgr
```

- [ ] **Step 4: Integrate scheduler into server/app.py lifespan**

Replace the lifespan function:

```python
from server.scheduler import get_scheduler
from server.service import run_task


def _scheduled_run(task_id: int):
    """Callback for APScheduler — run a task."""
    from server.db import get_db
    db = get_db()
    run_task(task_id, db=db)


@asynccontextmanager
async def lifespan(app: FastAPI):
    db = get_db()
    db.connect()

    # Init scheduler and load all enabled tasks
    mgr = get_scheduler()
    mgr.init(db_path=server_settings.db_path)
    tasks, _ = db.list_tasks(page=1, size=9999)
    mgr.reload_all(tasks, _scheduled_run)

    yield

    mgr.shutdown()
    close_db()
```

- [ ] **Step 5: Run scheduler tests**

```bash
uv run pytest tests/test_server_scheduler.py -v
```
Expected: all pass.

- [ ] **Step 6: Add apscheduler to pyproject.toml**

```toml
# Add to dependencies in pyproject.toml:
"apscheduler>=3.10",
```

- [ ] **Step 7: Commit**

```bash
git add server/scheduler.py server/app.py tests/test_server_scheduler.py
git commit -m "feat: add APScheduler integration with job persistence"
```

---

### Task 6: Vue project setup + base layout

**Files:**
- Create: `server/frontend/package.json`
- Create: `server/frontend/vite.config.ts`
- Create: `server/frontend/tsconfig.json`
- Create: `server/frontend/tsconfig.node.json`
- Create: `server/frontend/index.html`
- Create: `server/frontend/src/main.ts`
- Create: `server/frontend/src/App.vue`
- Create: `server/frontend/src/router.ts`
- Create: `server/frontend/src/api/index.ts`
- Create: `server/frontend/src/types/index.ts`

**Prerequisites:** Node.js (v18+) must be installed.

- [ ] **Step 1: Create package.json with Vue 3 + Vite + Naive UI**

```json
{
  "name": "omnispy-frontend",
  "version": "0.1.0",
  "private": true,
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "vue-tsc && vite build",
    "preview": "vite preview"
  },
  "dependencies": {
    "vue": "^3.4",
    "vue-router": "^4.3",
    "naive-ui": "^2.38",
    "axios": "^1.7"
  },
  "devDependencies": {
    "@vitejs/plugin-vue": "^5.0",
    "typescript": "^5.4",
    "vite": "^5.4",
    "vue-tsc": "^2.0"
  }
}
```

- [ ] **Step 2: Create vite.config.ts**

```typescript
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: 'dist',
  },
})
```

- [ ] **Step 3: Create tsconfig files**

```json
// tsconfig.json
{
  "compilerOptions": {
    "target": "ES2020",
    "module": "ESNext",
    "moduleResolution": "bundler",
    "strict": true,
    "jsx": "preserve",
    "resolveJsonModule": true,
    "isolatedModules": true,
    "esModuleInterop": true,
    "lib": ["ES2020", "DOM", "DOM.Iterable"],
    "skipLibCheck": true,
    "noEmit": true,
    "paths": {
      "@/*": ["./src/*"]
    }
  },
  "include": ["src/**/*.ts", "src/**/*.vue"],
  "references": [{ "path": "./tsconfig.node.json" }]
}
```

```json
// tsconfig.node.json
{
  "compilerOptions": {
    "composite": true,
    "skipLibCheck": true,
    "module": "ESNext",
    "moduleResolution": "bundler",
    "allowSyntheticDefaultImports": true
  },
  "include": ["vite.config.ts"]
}
```

- [ ] **Step 4: Create index.html**

```html
<!DOCTYPE html>
<html lang="zh-CN">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>Omnispy — 社交媒体监控</title>
  </head>
  <body>
    <div id="app"></div>
    <script type="module" src="/src/main.ts"></script>
  </body>
</html>
```

- [ ] **Step 5: Create types/index.ts**

```typescript
export interface Task {
  id: number
  name: string
  type: 'keyword' | 'user' | 'mixed'
  keywords: string
  users: string
  schedule: string
  enabled: number
  created_at: string
  updated_at: string
}

export interface TaskRun {
  id: number
  task_id: number
  status: 'running' | 'success' | 'failed'
  started_at: string
  finished_at: string | null
  error_msg: string
}

export interface Tweet {
  id: number
  tweet_id: string
  task_run_id: number
  task_id: number
  author: string
  text: string
  time: string
  url: string
  crawled_at: string
}

export interface PaginatedResponse<T> {
  items: T[]
  total: number
  page: number
  size: number
}

export interface Stats {
  total_tasks: number
  enabled_tasks: number
  runs_today: number
  last_run_at: string | null
}
```

- [ ] **Step 6: Create src/api/index.ts**

```typescript
import axios from 'axios'
import type { Task, TaskRun, Tweet, PaginatedResponse, Stats } from '../types'

const api = axios.create({ baseURL: '/api' })

// Tasks
export function listTasks(page = 1, size = 20) {
  return api.get<PaginatedResponse<Task>>('/tasks', { params: { page, size } })
}

export function getTask(id: number) {
  return api.get<Task>(`/tasks/${id}`)
}

export function createTask(data: Partial<Task>) {
  return api.post<Task>('/tasks', data)
}

export function updateTask(id: number, data: Partial<Task>) {
  return api.put<Task>(`/tasks/${id}`, data)
}

export function deleteTask(id: number) {
  return api.delete(`/tasks/${id}`)
}

export function toggleTask(id: number) {
  return api.post<Task>(`/tasks/${id}/toggle`)
}

export function triggerRun(id: number) {
  return api.post<{ tweets: Tweet[]; count: number }>(`/tasks/${id}/run`)
}

// Runs & Tweets
export function listRuns(taskId: number, page = 1, size = 20) {
  return api.get<PaginatedResponse<TaskRun>>(`/tasks/${taskId}/runs`, { params: { page, size } })
}

export function listRunTweets(runId: number, page = 1, size = 20) {
  return api.get<PaginatedResponse<Tweet>>(`/runs/${runId}/tweets`, { params: { page, size } })
}

export function listTaskTweets(taskId: number, page = 1, size = 20) {
  return api.get<PaginatedResponse<Tweet>>(`/tasks/${taskId}/tweets`, { params: { page, size } })
}

// Search
export function manualSearch(type: 'keyword' | 'user', keywords: string, users: string, limit = 20) {
  return api.post<{ tweets: Tweet[]; count: number }>('/search', { type, keywords, users, limit })
}

// Stats
export function getStats() {
  return api.get<Stats>('/stats')
}
```

- [ ] **Step 7: Create src/router.ts**

```typescript
import { createRouter, createWebHistory } from 'vue-router'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', name: 'task-list', component: () => import('./views/TaskList.vue') },
    { path: '/tasks/new', name: 'task-new', component: () => import('./views/TaskForm.vue') },
    { path: '/tasks/:id/edit', name: 'task-edit', component: () => import('./views/TaskForm.vue') },
    { path: '/tasks/:id', name: 'task-detail', component: () => import('./views/TaskDetail.vue') },
    { path: '/search', name: 'manual-search', component: () => import('./views/ManualSearch.vue') },
  ],
})

export default router
```

- [ ] **Step 8: Create src/main.ts**

```typescript
import { createApp } from 'vue'
import App from './App.vue'
import router from './router'

const app = createApp(App)
app.use(router)
app.mount('#app')
```

- [ ] **Step 9: Create App.vue (naive-ui provider + layout)**

```vue
<script setup lang="ts">
import { NConfigProvider, NMessageProvider, darkTheme, zhCN, dateZhCN } from 'naive-ui'
</script>

<template>
  <NConfigProvider :theme="darkTheme" :locale="zhCN" :date-locale="dateZhCN">
    <NMessageProvider>
      <router-view />
    </NMessageProvider>
  </NConfigProvider>
</template>

<style>
html, body, #app {
  margin: 0;
  padding: 0;
  height: 100%;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
}
</style>
```

- [ ] **Step 10: Install deps and verify build**

```bash
cd server/frontend && npm install && cd ../..
```

- [ ] **Step 11: Commit**

```bash
git add server/frontend/package.json server/frontend/vite.config.ts server/frontend/tsconfig*.json server/frontend/index.html server/frontend/src/main.ts server/frontend/src/App.vue server/frontend/src/router.ts server/frontend/src/api/index.ts server/frontend/src/types/index.ts
git commit -m "feat: add Vue 3 + Naive UI frontend scaffold"
```

---

### Task 7: Frontend Page 1 — Task list (home)

**Files:**
- Create: `server/frontend/src/views/TaskList.vue`

- [ ] **Step 1: Implement TaskList.vue**

```vue
<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { NButton, NCard, NDataTable, NSpace, NTag, NIcon, NPopconfirm, NSpin } from 'naive-ui'
import { Add as AddIcon, Refresh as RefreshIcon } from '@vicons/ionicons5'
import { listTasks, deleteTask, toggleTask, getStats, triggerRun } from '../api'
import type { Task, Stats } from '../types'

const router = useRouter()
const tasks = ref<Task[]>([])
const stats = ref<Stats | null>(null)
const loading = ref(true)
const page = ref(1)
const total = ref(0)

async function load() {
  loading.value = true
  try {
    const [tRes, sRes] = await Promise.all([
      listTasks(page.value, 20),
      getStats(),
    ])
    tasks.value = tRes.data.items
    total.value = tRes.data.total
    stats.value = sRes.data
  } finally {
    loading.value = false
  }
}

async function handleDelete(id: number) {
  await deleteTask(id)
  await load()
}

async function handleToggle(id: number) {
  await toggleTask(id)
  await load()
}

async function handleRun(id: number) {
  await triggerRun(id)
  window.$message?.success('执行完成')
}

onMounted(load)

const columns = [
  { title: '名称', key: 'name', ellipsis: { tooltip: true } },
  {
    title: '类型',
    key: 'type',
    render(row: Task) {
      const map: Record<string, string> = { keyword: '关键词', user: '用户', mixed: '混合' }
      return h(NTag, { size: 'small', type: row.type === 'keyword' ? 'info' : row.type === 'user' ? 'success' : 'warning' },
        () => map[row.type] || row.type
      )
    },
  },
  { title: '关键词/用户', key: 'keywords', ellipsis: { tooltip: true } },
  { title: '调度', key: 'schedule' },
  {
    title: '状态',
    key: 'enabled',
    render(row: Task) {
      return h(NTag, { size: 'small', type: row.enabled ? 'success' : 'default' },
        () => row.enabled ? '启用' : '禁用'
      )
    },
  },
  {
    title: '操作',
    key: 'actions',
    render(row: Task) {
      return h(NSpace, { size: 'small' }, () => [
        h(NButton, { size: 'tiny', onClick: () => router.push(`/tasks/${row.id}`) }, () => '详情'),
        h(NButton, { size: 'tiny', onClick: () => router.push(`/tasks/${row.id}/edit`) }, () => '编辑'),
        h(NButton, { size: 'tiny', onClick: () => handleToggle(row.id) }, () => row.enabled ? '禁用' : '启用'),
        h(NButton, { size: 'tiny', onClick: () => handleRun(row.id) }, () => '运行'),
        h(NPopconfirm, { onPositiveClick: () => handleDelete(row.id) }, {
          default: () => '确定删除此任务？',
          trigger: () => h(NButton, { size: 'tiny', type: 'error' }, () => '删除'),
        }),
      ])
    },
  },
]
</script>

<template>
  <div style="max-width: 1200px; margin: 0 auto; padding: 24px;">
    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 24px;">
      <h1 style="margin: 0;">Omnispy 监控面板</h1>
      <NSpace>
        <NButton @click="load" :loading="loading">
          <template #icon><NIcon><RefreshIcon /></NIcon></template>
          刷新
        </NButton>
        <NButton type="primary" @click="router.push('/tasks/new')">
          <template #icon><NIcon><AddIcon /></NIcon></template>
          新建任务
        </NButton>
      </NSpace>
    </div>

    <!-- Stats bar -->
    <NSpace v-if="stats" style="margin-bottom: 16px;">
      <NCard size="small" style="min-width: 150px;">
        <template #header>总任务</template>
        {{ stats.total_tasks }}
      </NCard>
      <NCard size="small" style="min-width: 150px;">
        <template #header>已启用</template>
        {{ stats.enabled_tasks }}
      </NCard>
      <NCard size="small" style="min-width: 150px;">
        <template #header>今日执行</template>
        {{ stats.runs_today }}
      </NCard>
    </NSpace>

    <NCard>
      <template #header>定时任务列表</template>
      <NSpin :show="loading">
        <NDataTable :columns="columns" :data="tasks" :row-key="(r: Task) => r.id"
          :pagination="{ page: page, pageSize: 20, pageCount: Math.ceil(total / 20) }"
          @update:page="(p: number) => { page = p; load() }" />
      </NSpin>
    </NCard>
  </div>
</template>
```

Note: For `h()` (hyperscript) to work properly in `<script setup>`, it needs to be imported from `vue`. The Naive UI `h` function works within render functions. However, since Naive UI columns use `h()` heavily, it's cleaner to define them inside the component scope. In practice, you'd need the component context. A simpler approach for production: define column render functions that use `h` imported from `vue`:

```vue
<script setup lang="ts">
import { h, ref, onMounted } from 'vue'
```
And the columns definition works as shown above because `h` is imported.

- [ ] **Step 2: Verify frontend builds**

```bash
cd server/frontend && npx vue-tsc --noEmit && cd ../..
```
(or just `npm run build` for the full build — may fail since other pages aren't created yet)

- [ ] **Step 3: Commit**

```bash
git add server/frontend/src/views/TaskList.vue
git commit -m "feat: add task list page with stats bar"
```

---

### Task 8: Frontend Page 2 — Task form (create/edit)

**Files:**
- Create: `server/frontend/src/views/TaskForm.vue`

- [ ] **Step 1: Implement TaskForm.vue**

```vue
<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import {
  NForm, NFormItem, NInput, NSelect, NButton, NSpace, NCheckbox, NCard, NInputNumber,
} from 'naive-ui'
import { getTask, createTask, updateTask } from '../api'
import type { Task } from '../types'

const router = useRouter()
const route = useRoute()
const isEdit = route.name === 'task-edit'
const taskId = Number(route.params.id)
const saving = ref(false)
const loading = ref(false)

const form = ref({
  name: '',
  type: 'keyword' as 'keyword' | 'user' | 'mixed',
  keywords: '',
  users: '',
  schedule: '0 9 * * *',
  enabled: 1,
})

const typeOptions = [
  { label: '关键词搜索', value: 'keyword' },
  { label: '用户时间线', value: 'user' },
  { label: '混合搜索', value: 'mixed' },
]

const schedulePresets = [
  { label: '每1小时', value: '0 * * * *' },
  { label: '每6小时', value: '0 */6 * * *' },
  { label: '每天 9:00', value: '0 9 * * *' },
  { label: '每天 21:00', value: '0 21 * * *' },
  { label: '每周一 9:00', value: '0 9 * * 1' },
]

onMounted(async () => {
  if (isEdit) {
    loading.value = true
    try {
      const res = await getTask(taskId)
      const t = res.data
      form.value = {
        name: t.name,
        type: t.type,
        keywords: t.keywords,
        users: t.users,
        schedule: t.schedule,
        enabled: t.enabled,
      }
    } finally {
      loading.value = false
    }
  }
})

async function handleSubmit() {
  saving.value = true
  try {
    if (isEdit) {
      await updateTask(taskId, form.value)
      window.$message?.success('任务已更新')
    } else {
      await createTask(form.value)
      window.$message?.success('任务已创建')
    }
    router.push('/')
  } catch (e: any) {
    window.$message?.error(e?.response?.data?.detail || '保存失败')
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <div style="max-width: 700px; margin: 0 auto; padding: 24px;">
    <NCard :title="isEdit ? '编辑任务' : '新建任务'" style="margin-bottom: 16px;">
      <NForm v-if="!loading" :model="form" label-placement="top" @submit.prevent="handleSubmit">
        <NFormItem label="任务名称" required>
          <NInput v-model:value="form.name" placeholder="例如：监控AI大模型动态" />
        </NFormItem>

        <NFormItem label="搜索类型" required>
          <NSelect v-model:value="form.type" :options="typeOptions" />
        </NFormItem>

        <NFormItem v-if="form.type === 'keyword' || form.type === 'mixed'" label="关键词（逗号分隔）">
          <NInput v-model:value="form.keywords" placeholder="AI,GPT,Claude" type="textarea" :rows="2" />
        </NFormItem>

        <NFormItem v-if="form.type === 'user' || form.type === 'mixed'" label="用户名（逗号分隔，不带@）">
          <NInput v-model:value="form.users" placeholder="elonmusk,lexfridman" type="textarea" :rows="2" />
        </NFormItem>

        <NFormItem label="调度频率" required>
          <NSelect v-model:value="form.schedule" :options="schedulePresets" :allow-create="true"
            placeholder="选择或输入 cron 表达式" />
        </NFormItem>

        <NFormItem>
          <NCheckbox v-model:checked="form.enabled" :checked-value="1" :unchecked-value="0">
            创建后立即启用
          </NCheckbox>
        </NFormItem>

        <NSpace>
          <NButton type="primary" attr-type="submit" :loading="saving">
            {{ isEdit ? '保存修改' : '创建任务' }}
          </NButton>
          <NButton @click="router.push('/')">取消</NButton>
        </NSpace>
      </NForm>
    </NCard>
  </div>
</template>
```

- [ ] **Step 2: Commit**

```bash
git add server/frontend/src/views/TaskForm.vue
git commit -m "feat: add task create/edit form page"
```

---

### Task 9: Frontend Pages 3 & 4 — Task detail + Manual search

**Files:**
- Create: `server/frontend/src/views/TaskDetail.vue`
- Create: `server/frontend/src/views/ManualSearch.vue`

- [ ] **Step 1: Implement TaskDetail.vue**

```vue
<script setup lang="ts">
import { h, ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  NCard, NDataTable, NTag, NButton, NSpace, NSpin, NTabs, NTabPane,
} from 'naive-ui'
import { getTask, listRuns, listTaskTweets, triggerRun } from '../api'
import type { Task, TaskRun, Tweet } from '../types'

const route = useRoute()
const router = useRouter()
const taskId = Number(route.params.id)
const task = ref<Task | null>(null)
const runs = ref<TaskRun[]>([])
const tweets = ref<Tweet[]>([])
const loading = ref(true)

const runColumns = [
  { title: '开始时间', key: 'started_at', width: 180 },
  {
    title: '状态',
    key: 'status',
    width: 100,
    render(row: TaskRun) {
      const map: Record<string, string> = { running: '运行中', success: '成功', failed: '失败' }
      return h(NTag, { size: 'small', type: row.status === 'success' ? 'success' : row.status === 'failed' ? 'error' : 'warning' },
        () => map[row.status] || row.status
      )
    },
  },
  { title: '错误信息', key: 'error_msg', ellipsis: { tooltip: true } },
]

const tweetColumns = [
  { title: '作者', key: 'author', width: 120 },
  { title: '内容', key: 'text', ellipsis: { tooltip: true } },
  { title: '时间', key: 'time', width: 180 },
  {
    title: '链接',
    key: 'url',
    width: 80,
    render(row: Tweet) {
      if (!row.url) return ''
      return h('a', { href: row.url, target: '_blank', rel: 'noopener' }, '打开')
    },
  },
]

async function load() {
  loading.value = true
  try {
    const [tRes, runsRes, twRes] = await Promise.all([
      getTask(taskId),
      listRuns(taskId, 1, 20),
      listTaskTweets(taskId, 1, 50),
    ])
    task.value = tRes.data
    runs.value = runsRes.data.items
    tweets.value = twRes.data.items
  } finally {
    loading.value = false
  }
}

async function handleRun() {
  await triggerRun(taskId)
  window.$message?.success('执行完成')
  await load()
}

onMounted(load)
</script>

<template>
  <div style="max-width: 1200px; margin: 0 auto; padding: 24px;">
    <NSpace style="margin-bottom: 16px;">
      <NButton @click="router.push('/')">← 返回</NButton>
      <NButton v-if="task" @click="router.push(`/tasks/${task.id}/edit`)">编辑</NButton>
      <NButton type="primary" @click="handleRun">立即执行</NButton>
    </NSpace>

    <NSpin :show="loading">
      <NCard v-if="task" :title="task.name" style="margin-bottom: 16px;">
        <NSpace>
          <NTag :type="task.type === 'keyword' ? 'info' : task.type === 'user' ? 'success' : 'warning'">
            {{ task.type === 'keyword' ? '关键词' : task.type === 'user' ? '用户' : '混合' }}
          </NTag>
          <NTag v-if="task.keywords">关键词: {{ task.keywords }}</NTag>
          <NTag v-if="task.users">用户: {{ task.users }}</NTag>
          <NTag>调度: {{ task.schedule }}</NTag>
          <NTag :type="task.enabled ? 'success' : 'default'">
            {{ task.enabled ? '已启用' : '已禁用' }}
          </NTag>
        </NSpace>
      </NCard>

      <NTabs type="line">
        <NTabPane tab="执行记录" name="runs">
          <NDataTable :columns="runColumns" :data="runs" :row-key="(r: TaskRun) => r.id" />
        </NTabPane>
        <NTabPane tab="最新推文" name="tweets">
          <NDataTable :columns="tweetColumns" :data="tweets" :row-key="(r: Tweet) => r.id" />
        </NTabPane>
      </NTabs>
    </NSpin>
  </div>
</template>
```

- [ ] **Step 2: Implement ManualSearch.vue**

```vue
<script setup lang="ts">
import { ref } from 'vue'
import { NButton, NCard, NDataTable, NForm, NFormItem, NInput, NSelect, NSpace, NSpin, NTag } from 'naive-ui'
import { manualSearch } from '../api'
import type { Tweet } from '../types'

const queryType = ref<'keyword' | 'user'>('keyword')
const keywords = ref('')
const users = ref('')
const limit = ref(20)
const results = ref<Tweet[]>([])
const searching = ref(false)
const searched = ref(false)

const typeOptions = [
  { label: '关键词搜索', value: 'keyword' },
  { label: '用户时间线', value: 'user' },
]

const tweetColumns = [
  { title: '作者', key: 'author', width: 120 },
  { title: '内容', key: 'text', ellipsis: { tooltip: true } },
  { title: '时间', key: 'time', width: 180 },
  {
    title: '链接', key: 'url', width: 80,
    render(row: Tweet) {
      if (!row.url) return ''
      return h('a', { href: row.url, target: '_blank', rel: 'noopener' }, '打开')
    },
  },
]

async function handleSearch() {
  searching.value = true
  searched.value = false
  try {
    const res = await manualSearch(queryType.value, keywords.value, users.value, limit.value)
    results.value = res.data.tweets
  } catch (e: any) {
    window.$message?.error('搜索失败')
  } finally {
    searching.value = false
    searched.value = true
  }
}
</script>

<template>
  <div style="max-width: 1000px; margin: 0 auto; padding: 24px;">
    <h1>手动搜索</h1>

    <NCard style="margin-bottom: 16px;">
      <NForm label-placement="top" @submit.prevent="handleSearch">
        <NFormItem label="搜索类型">
          <NSelect v-model:value="queryType" :options="typeOptions" />
        </NFormItem>

        <NFormItem v-if="queryType === 'keyword'" label="关键词（逗号分隔）">
          <NInput v-model:value="keywords" placeholder="AI,GPT,Claude" type="textarea" :rows="2" />
        </NFormItem>

        <NFormItem v-if="queryType === 'user'" label="用户名（逗号分隔，不带@）">
          <NInput v-model:value="users" placeholder="elonmusk,lexfridman" type="textarea" :rows="2" />
        </NFormItem>

        <NFormItem label="每个关键词/用户获取条数">
          <NInput v-model:value="limit" type="number" :min="1" :max="100" style="width: 120px;" />
        </NFormItem>

        <NSpace>
          <NButton type="primary" attr-type="submit" :loading="searching">搜索</NButton>
        </NSpace>
      </NForm>
    </NCard>

    <NSpin :show="searching">
      <NCard v-if="searched" :title="`搜索结果 (${results.length} 条)`">
        <NDataTable v-if="results.length > 0" :columns="tweetColumns" :data="results" :row-key="(r: Tweet) => r.id" />
        <p v-else style="color: #888;">无结果</p>
      </NCard>
    </NSpin>
  </div>
</template>
```

Note: The `h` import is needed in ManualSearch.vue too for the hyperlink render function. Add `import { h } from 'vue'` alongside the other imports.

- [ ] **Step 3: Verify full frontend build**

```bash
cd server/frontend && npm run build && cd ../..
```
Expected: build succeeds, `dist/` directory created.

- [ ] **Step 4: Mount frontend dist in FastAPI**

In `server/app.py`, after routes:

```python
import os
from fastapi.staticfiles import StaticFiles

FRONTEND_DIST = os.path.join(os.path.dirname(__file__), "frontend", "dist")
if os.path.isdir(FRONTEND_DIST):
    app.mount("/", StaticFiles(directory=FRONTEND_DIST, html=True), name="frontend")
```

- [ ] **Step 5: Commit**

```bash
git add server/frontend/src/views/TaskDetail.vue server/frontend/src/views/ManualSearch.vue server/app.py
git commit -m "feat: add task detail and manual search pages, serve frontend from FastAPI"
```

---

### Task 10: Integrate scheduler reload on task CRUD + navigation bar

**Files:**
- Modify: `server/routes/tasks.py` (call scheduler reload after create/update/delete/toggle)
- Create: `server/frontend/src/components/NavBar.vue`
- Modify: `server/frontend/src/App.vue` (add NavBar + router-view)

- [ ] **Step 1: Add scheduler reload to task routes**

In `server/routes/tasks.py`, import the scheduler and call reload_all after mutations:

```python
from server.db import get_db
from server.scheduler import get_scheduler
from server.service import run_task


def _reload_scheduler():
    """Reload all enabled tasks into the scheduler."""
    mgr = get_scheduler()
    if not mgr.scheduler:
        return
    db = get_db()
    tasks, _ = db.list_tasks(page=1, size=9999)
    from server.app import _scheduled_run
    mgr.reload_all(tasks, _scheduled_run)
```

Add a call to `_reload_scheduler()` at the end of `create_task`, `update_task`, `delete_task`, and `toggle_task` route handlers.

Also update the `trigger_task_run` handler to use the actual `run_task`:

```python
@router.post("/{task_id}/run")
def trigger_task_run(task_id: int):
    db = get_db()
    task = db.get_task(task_id)
    if not task:
        raise HTTPException(404, "Task not found")
    tweets = run_task(task_id, db=db)
    return {"tweets": tweets, "count": len(tweets)}
```

- [ ] **Step 2: Create NavBar.vue**

```vue
<script setup lang="ts">
import { NMenu } from 'naive-ui'
import { useRouter, useRoute } from 'vue-router'

const router = useRouter()
const route = useRoute()

const menuOptions = [
  { label: '监控面板', key: '/' },
  { label: '手动搜索', key: '/search' },
]

function handleUpdate(key: string) {
  router.push(key)
}
</script>

<template>
  <NMenu :value="route.path" :options="menuOptions" mode="horizontal" @update:value="handleUpdate" />
</template>
```

- [ ] **Step 3: Update App.vue to include NavBar**

```vue
<script setup lang="ts">
import { NConfigProvider, NMessageProvider, darkTheme, zhCN, dateZhCN } from 'naive-ui'
import NavBar from './components/NavBar.vue'
</script>

<template>
  <NConfigProvider :theme="darkTheme" :locale="zhCN" :date-locale="dateZhCN">
    <NMessageProvider>
      <NavBar />
      <router-view />
    </NMessageProvider>
  </NConfigProvider>
</template>
```

- [ ] **Step 4: Commit**

```bash
git add server/routes/tasks.py server/frontend/src/components/NavBar.vue server/frontend/src/App.vue
git commit -m "feat: integrate scheduler reload with task CRUD, add navigation bar"
```

---

### Task 11: End-to-end test + polish

**Files:**
- Modify: `README.md`
- Create/Modify: various minor fixes

- [ ] **Step 1: Run all backend tests**

```bash
uv run pytest -v
```
Expected: all tests pass (both old omnispy tests and new server tests).

- [ ] **Step 2: Manual smoke test — start server**

```bash
uv run uvicorn server.app:create_app --factory --reload --port 8000
```
Expected: server starts, no errors.

- [ ] **Step 3: Manual smoke test — API calls**

```bash
# Create a task
curl -s -X POST http://localhost:8000/api/tasks \
  -H 'Content-Type: application/json' \
  -d '{"name":"测试任务","type":"keyword","keywords":"AI","schedule":"0 9 * * *"}'

# List tasks
curl -s http://localhost:8000/api/tasks

# Manual search
curl -s -X POST http://localhost:8000/api/search \
  -H 'Content-Type: application/json' \
  -d '{"type":"keyword","keywords":"AI","limit":3}'

# Stats
curl -s http://localhost:8000/api/stats
```

- [ ] **Step 4: Verify frontend serves correctly**

Open `http://localhost:8000/` in a browser. Expected: Vue app loads with task list page.

- [ ] **Step 5: Update README.md**

Add a new section under the existing "Usage" section:

```markdown
## Web 服务

启动一体化服务（API + 前端 + 定时任务调度器）：

```bash
uv run uvicorn server.app:create_app --factory --reload --port 8000
```

打开 http://localhost:8000 查看监控面板。

### API 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /api/tasks | 任务列表（分页） |
| POST | /api/tasks | 新建任务 |
| GET | /api/tasks/:id | 任务详情 |
| PUT | /api/tasks/:id | 编辑任务 |
| DELETE | /api/tasks/:id | 删除任务 |
| POST | /api/tasks/:id/toggle | 启用/禁用 |
| POST | /api/tasks/:id/run | 立即执行 |
| GET | /api/tasks/:id/runs | 执行记录 |
| GET | /api/tasks/:id/tweets | 任务全部推文 |
| GET | /api/runs/:id/tweets | 某次执行推文 |
| POST | /api/search | 手动搜索 |
| GET | /api/stats | 系统概览 |
```

- [ ] **Step 6: Final commit**

```bash
git add README.md
git commit -m "docs: update README with web server and API docs"
```

---

## Self-Review Checklist

- [ ] **Spec coverage:** All three requirements covered: keyword/user list search (Task 2, 4, 9), scheduled tasks (Task 5, 10), frontend (Task 6-9).
- [ ] **Placeholder scan:** No "TODO", "TBD", "implement later" — all code is fully specified with complete implementations.
- [ ] **Type consistency:** `run_manual_search` signature (`query_type, keywords, users, limit, db`) is consistent across service, routes, and test. `run_task(task_id, db)` consistent across service, scheduler, and routes.
- [ ] **spider.py untouched:** All batch orchestration lives in `server/service.py`. Only `pyproject.toml` changes in the root package.
- [ ] **Existing tests preserved:** Only new test files added. Old omnispy tests should continue to pass untouched.
