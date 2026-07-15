# Omnispy MVP — 多路搜索 + 定时采集 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** 在现有 server/ 代码基础上，实现设计文档中的多路搜索策略，并确保全链路（后端+前端+调度器）完整可用。

**架构:** 现有代码已有完整后端（FastAPI + APScheduler + SQLite + Vue 3 前端），核心缺失是多路搜索。本计划聚焦增量改动。

**Tech Stack:** Python 3.10+, FastAPI, APScheduler, SQLite, Vue 3 + Naive UI + TypeScript

## Global Constraints
- Dependencies: fastapi, uvicorn, apscheduler 已添加，无需新增
- DB: SQLite, schema 已存在（4 表），不需修改
- 前端已有全部 4 页，只需确认功能对齐
- 不新增 npm 依赖
- 不修改 omnispy/spider.py（爬虫原语层不动）
- 遵守 TDD，每个任务先写测试再改代码

## 现有代码 vs 设计文档的差距

| 模块 | 现有状态 | 需改动 |
|------|---------|--------|
| `server/db.py` | 完整，含 tweet_count 字段 | 无需改动 |
| `server/service.py` | 有 run_manual_search + run_task，但**只走单路搜索** | 核心改动：加 `_expand_queries` + `_multi_search` |
| `server/routes/tasks.py` | 完整 CRUD | 无需改动 |
| `server/routes/search.py` | 只有一个搜索端点 | 确认对齐即可 |
| `server/routes/results.py` | 完整 | 无需改动 |
| `server/scheduler.py` | 完整 | 确认 `finish_run` 传参 |
| `server/app.py` | 完整 | 无需改动 |
| 前端 4 页 | 完整 | 无需改动 |
| `server/frontend/src/api/` | 完整 | 无需改动 |
| 测试 | 无 `tests/` 目录用于 server | 新建 `tests/` |

---

### Task 1: 多路搜索 — `service.py`

**Files:**
- Modify: `server/service.py` (全部重写)
- Test: `tests/test_server_service.py`
- No change to: `omnispy/platforms/x/spider.py`

**Interfaces:**
- Consumes: `spider.search_tweets(keywords, sort, limit, since, until)` — 已存在
- Produces: `_expand_queries(keywords) -> list[dict]`, `_multi_search(keywords, since, until, limit_per_route) -> list[dict]`, `run_manual_search(...)` 签名不变, `run_task(...)` 签名不变

**Step 1: Write the failing tests**

`tests/test_server_service.py`:

