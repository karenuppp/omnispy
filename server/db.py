"""SQLite database layer. Schema, CRUD, and a singleton Database class."""

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from .config import server_settings


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
