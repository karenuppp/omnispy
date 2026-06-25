# Plan 001 — X (Twitter) 抓取 MVP

**Status (2026-06-25)**: T1–T11 complete. MVP shipped: CLI + FastAPI + LightSwarm router + X specialist agent + Scrapling StealthyFetcher crawler. Test suite: 17 passed. Real X crawling still requires a valid browser cookie in `.env` and a running LM Studio — both unverified end-to-end here.

**Post-MVP rename (2026-06-25)**: LLM backend switched from Ollama → LM Studio (port 1234, model `gemma-4-e4b`). Config fields renamed `ollama_*` → `llm_*`, env vars `OLLAMA_*` → `LLM_*`, module `omnispy/llm/ollama.py` → `omnispy/llm/provider.py` (function `ollama_provider()` → `provider()`). Below still shows the original design for context.

## 目标

搭建 omnispy 的最小可运行骨架，跑通一条端到端链路：

```
用户自然语言 query (CLI / HTTP)
   → LightSwarm 路由 → x_agent
   → 工具调用 fetch_x_user_tweets
   → Scrapling StealthyFetcher + 本地 Cookie
   → 结构化推文列表 → 返回给用户
```

memory 暂不接（后续 plan 处理）；LLM 用本地 Ollama。

---

## 范围 (In Scope)

- 项目骨架：pyproject.toml (uv)、目录结构、最小 README
- 配置：`pydantic-settings` 读 `.env`（X_COOKIE、OLLAMA_BASE_URL、OLLAMA_MODEL、HTTP_PORT）
- `platforms/x/spider.py`：封装 StealthyFetcher 调用，单函数 `fetch_user_tweets(handle: str, limit: int) -> list[dict]`
- `platforms/x/selectors.py`：X 推文卡片的 CSS 选择器（独立文件，方便后续站点改版时调整）
- `platforms/x/tools.py`：把 spider 函数包装成 LightAgent 工具（挂 `tool_info`）
- `agents/x_agent.py`：构造 `LightAgent(name="x", tools=[fetch_x_user_tweets], ...)`
- `agents/router.py`：构造 `LightSwarm`，注册 `router_agent` + `x_agent`
- `llm/ollama.py`：统一构造 Ollama 的 `model`/`api_key`/`base_url` 三件套
- CLI 入口：`python -m omnispy "抓 @elonmusk 最近 5 条推文"`
- FastAPI 服务：`POST /query { "q": "..." }`，单接口
- 离线测试：HTML fixture + 解析层 unit test；agent 层 mock tool

## 范围之外 (Out of Scope)

- Memory / 长期记忆 / 用户偏好
- X 的搜索、话题、点赞列表（先只做用户推文列表）
- 小红书 / 微博等其他平台（接口预留，不实现）
- 登录态自动续期 / Cookie 失效检测（先用手动 Cookie）
- 生产部署（Docker / k8s）

---

## 目录结构

```
omnispy/
├── pyproject.toml
├── README.md
├── .env.example
├── .gitignore
├── omnispy/
│   ├── __init__.py
│   ├── __main__.py              # CLI: python -m omnispy "..."
│   ├── config.py                # Settings (pydantic-settings)
│   ├── api.py                   # FastAPI app
│   ├── llm/
│   │   ├── __init__.py
│   │   └── ollama.py            # 构造 Ollama provider dict
│   ├── platforms/
│   │   ├── __init__.py
│   │   └── x/
│   │       ├── __init__.py
│   │       ├── spider.py        # fetch_user_tweets()
│   │       ├── selectors.py     # X CSS 选择器常量
│   │       └── tools.py         # LightAgent tool 包装
│   └── agents/
│       ├── __init__.py
│       ├── x_agent.py           # x_agent = LightAgent(...)
│       └── router.py            # LightSwarm 注册
├── tests/
│   ├── fixtures/
│   │   └── x_user_page.html     # 抓下来的离线 HTML（手动放）
│   ├── test_x_selectors.py      # 解析层
│   ├── test_x_spider.py         # spider 解析逻辑（喂 fixture）
│   └── test_x_tools.py          # tool 包装
└── plans/
    └── 001-x-mvp.md             # 本文件
```

