# omnispy

Multi-platform social media scraping agent. Built on [Scrapling] (crawl layer) and [LightAgent] (agent layer).

Current scope (MVP): X (Twitter) user timeline scraping via `python -m omnispy "..."` or FastAPI.

[Scrapling]: https://github.com/D4Vinci/Scrapling
[LightAgent]: https://github.com/wanxingai/LightAgent

## Status

Active development. See [`plans/001-x-mvp.md`](plans/001-x-mvp.md) for the current implementation plan.

## Setup

Prerequisites:

- Python ≥ 3.10
- [uv](https://docs.astral.sh/uv/) (dependency manager)
- [Ollama](https://ollama.com/) running locally with an OpenAI-compatible model pulled
  (default: `qwen2.5:7b`)
- An X (Twitter) browser session — export cookies as a single string and put in `.env`

```bash
uv sync                              # install deps
cp .env.example .env                 # then edit .env with your cookie + model name
uv run scrapling install             # one-time browser install for Scrapling
```

## Usage

CLI:

```bash
uv run python -m omnispy "抓 @elonmusk 最近 5 条推文"
```

HTTP server:

```bash
uv run uvicorn omnispy.api:app --reload --port 8000

curl -X POST http://127.0.0.1:8000/query \
  -H 'Content-Type: application/json' \
  -d '{"q": "抓 @elonmusk 最近 5 条推文"}'
```

## Development

```bash
uv run pytest                        # run all tests
uv run pytest tests/test_x_spider.py # single test file
uv run pytest -k selectors           # match by name
```

See [CLAUDE.md](CLAUDE.md) for architecture and contributor guidance.