```python
"""Tests for server service layer — multi-route search, merge dedup."""

from datetime import datetime, timezone
from unittest.mock import patch

import pytest

from server.service import run_manual_search


class TestExpandQueries:
    """_expand_queries: each keyword → 4 routes"""

    def test_expand_single_keyword(self):
        from server.service import _expand_queries
        queries = _expand_queries(["AI"])
        assert len(queries) == 4
        sorts = {q["sort"] for q in queries}
        assert sorts == {"top", "live"}
        qstrings = {q["q"] for q in queries}
        assert qstrings == {"AI", "#AI"}

    def test_expand_multiple_keywords(self):
        from server.service import _expand_queries
        queries = _expand_queries(["AI", "GPT"])
        assert len(queries) == 8
        assert all(q["sort"] in ("top", "live") for q in queries)

    def test_expand_strips_whitespace(self):
        from server.service import _expand_queries
        queries = _expand_queries(["  AI ", "GPT "])
        # whitespace-only entries are excluded
        assert len(queries) == 8

    def test_expand_empty_list(self):
        from server.service import _expand_queries
        assert _expand_queries([]) == []


class TestMergeDedup:
    """_merge_and_dedup: merge multi-route results, remove duplicates"""

    def test_merge_no_duplicates(self):
        from server.service import _merge_and_dedup
        results = [
            {"id": "1", "text": "a"},
            {"id": "2", "text": "b"},
            {"id": "3", "text": "c"},
        ]
        merged = _merge_and_dedup(results)
        assert len(merged) == 3

    def test_merge_removes_duplicates(self):
        from server.service import _merge_and_dedup
        results = [
            {"id": "1", "text": "a"},
            {"id": "2", "text": "b"},
            {"id": "1", "text": "a"},  # duplicate
            {"id": "1", "text": "a"},  # triple duplicate
        ]
        merged = _merge_and_dedup(results)
        assert len(merged) == 2
        assert [t["id"] for t in merged] == ["1", "2"]

    def test_merge_preserves_first_seen_order(self):
        from server.service import _merge_and_dedup
        results = [
            {"id": "3", "text": "third"},
            {"id": "1", "text": "first"},
            {"id": "2", "text": "second"},
            {"id": "1", "text": "first"},  # dup
        ]
        merged = _merge_and_dedup(results)
        assert [t["id"] for t in merged] == ["3", "1", "2"]

    def test_merge_skips_missing_id(self):
        from server.service import _merge_and_dedup
        results = [
            {"id": "1", "text": "a"},
            {"no_id": True},
            {"id": "2", "text": "b"},
        ]
        merged = _merge_and_dedup(results)
        assert len(merged) == 2
        assert merged[0]["id"] == "1"
        assert merged[-1]["id"] == "2"


class TestMultiSearch:
    """_multi_search: concurrent dispatch + merge dedup"""

    def test_dispatches_all_queries(self):
        from server.service import _multi_search

        dispatched = []

        def fake_search_tweets(keywords, sort, limit, since, until):
            dispatched.append((keywords[0], sort))
            return []

        with patch("server.service.search_tweets", fake_search_tweets):
            results = _multi_search(
                keywords=["AI"],
                since="2026-07-07",
                until="2026-07-08",
                limit_per_route=5,
            )

        assert len(dispatched) == 4  # 4 routes per keyword

    def test_merged_and_deduped(self):
        from server.service import _multi_search

        call_count = 0

        def fake_search_tweets(keywords, sort, limit, since, until):
            nonlocal call_count
            call_count += 1
            # First call returns nothing; second call returns 2 tweets
            if call_count == 2:
                return [
                    {"id": "1", "text": "found in route 2", "author": "U", "time": "2026-07-07T12:00:00Z"},
                ]
            return [
                {"id": "1", "text": "found in route X", "author": "U", "time": "2026-07-07T12:00:00Z"},
            ]

        with patch("server.service.search_tweets", fake_search_tweets):
            results = _multi_search(
                keywords=["AI"],
                since="2026-07-07",
                limit_per_route=10,
            )

        assert len(results) == 1  # deduped to 1
        assert results[0]["id"] == "1"

    def test_empty_results(self):
        from server.service import _multi_search

        def fake_search_tweets(keywords, sort, limit, since, until):
            return []

        with patch("server.service.search_tweets", fake_search_tweets):
            results = _multi_search(keywords=["AI"])
            assert results == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_server_service.py -v`
Expected: FAIL with "function not defined" for `_expand_queries`, `_merge_and_dedup`, `_multi_search`

- [ ] **Step 3: Implement `_expand_queries`, `_merge_and_dedup`, `_multi_search` in service.py**

Replace the entire `server/service.py`:

