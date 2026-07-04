# Plan 002 — X (Twitter) 搜索功能

**Status (2026-07-04)**: 已实现，通过 32 个测试，待手动端到端验证 (T7)。

## 目标

为 x_agent 新增搜索能力，让用户可以用自然语言查询 X 上的热帖，支持多种搜索场景：

```
用户 query → LightSwarm → x_agent
  → 工具调用 search_x_tweets (新)
  → X 搜索页 HTML 解析（复用现有 selectors）
  → 结构化推文列表 → 返回
```

典型 query 示例：
- "搜索香港最近的热帖"
- "搜索 @elonmusk 发的关于 AI 的推文"
- "找 10 条 Elon Musk 或 Grok 发的热帖"

---

## 设计决策（已确认）

| 决策 | 选择 | 理由 |
|------|------|------|
| 搜索入口 | `x.com/search?q=...&f=top` | 公开 HTML 页面，复用现有 Scrapling + selectors |
| 参数风格 | 混合（方案 C）— `query` 自由语法 + `keywords`/`from_users` 结构化 | agent 简单场景不出错，复杂场景保留灵活性 |
| 翻页 | 先不做，单页 ≤ ~20 条 | 降低 MVP 复杂度；翻页后续 plan 处理 |
| 工具粒度 | 单工具 `search_x_tweets` | 工具越多路由越容易选错 |
| GraphQL API | 暂不走 | queryId 定期换，逆向成本高 |

---

## 范围 (In Scope)

- `platforms/x/spider.py` 新增 `search_tweets()` 函数
  - 参数：`keywords`、`from_users`、`query`、`sort`、`limit`
  - URL 拼装逻辑（keywords → `"kw1" OR "kw2"`，from_users → `from:u1 OR from:u2`）
  - 复用 `_parse_tweets()` 和现有 selectors
- `platforms/x/tools.py` 注册 `search_x_tweets` 工具（`tool_info` 元数据）
- `agents/x_agent.py` 更新 role prompt + tools 列表
- `agents/router.py` 更新 ROUTER_ROLE 描述
- 测试：搜索 URL 构造逻辑 + 搜索页 fixture 解析 + tool_info 存在性

## 范围之外 (Out of Scope)

- 翻页/滚动加载（> 20 条）
- 按热度阈值过滤（min_faves / min_retweets）
- 时间范围过滤（since / until）
- 其他平台搜索

---

## 关键模块设计

### `platforms/x/spider.py` — 新增 `search_tweets()`

```python
def search_tweets(
    keywords: list[str] | None = None,
    from_users: list[str] | None = None,
    query: str | None = None,
    sort: str = "top",
    limit: int = 20,
) -> list[dict]:
    """Search X tweets by keyword and/or author.

    Args:
        keywords:   List of search terms (combined with OR).
        from_users: List of X handles (combined with OR).
        query:      Raw X search query string.  When provided together with
                    keywords/from_users, they are AND-joined.
        sort:       "top" (hot) or "latest" (real-time).
        limit:      Maximum tweets to return.

    Returns:
        List of dicts with keys: id, text, time, author.
    """
    q = _build_search_query(keywords=keywords, from_users=from_users, raw=query)
    sort_param = "top" if sort == "top" else "live"
    url = f"https://x.com/search?q={q}&f={sort_param}&src=typed_query"

    # ... StealthySession fetch + _parse_tweets (same pattern as fetch_user_tweets)
```

### URL 拼装逻辑 (`_build_search_query`)

```python
def _build_search_query(
    keywords: list[str] | None = None,
    from_users: list[str] | None = None,
    raw: str | None = None,
) -> str:
    parts: list[str] = []

    if keywords:
        kw_parts = [f'"{kw}"' if " " in kw else kw for kw in keywords]
        parts.append("(" + " OR ".join(kw_parts) + ")")

    if from_users:
        user_parts = [f"from:@{u.lstrip('@')}" for u in from_users]
        parts.append("(" + " OR ".join(user_parts) + ")")

    if raw:
        parts.append(raw)

    return " ".join(parts)
```

效果示例：

