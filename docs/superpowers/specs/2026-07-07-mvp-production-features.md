# Omnispy MVP — 定时多路搜索 + 前端展示

> **Design doc for the MVP production features.** Builds on the existing X spider and adds: multi-route search for max coverage, scheduled periodic collection, dedup storage, and a web frontend for non-technical users.

## Problem

Current `search_tweets` does a single X search query per call and returns whatever X's search index serves. Two problems:

1. **Coverage too low** — X's search index caps per-query results. A single query (even with scrolling) typically returns ~15-20 tweets regardless of `limit`.
2. **No persistence** — Each call is stateless. No history, no dedup across runs, no way to "collect over time."

## Solution Overview

**Multi-route search** — Expand each monitoring keyword into several X search queries (different sort modes, hashtag variants), run them concurrently, merge and dedup by `tweet_id`. Store everything in SQLite. Schedule periodic runs via APScheduler. Surface results via a Vue 3 frontend.

## Multi-Route Search Strategy

### MVP scope (Phase 1)

Two routes per keyword, both zero-cost in engineering:

| Route | Description | Why it works |
|-------|-------------|-------------|
| **Sort: top** | `f=top` — engagement-ranked | Catches high-interaction tweets |
| **Sort: live** | `f=live` — chronologically | Catches newest tweets (top often misses) |
| **Hashtag + top** | `#keyword` + `f=top` | Users who tag vs. users who don't |
| **Hashtag + live** | `#keyword` + `f=live` | Complements all above |

**Implementation:** In `server/service.py`, expand a keyword list into a flat list of `(query_string, sort_mode)` tuples, then dispatch them concurrently via `concurrent.futures.ThreadPoolExecutor`.

### Deferred to post-MVP

| Strategy | Reason deferred |
|----------|----------------|
| Synonym expansion | Requires a synonym table or LLM call — maintenance cost |
| Time-window splitting | 6h window is small; only needed for full historical backfill |
| Interaction threshold | `min_faves:` reduces recall, contrary to "collect everything" goal |
| `filter:` operator | Same as above — too early to filter |
| Progressive window splitting | Recursive logic, only needed for backfill |

### Estimated coverage gain