```python
"""Service layer: batch orchestration for list-based searches.

This module sits between routes and spider. It handles:
- Expanding keyword lists into multi-route search queries (top/live, hashtag variants)
- Concurrent dispatch of all routes
- Merging and deduplicating results
- Persisting results to the database
"""

from datetime import datetime, timezone

from omnispy.platforms.x.spider import fetch_user_tweets, search_tweets

from .db import get_db


def _expand_queries(keywords: list[str]) -> list[dict]:
    """Expand keyword list into multi-route search queries.

    For each keyword, generates 4 routes:
    - keyword + sort=top
    - keyword + sort=live
    - #keyword + sort=top
    - #keyword + sort=live

    Returns list of dicts with keys: ``q``, ``sort``.
    """
    queries: list[dict] = []
    for kw in keywords:
        kw = kw.strip()
        if not kw:
            continue
        for sort in ("top", "live"):
            queries.append({"q": kw, "sort": sort})
            queries.append({"q": f"#{kw}", "sort": sort})
    return queries


def _merge_and_dedup(results: list[dict]) -> list[dict]:
    """Merge results from multiple routes and deduplicate by tweet_id.

    Preserves first-seen order (routes that finish first keep their tweet).
    Skips entries without an ``id`` field.
    """
    seen: set[str] = set()
    deduped: list[dict] = []
    for t in results:
        tid = t.get("id")
        if tid and tid not in seen:
            seen.add(tid)
            deduped.append(t)
    return deduped


def _multi_search(
    keywords: list[str],
    since: str | None = None,
    until: str | None = None,
    limit_per_route: int = 20,
) -> list[dict]:
    """Dispatch all expanded queries concurrently, merge + dedup.

    Args:
        keywords: List of search terms.
        since:    ISO date string (YYYY-MM-DD) or None.
        until:    ISO date string (YYYY-MM-DD) or None.
        limit_per_route: Max tweets per individual route.

    Returns:
        Merged, deduplicated list of tweet dicts.
    """
    import concurrent.futures

    queries = _expand_queries(keywords)
    if not queries:
        return []

    results: list[dict] = []

    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        futures = [
            pool.submit(
                search_tweets,
                keywords=[q["q"]],
                since=since,
                until=until,
                limit=limit_per_route,
                sort=q["sort"],
            )
            for q in queries
        ]
        for future in concurrent.futures.as_completed(futures):
            try:
                results.extend(future.result())
            except Exception:
                pass  # individual route failure is non-fatal

    return _merge_and_dedup(results)


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

        since = _today_since()
        tweets = _multi_search(kw_list, since=since, limit_per_route=limit)
        tweets.sort(key=lambda t: t.get("time", ""), reverse=True)

        if db:
            db.log_search("keyword", keywords, "", len(tweets))

        return tweets

    elif query_type == "user":
        user_list = [u.strip().lstrip("@") for u in users.split(",") if u.strip()]
        if not user_list:
            return []
        all_tweets: list[dict] = []
        seen: set[str] = set()
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

    Creates a task_run record, fetches tweets via multi-route search, persists
    them, and updates the run status.

    Args:
        task_id: The task's ID in the database.
        db:      Database instance (optional, but needed for persistence).

    Returns:
        The list of tweets fetched (deduplicated).
    """
    if db is None:
        db = get_db()

    task = db.get_task(task_id)
    if not task or not task["enabled"]:
        return []

    run_id = db.create_run(task_id)
    tweet_count = 0

    try:
        if task["type"] == "user":
            tweets = run_manual_search("user", "", task["users"], limit=1, db=None)
        elif task["type"] == "keyword":
            kw_list = [k.strip() for k in task["keywords"].split(",") if k.strip()]
            tweets = _multi_search(kw_list, since=_today_since(), limit_per_route=20)
        else:  # mixed
            kw_list = [k.strip() for k in task["keywords"].split(",") if k.strip()]
            user_list = [u.strip().lstrip("@") for u in task["users"].split(",") if u.strip()]

            user_tweets: list[dict] = []
            seen_users: set[str] = set()
            for handle in user_list:
                results = fetch_user_tweets(handle, limit=1)
                for t in results:
                    tid = t.get("id")
                    if tid and tid not in seen_users:
                        seen_users.add(tid)
                        user_tweets.append(t)

            kw_tweets = _multi_search(kw_list, since=_today_since(), limit_per_route=20)

            seen = {t["id"] for t in user_tweets if t.get("id")}
            tweets = user_tweets + [t for t in kw_tweets if t.get("id") not in seen]
            tweets.sort(key=lambda t: t.get("time", ""), reverse=True)

        # Persist tweets
        if tweets:
            db.insert_tweets(tweets, run_id, task_id)
            tweet_count = len(tweets)

        db.finish_run(run_id, "success")
        return tweets

    except Exception as e:
        db.finish_run(run_id, "failed", str(e))
        return []
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_server_service.py -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add server/service.py tests/test_server_service.py
git commit -m "feat: multi-route search — 4 routes per keyword, concurrent dispatch, merge dedup"
```

---

### Task 2: 修复 `finish_run` 缺失 tweet_count 参数

**Files:**
- Modify: `server/db.py` (`finish_run` 方法)
- Modify: `server/service.py` (`run_task` 中调用 `finish_run` 时传入 count)

**Issue:** DB schema 有 `task_runs.tweet_count` 字段，但 `finish_run()` 方法不接收 tweet_count 参数，导致每次完成时 tweet_count 永远是 0。