---

## 依赖 (`pyproject.toml`)

```toml
[project]
name = "omnispy"
version = "0.1.0"
requires-python = ">=3.10"
dependencies = [
    "scrapling[all]>=0.3",          # 爬取
    "lightagent>=0.6.5",            # agent 框架
    "pydantic-settings>=2.0",       # 配置
    "fastapi>=0.110",
    "uvicorn[standard]>=0.27",
    "typer>=0.12",                  # CLI
]

[dependency-groups]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.23",
    "httpx>=0.27",                  # 测试 FastAPI
]
```

> ⚠️ `lightagent` 当前在快速迭代，pin 到具体 tag（`>=0.6.5,<0.9`），避免 LightSwarm 实验 API 变更。

---

## 关键模块设计

### `config.py`

```python
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    x_cookie: str                       # 必填；CT0 + auth_token 等
    ollama_base_url: str = "http://localhost:11434/v1"
    ollama_model: str = "qwen2.5:7b"
    ollama_api_key: str = "ollama"      # Ollama 不校验，但 OpenAI 协议要传
    http_host: str = "127.0.0.1"
    http_port: int = 8000

settings = Settings()
```

### `llm/ollama.py`

```python
def ollama_provider() -> dict:
    return {
        "model": settings.ollama_model,
        "api_key": settings.ollama_api_key,
        "base_url": settings.ollama_base_url,
    }
```

### `platforms/x/spider.py`

```python
from scrapling.fetchers import StealthyFetcher, StealthySession
from .selectors import USER_TWEET_CARD, TWEET_TEXT, TWEET_TIME

def fetch_user_tweets(handle: str, limit: int = 10) -> list[dict]:
    """抓取指定用户的最近推文列表。
    handle: 不含 @ 的用户名
    """
    url = f"https://x.com/{handle}"
    with StealthySession(headless=True, cookies_str=settings.x_cookie) as session:
        page = session.fetch(url)
    return _parse_tweets(page, limit)

def _parse_tweets(page, limit: int) -> list[dict]:
    out = []
    for card in page.css(USER_TWEET_CARD)[:limit]:
        out.append({
            "text": card.css(TWEET_TEXT).get(),
            "time": card.css(TWEET_TIME).get(),
        })
    return out
```

### `platforms/x/tools.py`

```python
from .spider import fetch_user_tweets as _fetch

def fetch_x_user_tweets(handle: str, limit: int = 10) -> list[dict]:
    """Fetch the most recent tweets from a specific X (Twitter) user's timeline.

    Args:
        handle: The X username without the leading @ (e.g. 'elonmusk').
        limit:  Maximum number of tweets to return (default 10).

    Returns:
        A list of dicts with keys 'text' and 'time'.
    """
    return _fetch(handle, limit)

fetch_x_user_tweets.tool_info = {
    "tool_name": "fetch_x_user_tweets",
    "tool_description": "Fetch the most recent tweets from a specific X (Twitter) user timeline.",
    "tool_params": [
        {"name": "handle", "description": "X username without leading @", "type": "string", "required": True},
        {"name": "limit",  "description": "Max tweets to return", "type": "integer", "required": False},
    ],
}
```

### `agents/x_agent.py`

```python
from LightAgent import LightAgent
from omnispy.llm.ollama import ollama_provider
from omnispy.platforms.x.tools import fetch_x_user_tweets

def build_x_agent() -> LightAgent:
    return LightAgent(
        name="x_agent",
        role="Crawl X (Twitter) user timelines. Use the fetch_x_user_tweets tool when the user asks for tweets from a specific account.",
        tools=[fetch_x_user_tweets],
        **ollama_provider(),
    )
```

### `agents/router.py`

