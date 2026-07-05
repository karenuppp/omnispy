# Plan 003 — X 搜索时间范围过滤器优化

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复 `search_tweets()` 的时间范围过滤，让 `since`/`until` 参数走服务端而非仅客户端过滤。

**Architecture:** 在 `_build_search_query()` 加回 `since:/until:` URL 参数 + `_fetch_sync` 启用 `network_idle=True` + 空结果时自动重试降级到客户端 `_filter_tweets_by_time()`。

**Tech Stack:** Python 3.10+, Scrapling (StealthySession), pytest

**关联设计**: [Design Doc](003-x-search-time-filter.md) (本文件上半部分)

## Global Constraints

- `_build_search_query` 对外接口保持一致（keyword/from_users/raw 不变，追加 since/until）
- `_fetch_sync` 不破坏现有 `fetch_user_tweets` 路径
- `_filter_tweets_by_time` 保留（但不再由主路径调用）
- 所有现有测试必须通过
- Scrapling `network_idle` 仅在 `_fetch_sync` 中开启，不改变 `fetch_user_tweets` 行为

---

### Task 1: `_build_search_query` 加回 since/until 参数 + 单测

**Files:**
- Modify: `omnispy/platforms/x/spider.py:214-253`
- Test: `tests/test_x_spider.py` （追加新测试）

**Interfaces:**
- Produces: `_build_search_query(keywords, from_users, raw, since, until) -> str`

- [ ] **Step 1.1: 写两个新测试（验证 since/until 在 URL 中的拼装）**

追加到 `tests/test_x_spider.py` 末尾：

```python
# ---------------------------------------------------------------------------
# _build_search_query with since/until
# ---------------------------------------------------------------------------


def test_search_query_with_since():
    q = _build_search_query(keywords=["香港"], since="2026-07-01")
    assert q == "香港 since:2026-07-01"


def test_search_query_with_since_until():
    q = _build_search_query(
        keywords=["香港"],
        since="2026-07-01",
        until="2026-07-05",
    )
    assert q == "香港 since:2026-07-01 until:2026-07-05"


def test_search_query_since_until_no_keywords():
    q = _build_search_query(since="2026-07-01", until="2026-07-05")
    assert q == "since:2026-07-01 until:2026-07-05"
```

- [ ] **Step 1.2: 运行测试确认失败**

```bash
uv run pytest tests/test_x_spider.py::test_search_query_with_since -v
```
Expected: FAIL — `_build_search_query` 当前不接收 since/until 参数。

- [ ] **Step 1.3: 修改 `_build_search_query`**

在 `omnispy/platforms/x/spider.py` 中把 `_build_search_query` 的函数签名改为：

```python
def _build_search_query(
    keywords: list[str] | None = None,
    from_users: list[str] | None = None,
    raw: str | None = None,
    since: str | None = None,
    until: str | None = None,
) -> str:
```

并在 `parts.append(raw)`（约 line 251）之后追加：

```python
    if since:
        parts.append(f"since:{since}")

    if until:
        parts.append(f"until:{until}")
```

更新 docstring，删除旧注释中关于 "since/until 因 ERR_CONNECTION_RESET 故意去掉" 的说明，改为：

```
    Args:
        keywords:   List of search terms (combined with OR).
        from_users: List of X handles without leading @ (combined with OR).
        raw:        Raw X search query snippet, appended as-is.
        since:      Only tweets from this date onwards (YYYY-MM-DD).
        until:      Only tweets before this date (YYYY-MM-DD).
```

- [ ] **Step 1.4: 运行测试确认通过**

```bash
uv run pytest tests/test_x_spider.py::test_search_query_with_since -v
uv run pytest tests/test_x_spider.py::test_search_query_with_since_until -v
uv run pytest tests/test_x_spider.py::test_search_query_since_until_no_keywords -v
```

Expected: 三个 PASS。

- [ ] **Step 1.5: 确保所有既有测试仍通过**

```bash
uv run pytest tests/test_x_spider.py -v
```

Expected: 全部 PASS（原 20+ 测试 + 3 新测试）。

- [ ] **Step 1.6: Commit**

```bash
git add tests/test_x_spider.py omnispy/platforms/x/spider.py
git commit -m "feat: _build_search_query 加回 since/until 参数"
```

---

### Task 2: `search_tweets` 空结果自动降级 + `_fetch_sync` network_idle + 测试

**Files:**
- Modify: `omnispy/platforms/x/spider.py:102-155` （`search_tweets` + `_fetch_sync`）
- Test: `tests/test_x_spider.py` （追加新测试）

