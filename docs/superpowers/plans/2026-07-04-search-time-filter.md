# X 搜索时间范围筛选功能 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 `search_x_tweets` 工具新增 `since`/`until` 时间范围参数，让 LLM 能把"2026年6月"等中文日期表达转为 X 搜索语法 `since:YYYY-MM-DD until:YYYY-MM-DD`。

**Architecture:** spider 层 `_build_search_query()` 新增时间片段拼装逻辑 → tools 层暴露参数 → agent prompt 教导 LLM 如何使用。

**Tech Stack:** Python 3.10+, Scrapling, LightAgent

**设计文档:** `docs/superpowers/specs/2026-07-04-search-time-filter-design.md`

## Global Constraints

- 不改动 spider.py 的 `fetch_user_tweets()` / `_fetch_sync()` / `_parse_tweets()` — 只改搜索链
- `since`/`until` 格式为 `YYYY-MM-DD`，不校验合法性，X 服务端自行处理非法日期
- spider 层不导入 LightAgent（layering rule）
- 保持现有测试全部通过（32 个）

---

### Task 1: spider 层 `_build_search_query()` 新增时间参数

**Files:**
- Modify: `omnispy/platforms/x/spider.py:165-199` (`_build_search_query`)
- Modify: `omnispy/platforms/x/spider.py:100-125` (`search_tweets` signature + pass-through)
- Test: `tests/test_x_spider.py` (新增 4 个测试)

**Interfaces:**
- Consumes: `_build_search_query(keywords, from_users, raw, since, until)` — 增加 `since`/`until`
- Produces: `search_tweets(keywords, from_users, query, sort, limit, since, until)` — 新增 `since`/`until`

- [ ] **Step 1: 为 `_build_search_query` 写失败的测试**

```python
def test_search_query_with_since():
    q = _build_search_query(keywords=["香港"], since="2026-06-01")
    assert q == '香港 since:2026-06-01'


def test_search_query_with_since_until():
    q = _build_search_query(keywords=["香港"], since="2026-06-01", until="2026-06-30")
    assert q == '香港 since:2026-06-01 until:2026-06-30'


def test_search_query_with_until_only():
    q = _build_search_query(keywords=["香港"], until="2026-06-30")
    assert q == '香港 until:2026-06-30'


def test_search_query_since_until_no_keywords():
    q = _build_search_query(since="2026-06-01", until="2026-06-30")
    assert q == 'since:2026-06-01 until:2026-06-30'
```

在 `test_x_spider.py` 的 `# _build_search_query` 测试区末尾添加这 4 个测试。

- [ ] **Step 2: 运行测试确认失败**

```bash
uv run pytest tests/test_x_spider.py -k "since or until" -v
```
预期：4 FAIL（`_build_search_query()` 不认 `since`/`until` 参数）

- [ ] **Step 3: 实现 `_build_search_query` 时间参数**

修改 `spider.py:165` 的函数签名：

```python
def _build_search_query(
    keywords: list[str] | None = None,
    from_users: list[str] | None = None,
    raw: str | None = None,
    since: str | None = None,
    until: str | None = None,
) -> str:
```

在函数体 `parts: list[str] = []` 之后、现有逻辑不变，新增：

```python
    if since:
        parts.append(f"since:{since}")

    if until:
        parts.append(f"until:{until}")
```

这 4 行加在 `if raw: parts.append(raw)` 之后、`return " ".join(parts)` 之前。

- [ ] **Step 4: 运行测试确认通过**

```bash
uv run pytest tests/test_x_spider.py -k "since or" -v
```
预期：4 PASS

- [ ] **Step 5: 实现 `search_tweets()` 参数传递**