```python
from LightAgent import LightAgent, LightSwarm
from .x_agent import build_x_agent

ROUTER_ROLE = """You are a routing agent for omnispy. Identify the target platform from the user query and delegate to the appropriate specialist agent.
Current specialists:
- x_agent: X / Twitter user timeline crawling
For any X/Twitter request (e.g. '抓 @xxx 的推文', 'get tweets from @xxx'), delegate to x_agent with the original query.
"""

def build_router() -> LightSwarm:
    router_agent = LightAgent(
        name="router",
        role=ROUTER_ROLE,
        **ollama_provider(),
    )
    x_agent = build_x_agent()
    swarm = LightSwarm()
    swarm.register_agent(router_agent, x_agent)
    return swarm

def run(query: str) -> str:
    swarm = build_router()
    router = next(a for a in swarm.agents if a.name == "router")
    return swarm.run(agent=router, query=query)
```

### `__main__.py` (CLI)

```python
import sys
import typer
from omnispy.agents.router import run

app = typer.Typer()

@app.command()
def main(query: str = typer.Argument(..., help="Natural language query")):
    """omnispy CLI: route a query to the right platform agent."""
    print(run(query))

if __name__ == "__main__":
    app()
```

### `api.py` (FastAPI)

```python
from fastapi import FastAPI
from pydantic import BaseModel
from omnispy.agents.router import run

app = FastAPI(title="omnispy")

class QueryIn(BaseModel):
    q: str

class QueryOut(BaseModel):
    answer: str

@app.post("/query", response_model=QueryOut)
def query_endpoint(body: QueryIn):
    return {"answer": run(body.q)}
```

---

## 测试策略

| 层 | 测试方式 | 覆盖目标 |
|---|---|---|
| 解析 (`selectors` / `spider._parse_tweets`) | pytest + HTML fixture 喂入 | 选择器命中、字段提取 |
| Spider 整体 | pytest + monkeypatch `StealthySession` 返回 mock page | 函数入口参数、返回结构 |
| Tool 包装 | 单测 `fetch_x_user_tweets.tool_info` 存在 + 字段齐全 | 不调真实网络 |
| Router / Agent | mock 工具返回值，单测 router 拼装 + 调用约定 | 不调真实 LLM |

> X 真实抓取（Cloudflare 绕过、Cookie 有效性）只能手测；用 `scripts/run_swarm.py` 或 CLI 跑真实 query 验证。

---

## 阶段任务（建议拆分到独立 commit）

- [ ] T1. 项目骨架：pyproject.toml + uv init + 目录结构 + `.gitignore` + `.env.example` + README 占位
- [ ] T2. `config.py` + `.env.example` 加载单测
- [ ] T3. `platforms/x/selectors.py` + `spider.py`（含 `_parse_tweets`）
- [ ] T4. `platforms/x/spider` 解析层单测（fixture HTML）
- [ ] T5. `platforms/x/tools.py` 工具包装 + 单测 `tool_info`
- [ ] T6. `llm/ollama.py` provider 三件套
- [ ] T7. `agents/x_agent.py` + `agents/router.py`
- [ ] T8. `__main__.py` CLI（typer）
- [ ] T9. `api.py` FastAPI + `/query` endpoint + httpx 测试
- [ ] T10. README 写真实启动步骤（uv sync / 配置 .env / 跑 CLI / 启 FastAPI）
- [ ] T11. 手测：填 Cookie → 启 Ollama → `python -m omnispy "抓 @elonmusk 最近 3 条推文"` → 拿到结构化结果

---

## 风险点 / 待澄清

1. **X 选择器易失效**：X 经常改 DOM 结构。`selectors.py` 独立成文件、单元测试要覆盖到关键字段，未来站点改版时只改这个文件 + 跑测试。
2. **Cookie 格式**：`StealthySession(cookies_str=...)` 接受的是浏览器导出的整段 cookie string（`key=value; key=value`）。`.env.example` 要给出示例格式。
3. **Ollama 模型选择**：`qwen2.5:7b` 起步够用；如果路由器分发不稳定，可换 `qwen2.5:14b` 或 `deepseek-r1:7b`。
4. **lightagent 版本**：pin `<0.9`，避免 LightSwarm / SharedMemoryPool 实验 API 频繁变更。
5. **Cloudflare**：用 `StealthySession(headless=True)` 自动绕过大多数 Turnstile；如失败回退 `DynamicSession`。
6. **登录态降级**：X 未登录访问 `/elonmusk` 也能看到部分公开推文，但 limit/时间线深度受限，先按"需登录"实现。