**Interfaces:**
- Consumes: `_build_search_query()` from Task 1, `_filter_tweets_by_time()`, `_fetch_sync()`
- Produces: 修改后的 `search_tweets()` 带空结果降级逻辑

- [ ] **Step 2.1: 写 fallback 测试**

修改 `search_tweets` 函数需要 mock `_fetch_sync`，最简单的方式是让测试验证 `_build_search_query` 和 `_filter_tweets_by_time` 的协作。由于 `_fetch_sync` 涉及真实浏览器调用，我们用 `_parse_tweets` 加 fixture 的方式来验证 fallback 逻辑。追加到 `test_x_spider.py` 末尾：

```python
# ---------------------------------------------------------------------------
# search_tweets fallback (server-side → client-side)
# ---------------------------------------------------------------------------


def test_search_fallback_empty_results(monkeypatch):
    """When server-side returns empty, search_tweets retries without
    date operators and client-filters instead."""
    from omnispy.platforms.x.spider import search_tweets, _build_search_query

    calls = []

    def fake_fetch(url, limit):
        calls.append(url)
        # First call (with since): return empty
        # Second call (without since): return a tweet that *would* match
        if "since:" in url:
            return []
        return [
            {
                "id": "99",
                "text": "yesterday tweet",
                "time": "2026-07-04T12:00:00.000Z",
                "author": "User",
            },
            {
                "id": "100",
                "text": "today tweet",
                "time": "2026-07-05T12:00:00.000Z",
                "author": "User",
            },
        ]

    monkeypatch.setattr(
        "omnispy.platforms.x.spider._fetch_sync",
        fake_fetch,
    )

    result = search_tweets(
        keywords=["test"],
        since="2026-07-04",
        until="2026-07-05",
        limit=10,
    )

    # Should have called fetch twice
    assert len(calls) == 2
    assert "since:" in calls[0]
    assert "since:" not in calls[1]
    # Only the matching tweet should remain
    assert len(result) == 1
    assert result[0]["id"] == "99"


def test_search_no_fallback_when_results_exist(monkeypatch):
    """When server-side returns results, no retry happens."""
    from omnispy.platforms.x.spider import search_tweets

    calls = []

    def fake_fetch(url, limit):
        calls.append(url)
        return [{"id": "1", "text": "hot tweet", "time": "2026-07-04T12:00:00.000Z", "author": "U"}]

    monkeypatch.setattr("omnispy.platforms.x.spider._fetch_sync", fake_fetch)

    result = search_tweets(keywords=["test"], since="2026-07-04", limit=10)

    assert len(calls) == 1  # only one fetch
    assert len(result) == 1


def test_search_no_fallback_without_since_until(monkeypatch):
    """When no date filters, no retry happens even if empty."""
    from omnispy.platforms.x.spider import search_tweets

    calls = []

    def fake_fetch(url, limit):
        calls.append(url)
        return []

    monkeypatch.setattr("omnispy.platforms.x.spider._fetch_sync", fake_fetch)

    result = search_tweets(keywords=["test"], limit=10)

    assert len(calls) == 1  # only one fetch, no retry
    assert len(result) == 0
```

- [ ] **Step 2.2: 运行测试确认失败**

```bash
uv run pytest tests/test_x_spider.py::test_search_fallback_empty_results -v
```

Expected: FAIL — `search_tweets` 目前没有降级逻辑。

- [ ] **Step 2.3: 修改 `_fetch_sync` 启用 `network_idle=True`**

```python
def _fetch_sync(url: str, limit: int) -> list[dict]:
    with StealthySession(headless=True, cookies=_parse_cookies(settings.x_cookie)) as session:
        page = session.fetch(url, network_idle=True, timeout=30000, disable_resources=True)
    return _parse_tweets(page, limit)
```

- [ ] **Step 2.4: 修改 `search_tweets` 加降级逻辑**

将 `search_tweets` 函数（约 line 126-149）改写为：