修改 `spider.py:100` 的函数签名：

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
```

修改 `spider.py:123` 的 `_build_search_query` 调用行，传递新的参数：

```python
q = _build_search_query(keywords=keywords, from_users=from_users, raw=query, since=since, until=until)
```

- [ ] **Step 6: 运行完整测试确认全部通过**

```bash
uv run pytest tests/test_x_spider.py -v
```
预期：全部 PASS（原有测试不受影响）

- [ ] **Step 7: Commit**

```bash
git add tests/test_x_spider.py omnispy/platforms/x/spider.py
git commit -m "feat: 为 X 搜索新增 since/until 时间范围参数"
```

---

### Task 2: tools 层暴露 `since`/`until` 参数

**Files:**
- Modify: `omnispy/platforms/x/tools.py` — `search_x_tweets` 函数签名 + tool_info
- Test: `tests/test_x_tools.py`

**Interfaces:**
- Produces: `search_x_tweets(keywords, from_users, query, sort, limit, since, until)` — 对外暴露时间参数

- [ ] **Step 1: 写测试验证查找参数存在**

在 `tests/test_x_tools.py` 的 `test_search_tool_info_params` 中添加：

```python
assert params["since"]["type"] == "string"
assert params["since"]["required"] is False
assert params["until"]["type"] == "string"
assert params["until"]["required"] is False
```

- [ ] **Step 2: 运行测试确认失败**

```bash
uv run pytest tests/test_x_tools.py::test_search_tool_info_params -v
```
预期：KeyError on "since"（tool_info 尚未包含 `since`/`until`）

- [ ] **Step 3: 更新 `search_x_tweets` 函数签名**

修改 `tools.py:48` 的函数签名，新增参数：

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
```

更新 docstring（在 `Args:` 区末尾新增）：

```
        since:      Only tweets after this date (YYYY-MM-DD format).
        until:      Only tweets before this date (YYYY-MM-DD format).
```

更新调用行 `tools.py:73`：

```python
    result = _search_tweets(
        keywords=keywords,
        from_users=from_users,
        query=query,
        sort=sort,
        limit=limit,
        since=since,
        until=until,
    )
```

- [ ] **Step 4: 更新 `tool_info` 注册**

在 `tools.py:89` 的 `search_x_tweets.tool_info["tool_params"]` 列表末尾新增：

```python
        {
            "name": "since",
            "description": "Only tweets after this date (YYYY-MM-DD). e.g. '2026-06-01'.",
            "type": "string",
            "required": False,
        },
        {
            "name": "until",
            "description": "Only tweets before this date (YYYY-MM-DD). e.g. '2026-06-30'.",
            "type": "string",
            "required": False,
        },
```

- [ ] **Step 5: 运行测试确认通过**

```bash
uv run pytest tests/test_x_tools.py -v
```
预期：全部 PASS（包括新的 `since`/`until` 断言）

- [ ] **Step 6: Commit**

```bash
git add tests/test_x_tools.py omnispy/platforms/x/tools.py
git commit -m "feat: search_x_tweets 工具暴露 since/until 参数"
```

---

### Task 3: Agent role prompt 增加日期教学

**Files:**
- Modify: `omnispy/agents/x_agent.py`

- [ ] **Step 1: 更新 `X_AGENT_ROLE` 中的搜索示例**

在 `x_agent.py` 中 `Use search_x_tweets when:` 区域末尾（`tools.py` 改动前已有的内容之后），新增以下教学示例：

```
- The user specifies a time range
  (e.g. "搜索2026年6月关于香港的帖子"
   → keywords=["香港"], since="2026-06-01", until="2026-06-30", sort="top")
  (e.g. "搜索最近一周关于AI的帖子"
   → keywords=["AI"], since="2026-06-27", sort="latest")
```

- [ ] **Step 2: 运行现有测试确认无事**

```bash
uv run pytest -v
```
预期：全部 32+ 测试通过（agent prompt 不影响测试）

- [ ] **Step 3: Commit**

```bash
git add omnispy/agents/x_agent.py
git commit -m "feat: x_agent prompt 增加时间范围搜索教学示例"
```

---

### Task 4: 设计文档 + 计划 commit

- [ ] **Step 1: Commit 设计文档和实现计划**

```bash
git add docs/superpowers/specs/2026-07-04-search-time-filter-design.md docs/superpowers/plans/2026-07-04-search-time-filter.md
git commit -m "docs: 搜索时间范围筛选的设计文档和实现计划"
```

---

### Task 5: 端到端验证（手测）

- [ ] **Step 1: 搜索含时间范围**

```bash
uv run python -m omnispy "搜索2026年6月关于香港的热帖"
```
预期：返回 X 上 2026 年 6 月关于香港的热帖结果，不再报错。

- [ ] **Step 2: 搜索无时间范围的基线**

```bash
uv run python -m omnispy "搜索关于香港最近的热帖"
```
预期：正常返回结果，和之前一样。

- [ ] **Step 3: 如果有问题，运行完整测试确认不是代码问题**

```bash
uv run pytest -v
```
预期：全部通过。

- [ ] **Step 4: 更新 plan 002 status**

将 `plans/002-x-search.md` 的 T7 标记为完成，记录端到端验证结果。