- [ ] **Step 1: Write the failing test**

```python
# tests/test_server_db.py

def test_finish_run_records_tweet_count():
    from server.db import Database
    import tempfile, os
    
    # Use temp db
    db = Database(":memory:")
    db.connect()
    
    task = db.create_task({"name": "test", "type": "keyword", "keywords": "AI", "schedule": "0 */6 * * *"})
    run_id = db.create_run(task["id"])
    
    db.finish_run(run_id, "success", tweet_count=42)
    run = db._conn.execute("SELECT * FROM task_runs WHERE id = ?", (run_id,)).fetchone()
    assert run["tweet_count"] == 42
    assert run["status"] == "success"
    
    db.close()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_server_db.py::test_finish_run_records_tweet_count -v`
Expected: TypeError about unexpected keyword argument `tweet_count`

- [ ] **Step 3: Update `finish_run` in db.py**

```python
def finish_run(self, run_id: int, status: str, error_msg: str = "", tweet_count: int = 0):
    self._conn.execute(
        "UPDATE task_runs SET status=?, finished_at=strftime('%Y-%m-%dT%H:%M:%SZ','now'), error_msg=?, tweet_count=? WHERE id=?",
        (status, error_msg, tweet_count, run_id),
    )
    self._conn.commit()
```

- [ ] **Step 4: Update caller in service.py**

In `run_task()`, replace:
```python
db.finish_run(run_id, "success")
```
with:
```python
db.finish_run(run_id, "success", tweet_count=tweet_count)
```

And replace:
```python
db.finish_run(run_id, "failed", str(e))
```
with:
```python
db.finish_run(run_id, "failed", str(e), tweet_count=0)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_server_db.py::test_finish_run_records_tweet_count -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add server/db.py server/service.py tests/test_server_db.py
git commit -m "fix: finish_run 写入 tweet_count 字段"
```

---

### Task 3: 验证前端已对齐且可构建

**Files:**
- Navigate: `server/frontend/`

- [ ] **Step 1: 检查 package.json 依赖是否完整**

```bash
cd server/frontend && cat package.json
```
Expected: vue, vue-router, naive-ui, axios, @vicons/ionicons5 等都在

- [ ] **Step 2: 检查前端构建是否通过**

```bash
cd server/frontend && npm run build
```
Expected: 构建成功，dist/ 目录生成

- [ ] **Step 3: 确认 router 配置包含所有 4 页**

Read `server/frontend/src/router/index.ts` and verify routes for:
- `/` → TaskList
- `/tasks/new` → TaskForm
- `/tasks/:id/edit` → TaskForm (edit mode)
- `/tasks/:id` → TaskDetail
- `/search` → ManualSearch

- [ ] **Step 4: 如果构建失败或路由缺失，修复**

（具体修复内容取决于实际发现的问题，无问题则跳过）

- [ ] **Step 5: Commit 前端修复（如果有）**

---

### Task 4: 验证全链路 E2E

**Files:**
- Run: all existing tests

- [ ] **Step 1: 运行所有测试**

```bash
uv run pytest -v
```
Expected: 所有测试通过（包括 spider 测试和新增的 server 测试）

- [ ] **Step 2: 手动 E2E 检查（可选，在本地开发环境）**

```bash
# 确保 .env 中有 X_COOKIE
uv run uvicorn server.app:app --port 8000
```

然后在浏览器中:
1. 访问 http://localhost:8000/ → 看到监控面板首页
2. 新建一个关键词任务（如 "AI"）→ 保存成功
3. 点击"立即执行" → 任务运行，返回结果
4. 查看执行记录和推文列表
5. 手动搜索页 `/search` 可用

- [ ] **Step 3: 如果 E2E 发现 bug，修复并提交**

---

### Task 5: 文档更新

- [ ] **Step 1: 更新 CLAUDE.md 添加 server 相关命令**

```bash
# Add to CLAUDE.md's command table
Run all server tests: `uv run pytest tests/test_server_*.py -v`
Start server: `uv run uvicorn server.app:app --port 8000`
Build frontend: `cd server/frontend && npm run build`
```

- [ ] **Step 2: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: 添加 server 开发命令到 CLAUDE.md"
```


---