```python
def search_tweets(
    keywords: list[str] | None = None,
    from_users: list[str] | None = None,
    query: str | None = None,
    sort: str = "top",
    limit: int = 20,
    since: str | None = None,
    until: str | None = None,
) -> list[dict]:
    if not keywords and not from_users and not query:
        return []

    q = _build_search_query(
        keywords=keywords,
        from_users=from_users,
        raw=query,
        since=since,
        until=until,
    )
    sort_param = "top" if sort == "top" else "live"
    url = f"https://x.com/search?q={quote(q)}&f={sort_param}&src=typed_query"

    result = _do_fetch(url, limit)

    # Fallback: server-side returned empty → retry without date operators
    # and client-filter instead.
    if not result and (since or until):
        q_fallback = _build_search_query(
            keywords=keywords,
            from_users=from_users,
            raw=query,
            since=None,
            until=None,
        )
        url_fallback = f"https://x.com/search?q={quote(q_fallback)}&f={sort_param}&src=typed_query"
        result = _do_fetch(url_fallback, limit)
        result = _filter_tweets_by_time(result, since, until)

    return result[:limit]


def _do_fetch(url: str, limit: int) -> list[dict]:
    """Internal: run the fetch with StealthySession, handling asyncio loop
    detection. Returns parsed tweet list (may be empty)."""
    import asyncio
    import concurrent.futures

    try:
        running_loop = asyncio.get_running_loop()
    except RuntimeError:
        running_loop = None

    if running_loop is not None:
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(_fetch_sync, url, limit)
            return future.result()

    return _fetch_sync(url, limit)
```

注意：将原来 `search_tweets` 中的 loop 检测逻辑提取为 `_do_fetch` 函数，避免在 `search_tweets` 中重复。

- [ ] **Step 2.5: 运行测试确认通过**

```bash
uv run pytest tests/test_x_spider.py::test_search_fallback_empty_results -v
uv run pytest tests/test_x_spider.py::test_search_no_fallback_when_results_exist -v
uv run pytest tests/test_x_spider.py::test_search_no_fallback_without_since_until -v
```

Expected: 三个 PASS。

- [ ] **Step 2.6: 确保所有既有测试仍通过**

```bash
uv run pytest tests/test_x_spider.py -v
```

Expected: 全部 PASS（原 20+ 测试 + 3 已加 + 3 新）。

- [ ] **Step 2.7: Commit**

```bash
git add omnispy/platforms/x/spider.py tests/test_x_spider.py
git commit -m "feat: search_tweets 空结果降级 + _fetch_sync network_idle"
```

---

### Task 3: 移除 tools.py 遗留调试日志

**Files:**
- Modify: `omnispy/platforms/x/tools.py:74-92`

- [ ] **Step 3.1: 移除 `search_x_tweets` 中的 debug print**

删除以下行（约 line 74-92）：
- 第 75 行：`import sys` 和 `print(f"[DEBUG search_x_tweets] ..."`
- 第 86-87 行：`print(f"[DEBUG search_x_tweets] SUCCESS: ..."`
- 第 88-91 行：`import traceback`、`print(f"[DEBUG search_x_tweets] ERROR: ..."`、`traceback.print_exc(...`

清理后 `search_x_tweets` 函数体精简为：

```python
def search_x_tweets(
    keywords: list[str] | None = None,
    from_users: list[str] | None = None,
    query: str | None = None,
    sort: str = "top",
    limit: int = 20,
    since: str | None = None,
    until: str | None = None,
) -> list[dict]:
    """Search X (Twitter) for tweets by keyword and/or author.

    Use this when the user wants to find tweets by topic, keyword,
    or from multiple users — NOT for fetching a single user's timeline.

    Args:
        keywords:   List of search keywords (OR-combined).
        from_users: List of X handles without @ (OR-combined).
        query:      Raw X search query snippet for advanced filters.
        sort:       'top' (hot) or 'latest' (real-time).
        limit:      Max tweets to return (default 20).
        since:      Only tweets after this date (YYYY-MM-DD format).
        until:      Only tweets before this date (YYYY-MM-DD format).

    Returns:
        List of dicts with keys: id, text, time, author.
    """
    return _search_tweets(
        keywords=keywords,
        from_users=from_users,
        query=query,
        sort=sort,
        limit=limit,
        since=since,
        until=until,
    )
```

- [ ] **Step 3.2: 验证 tools.py 可正常导入**

```bash
uv run python -c "from omnispy.platforms.x.tools import search_x_tweets; print('OK')"
```

Expected: `OK`

- [ ] **Step 3.3: Commit**

```bash
git add omnispy/platforms/x/tools.py
git commit -m "chore: 移除 search_x_tweets 遗留 debug print"
```

---

### Task 4: 端到端验证

- [ ] **Step 4.1: 运行全部测试**

```bash
uv run pytest -v
```

Expected: 全部 PASS。

- [ ] **Step 4.2: 手动端到端测试**

```bash
uv run python -m omnispy "搜索昨天关于香港的热帖"
```

Expected: 返回昨天（2026-07-04）的香港相关热帖，非空。

- [ ] **Step 4.3: 在 plan 中标记状态**

更新 `plans/003-x-search-time-filter.md` 第一行的 `Status` 为 `已实现`。