| 输入 | 输出 |
|------|------|
| `keywords=["香港"]` | `"香港"` |
| `keywords=["香港", "Hong Kong"]` | `"香港" OR "Hong Kong"` |
| `from_users=["elonmusk"]` | `from:@elonmusk` |
| `keywords=["香港"]` + `from_users=["elonmusk"]` | `"香港" from:@elonmusk` |
| `query='min_faves:100 filter:links'` + `keywords=["香港"]` | `"香港" min_faves:100 filter:links` |

---

### `platforms/x/tools.py` — 新增工具注册

```python
search_x_tweets.tool_info = {
    "tool_name": "search_x_tweets",
    "tool_description": (
        "Search X (Twitter) for tweets matching keywords and/or from specific users. "
        "Use this when the user wants to find tweets by topic, keyword, or from "
        "multiple users at once — NOT for fetching a single user's timeline."
    ),
    "tool_params": [
        {"name": "keywords",  "description": "List of search keywords (OR-combined).", "type": "array", "required": False},
        {"name": "from_users","description": "List of X handles (OR-combined).", "type": "array", "required": False},
        {"name": "query",     "description": "Raw X search query for advanced filters.", "type": "string", "required": False},
        {"name": "sort",      "description": "'top' for hot tweets, 'latest' for real-time.", "type": "string", "required": False},
        {"name": "limit",     "description": "Max tweets to return (default 20).", "type": "integer", "required": False},
    ],
}
```

### `agents/x_agent.py` — 更新

```python
from omnispy.platforms.x.tools import fetch_x_user_tweets, search_x_tweets

X_AGENT_ROLE = """You are x_agent, the X (Twitter) specialist in the omnispy swarm.

You have two tools:
- `fetch_x_user_tweets` — get recent tweets from ONE specific user's timeline.
- `search_x_tweets` — search tweets by keyword, topic, or from multiple users.

Choose the right tool based on the user's intent:
- "抓 @xxx 的推文" → fetch_x_user_tweets
- "搜索关于香港的热帖" → search_x_tweets(keywords=["香港"], sort="top")
- "找 @a 和 @b 关于 AI 的帖" → search_x_tweets(keywords=["AI"], from_users=["a", "b"])
...
"""
```

### `agents/router.py` — 更新 ROUTER_ROLE

在 `ROUTER_ROLE` 里补充搜索场景描述，让路由 agent 知道 x_agent 现在也能处理搜索类 query。

---

## 测试策略

| 层 | 测试内容 | 方式 |
|---|---|---|
| `_build_search_query` | URL 拼装正确性 | 纯函数，pytest 参数化 |
| `search_tweets` 解析 | 搜索页 fixture HTML → 结构化推文 | 复用 `_parse_tweets`，新加搜索页 fixture |
| tool 注册 | `search_x_tweets.tool_info` 字段齐全 | 同现有 `test_x_tools.py` 模式 |
| 端到端 | 真实 Cookie + LLM 手动跑 | CLI smoke test |

---

## 风险点

1. **搜索页 DOM 可能与用户页不同**：搜索结果页顶部有 "People" / "Trending" 模块，但推文卡片 `<article>` 结构应该一致。如果不一致，`selectors.py` 加 v3 变体。
2. **未登录可访问性**：`x.com/search?q=...` 未登录状态下可能被限制（重定向到登录页）。需要有效 Cookie。
3. **排序参数**：`f=top` / `f=live` 当前稳定，但 X 可能在未来加入更多排序选项或修改参数名。
4. **单页数量不足**：搜索页首次加载可能少于 20 条（尤其特定关键词 + 热门排序时）。`limit` 参数标注 "up to" 语义。

---

## 阶段任务

- [x] T1. `_build_search_query()` + 单测（URL 拼装）
- [x] T2. `search_tweets()` spider 函数（复用 `_parse_tweets`）
- [x] T3. 搜索页 fixture + 解析测试
- [x] T4. `search_x_tweets` 工具注册 + tool_info 单测
- [x] T5. 更新 `x_agent.py`（新 tool + 更新 role prompt）
- [x] T6. 更新 `router.py` ROUTER_ROLE
- [x] T7. 手测：`python -m omnispy "搜索香港最近的热帖"`（7 条结果）
- [ ] T8. 手测：`python -m omnispy "搜索2026年6月关于香港的热帖"`（需验证时间筛选生效）

## 后续优化

| Feature | Plan |
|---------|------|
| 时间范围筛选 (`since`/`until`) | `plans/003-x-search-time-filter.md` → 已完成
