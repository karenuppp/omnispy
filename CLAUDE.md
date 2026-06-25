# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

**omnispy** — a multi-platform social media scraping agent. Two-layer architecture:

- **Crawl layer**: [Scrapling](https://github.com/D4Vinci/Scrapling) for fetching + parsing
- **Agent layer**: [LightAgent](https://github.com/wanxingai/LightAgent) `LightSwarm` (router) → specialized `LightAgent` per platform

Current scope: X (Twitter) user timeline scraping only. Other platforms (小红书 / 微博 etc.) are interface-only — not implemented.

## Current plan

The active implementation plan is [`plans/001-x-mvp.md`](plans/001-x-mvp.md). Read it first when picking up work. Don't start a new task without checking the plan against what's already done.

## Layout

```
omnispy/
├── config.py                # pydantic-settings, reads .env
├── __main__.py              # CLI entry (typer)
├── api.py                   # FastAPI app, POST /query
├── llm/provider.py          # builds the OpenAI-compat provider dict (LM Studio / Ollama / vLLM / etc.)
├── platforms/x/             # X-specific crawl + tool code
│   ├── spider.py            # StealthyFetcher wrapper, returns list[dict]
│   ├── selectors.py         # X DOM selectors — isolated because X breaks often
│   └── tools.py             # LightAgent tool wrappers (tool_info metadata)
└── agents/
    ├── x_agent.py           # builds the x_agent LightAgent
    └── router.py            # builds the LightSwarm, registration only
tests/
└── fixtures/                # offline HTML snapshots for selector tests
plans/                       # implementation plans, one per milestone
```

**Layering rule**: `platforms/*/spider.py` must NOT import LightAgent. Keep the crawl layer testable without an LLM in the loop.

## Development commands

Use [uv](https://docs.astral.sh/uv/). All commands assume project root.

| Action | Command |
|---|---|
| Install deps | `uv sync` |
| Install Scrapling browsers (one-time) | `uv run scrapling install` |
| Run all tests | `uv run pytest` |
| Run one test file | `uv run pytest tests/test_x_spider.py` |
| Run by name | `uv run pytest -k selectors` |
| CLI smoke test | `uv run python -m omnispy "抓 @elonmusk 最近 5 条推文"` |
| Start API server | `uv run uvicorn omnispy.api:app --reload --port 8000` |

## Stack notes

- **Python ≥ 3.10** — Scrapling requires it.
- **`scrapling[all]`** — the bare `pip install scrapling` ships only the parser. You need `[all]` (or at minimum `[fetchers]`) for `StealthyFetcher` and the browser binaries. After `uv sync`, run `uv run scrapling install` once.
- **`lightagent>=0.6.5,<0.9`** — pinned below 0.9 because `LightSwarm` and `SharedMemoryPool` are still iterating fast in v0.8.x/v0.9.x dev. When bumping, read the release notes; `LightSwarm.register_agent` and the `swarm.run(agent=...)` signature have changed across versions.
- **LM Studio** — local LLM via OpenAI-compatible `/v1` endpoint. Make sure `gemma-4-e4b` is loaded and the "Local Server" is enabled in LM Studio's Developer tab (default port 1234) before launching omnispy. Any other OpenAI-compatible backend (Ollama, vLLM, llama.cpp) works the same way — just adjust `LLM_BASE_URL` and `LLM_MODEL`.
- **X cookie** — paste a full browser-exported cookie string into `X_COOKIE` in `.env`. `StealthySession(cookies_str=...)` expects `"key=value; key=value"`. Don't commit `.env`.

## X selectors are a maintenance hotspot

X changes its DOM frequently. The CSS selectors live in `platforms/x/selectors.py` and the parser tests live in `tests/test_x_selectors.py`. When X breaks:

1. Update the selector constant in `selectors.py`.
2. Refresh `tests/fixtures/x_user_page.html`.
3. Re-run `uv run pytest tests/test_x_selectors.py`.
4. Only touch `spider.py` if the response shape (not just selectors) changed.

## Out of scope for MVP

- Memory / long-term user prefs (deliberately deferred — no `mem0` integration yet)
- Login / Cookie rotation / refresh
- Search, topics, likes (only `fetch_x_user_tweets` is implemented)
- Other platforms
- Production deployment (Docker, k8s)

Do not start any of these without a new plan in `plans/`.