For a single keyword over 6 hours:
- **Single route:** ~10-20 tweets
- **4 routes (top + live + #top + #live), merged + deduped:** ~25-50 tweets
- **Multiple keywords × 4 routes:** scales linearly

## Architecture

```
┌──────────┐     ┌─────────────────────────────────────────┐     ┌──────────────┐
│  Browser │────→│           FastAPI Server (:8000)          │────→│  SQLite      │
│  (Vue 3) │     │                                           │     │  (omnispy.db)│
└──────────┘     │  ┌─────────┐  ┌──────────┐  ┌─────────┐ │     └──────────────┘
                 │  │ routes/ │→│service.py│→│  db.py  │ │
                 │  │         │  │          │  │         │ │
                 │  │ tasks   │  │_multi_   │  │ CRUD    │ │
                 │  │ search  │  │ search() │  │ queries │ │
                 │  │ results │  │          │  │         │ │
                 │  └─────────┘  └────┬─────┘  └─────────┘ │
                 │                    │                      │
                 │           ┌────────▼────────┐            │
                 │           │  omnispy/spider.py│            │
                 │           │  (StealthySession│            │
                 │           │   + scroll)     │            │
                 │           └─────────────────┘            │
                 │                    │                      │
                 │           ┌────────▼────────┐            │
                 │           │    APScheduler   │            │
                 │           │  (every 6h, etc.)│            │
                 │           └─────────────────┘            │
                 └─────────────────────────────────────────┘
```

### Data flow

```
[User creates task] → [DB: tasks]
    ↓ every 6h (or manual trigger)
[Scheduler triggers task run]
    ↓
[service.py reads task config]
    ↓
[service._expand_queries() — 4 routes per keyword]
    ↓
[concurrent.futures — dispatch all queries in parallel]
    ↓
[Each route → spider.search_tweets() → StealthySession → X.com]
    ↓
[Merge all results → dedup by tweet_id]
    ↓
[DB: INSERT OR IGNORE into tweets]
    ↓
[DB: INSERT task_run record]
```

## Data Model

Four tables in SQLite:

### tasks

```sql
CREATE TABLE tasks (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    type        TEXT NOT NULL CHECK(type IN ('keyword', 'user', 'mixed')),
    keywords    TEXT DEFAULT '',       -- comma-separated
    users       TEXT DEFAULT '',       -- comma-separated
    schedule    TEXT NOT NULL DEFAULT '0 */6 * * *',
    enabled     INTEGER NOT NULL DEFAULT 1,
    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at  TEXT NOT NULL DEFAULT (datetime('now'))
);
```

### task_runs

```sql
CREATE TABLE task_runs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id     INTEGER NOT NULL REFERENCES tasks(id),
    status      TEXT NOT NULL DEFAULT 'running'
                    CHECK(status IN ('running','success','failed')),
    started_at  TEXT NOT NULL DEFAULT (datetime('now')),
    finished_at TEXT,
    error_msg   TEXT,
    tweet_count INTEGER DEFAULT 0       -- how many NEW tweets this run found
);
```

### tweets

```sql
CREATE TABLE tweets (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    tweet_id    TEXT NOT NULL UNIQUE,   -- X's tweet id, UNIQUE = dedup
    task_run_id INTEGER NOT NULL REFERENCES task_runs(id),
    task_id     INTEGER NOT NULL REFERENCES tasks(id),
    author      TEXT,
    text        TEXT,
    time        TEXT,                    -- ISO datetime or relative
    url         TEXT,
    crawled_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX idx_tweets_task_id ON tweets(task_id);
CREATE INDEX idx_tweets_task_run_id ON tweets(task_run_id);
CREATE INDEX idx_tweets_time ON tweets(time);
```

### search_logs (for manual search auditing)

```sql
CREATE TABLE search_logs (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    query_type   TEXT NOT NULL,
    keywords     TEXT,
    users        TEXT,
    result_count INTEGER DEFAULT 0,
    created_at   TEXT NOT NULL DEFAULT (datetime('now'))
);
```

## REST API

### Tasks

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/tasks?page=1&size=20` | List tasks (paginated) |
| POST | `/api/tasks` | Create task |
| GET | `/api/tasks/:id` | Get task details |
| PUT | `/api/tasks/:id` | Update task |
| DELETE | `/api/tasks/:id` | Delete task |
| POST | `/api/tasks/:id/toggle` | Enable/disable |
| POST | `/api/tasks/:id/run` | Trigger manual run (async) |

### Task Runs & Results

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/tasks/:id/runs?page=1&size=20` | List runs for a task |
| GET | `/api/runs/:id/tweets?page=1&size=50` | List tweets from a run |
| GET | `/api/tasks/:id/tweets?page=1&size=50` | List ALL tweets for a task (across runs) |

### Search & Stats

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/search` | Manual search (sync, returns tweets) |
| GET | `/api/stats` | Dashboard stats (total tasks, tweets today, etc.) |

## Project Structure

```
server/
├── __init__.py
├── __main__.py          # uvicorn.run()
├── app.py               # FastAPI app + lifespan (starts APScheduler)
├── config.py            # Server settings (DB path, etc.)
├── db.py                # SQLite models + CRUD functions (no ORM)
├── service.py           # _expand_queries, _multi_search, merge dedup
├── scheduler.py         # APScheduler with SQLiteJobStore
└── routes/
    ├── __init__.py
    ├── tasks.py         # Task CRUD routes
    ├── search.py        # Manual search route
    └── results.py       # Query runs/tweets
```

## Frontend (4 pages)

Built with Vue 3 + TypeScript + Naive UI + Vue Router.

### Page 1: Task List (/) — Homepage
- Table of all tasks (name, type, schedule, status, last run)
- Toggle enable/disable inline
- "New Task" button → Page 2
- Click row → Page 3
- Stats bar at top (total tasks, tweets collected today)

### Page 2: Task Config (/tasks/new, /tasks/:id/edit)
- Form: name, type (keyword/user/mixed), keywords/users, schedule preset
- Schedule: dropdown with presets (1h, 6h, 1d, etc.) + custom cron input
- Save → back to list

### Page 3: Task Detail (/tasks/:id)
- Task info + run history table
- Each run row shows: time, status, tweet count
- Click run → filtered tweet list at bottom
- "Run Now" button
- "Edit" button → Page 2

### Page 4: Manual Search (/search)
- Search type: keyword or user
- Input: keywords / users, limit
- Results table inline (no save)
- Same columns: author, text, time, link

## Service Layer Design

### Keyword → query expansion

```python
def _expand_queries(keywords: list[str]) -> list[dict]:
    """Expand keyword list into multi-route search queries.
    
    For each keyword, generates:
    - keyword + sort=top
    - keyword + sort=live
    - #keyword + sort=top
    - #keyword + sort=live
    """
    queries = []
    for kw in keywords:
        kw = kw.strip()
        if not kw:
            continue
        for sort in ("top", "live"):
            queries.append({"q": kw, "sort": sort})
            queries.append({"q": f"#{kw}", "sort": sort})
    return queries
```

### Multi-route dispatch

```python
def _multi_search(keywords, since=None, until=None, limit_per_route=20):
    """Dispatch all expanded queries concurrently, merge + dedup."""
    import concurrent.futures
    
    queries = _expand_queries(keywords)
    results = []
    
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
            results.extend(future.result())
    
    # Dedup by tweet_id (preserve order)
    seen: set[str] = set()
    deduped = []
    for t in results:
        if t.get("id") and t["id"] not in seen:
            seen.add(t["id"])
            deduped.append(t)
    
    return deduped
```

## Scheduler (APScheduler)

- **Job store:** SQLite (same `omnispy.db`, table `apscheduler_jobs`)
- **Trigger:** CRON expression from `tasks.schedule`
- **On startup:** Read all `enabled=1` tasks from DB, add/restore jobs
- **On task create/update/toggle:** Add/remove/reschedule job in-memory
- **Execution:** Each job triggers `service.run_task(task_id)` which:
  1. Creates `task_run` record (status=running)
  2. Reads task config, expands queries, dispatches multi-search
  3. Inserts deduped tweets via `INSERT OR IGNORE`
  4. Updates `task_run` (status=finished, tweet_count, finished_at)
  5. On error: updates `task_run` (status=failed, error_msg)

## Startup

```python
# server/app.py
from contextlib import asynccontextmanager
from fastapi import FastAPI
from .scheduler import start_scheduler, shutdown_scheduler

@asynccontextmanager
async def lifespan(app: FastAPI):
    start_scheduler()  # reads enabled tasks from DB
    yield
    shutdown_scheduler()

app = FastAPI(lifespan=lifespan)
```

CLI start: `uv run uvicorn server.app:app --port 8000`

## Implementation Order

### Phase 1: Backend core (db + routes + service)
1. `server/db.py` — SQLite schema + CRUD functions
2. `server/routes/tasks.py` — Task CRUD (list/create/update/delete/toggle)
3. `server/routes/search.py` — Manual search endpoint
4. `server/routes/results.py` — Query runs + tweets
5. `server/service.py` — Multi-route search, merge dedup
6. `server/app.py` — FastAPI app, CORS, mount routes

### Phase 2: Frontend
1. Scaffold Vite + Vue 3 + Naive UI + Vue Router
2. Task list page
3. Task config page (new/edit)
4. Task detail page
5. Manual search page

### Phase 3: Scheduler + Integration
1. `server/scheduler.py` — APScheduler with SQLiteJobStore
2. Wire scheduler to task lifecycle (create/update/toggle triggers job change)
3. E2E test: create task → scheduler picks it up → runs → results in DB

## Out of Scope

- User authentication / multi-user
- LLM Agent integration in search flow (CLI Agent path stays separate)
- Email/notification on new results
- Historical backfill (time-window splitting)
- Rate limiting / proxy rotation
- Docker deployment
- Other platforms (Weibo, Xiaohongshu, etc.)
