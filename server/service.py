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

        db.finish_run(run_id, "success", tweet_count=tweet_count)
        return tweets

    except Exception as e:
        db.finish_run(run_id, "failed", str(e), tweet_count=0)
        return []
