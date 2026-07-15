# omnispy

Multi-platform social media scraping agent. Built on [Scrapling] (crawl layer) and [LightAgent] (agent layer).

Current scope: X (Twitter) user timeline scraping and keyword search.

## Features

- **Timeline fetch** — batch pull latest tweets from multiple X users, with parallel crawling
- **Keyword search** — multi-route search (top/live/hashtag variants), concurrent dispatch
- **API-first** — intercepts X's internal GraphQL API for precise tweet count, falls back to DOM parsing
- **CLI + Web UI** — command-line tool and Vue 3 frontend
- **Scheduled tasks** — APScheduler integration for recurring searches
- **Cookie tool** — interactive browser-based X cookie fetcher (no local browser contamination)

## Quick start

```bash
# Install
uv sync && uv run scrapling install

# Fetch X cookies (one-time)
uv run python -m omnispy get-cookies

# Pull latest 5 tweets from multiple users
uv run python -m omnispy timeline "elonmusk,wsxyza" --limit 5 --workers 5 --output results.json

# Keyword search
uv run python -m omnispy search "AI" --limit 20

# Start web UI
uv run uvicorn server.app:app --port 8000
```

## Setup

1. Run `uv run python -m omnispy get-cookies` — opens an isolated Chromium window to log into X
2. (Optional) Set `LLM_BASE_URL` / `LLM_MODEL` in `.env` for agent mode

## Project layout

```
omnispy/
  platforms/x/    → spider.py (crawl), selectors.py, tools.py, get_cookies.py
  agents/         → x_agent.py, router.py (LightSwarm)
server/           → FastAPI + Vue 3 frontend
tests/            → offline fixture-based tests
```

[Scrapling]: https://github.com/D4Vinci/Scrapling
[LightAgent]: https://github.com/wanxingai/LightAgent
