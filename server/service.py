"""Service layer: batch orchestration for list-based searches.

This module sits between routes and spider. It handles:
- Splitting keyword/user lists into individual spider calls
- Merging and deduplicating results
- Persisting results to the database
"""

from datetime import datetime, timezone

from omnispy.platforms.x.spider import fetch_user_tweets, search_tweets

from .db import get_db


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
        all_tweets: list[dict] = []
        seen: set[str] = set()
        since = _today_since()
        for kw in kw_list:
            results = search_tweets(
                keywords=[kw],
                sort="top",
                limit=limit,
                since=since,
            )
            for t in results:
                tid = t.get("id")
                if tid and tid not in seen:
                    seen.add(tid)
                    all_tweets.append(t)

        all_tweets.sort(key=lambda t: t.get("time", ""), reverse=True)

        if db:
            db.log_search("keyword", keywords, "", len(all_tweets))

        return all_tweets

    elif query_type == "user":
        user_list = [u.strip().lstrip("@") for u in users.split(",") if u.strip()]
        if not user_list:
            return []
        all_tweets = []
        seen = set()
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

    Creates a task_run record, fetches tweets, persists them, and updates
    the run status.

    Args:
        task_id: The task's ID in the database.
        db:      Database instance (optional, but needed for persistence).

    Returns:
        The list of tweets fetched.
    """
    if db is None:
        db = get_db()

    task = db.get_task(task_id)
    if not task or not task["enabled"]:
        return []

    run_id = db.create_run(task_id)

    try:
        if task["type"] == "user":
            tweets = run_manual_search("user", "", task["users"], limit=1, db=None)
        elif task["type"] == "keyword":
            tweets = run_manual_search("keyword", task["keywords"], "", limit=20, db=None)
        else:  # mixed
            user_tweets = run_manual_search("user", "", task["users"], limit=1, db=None)
            kw_tweets = run_manual_search("keyword", task["keywords"], "", limit=20, db=None)
            seen = {t["id"] for t in user_tweets}
            tweets = user_tweets + [t for t in kw_tweets if t.get("id") not in seen]
            tweets.sort(key=lambda t: t.get("time", ""), reverse=True)

        # Persist tweets
        if tweets:
            db.insert_tweets(tweets, run_id, task_id)

        db.finish_run(run_id, "success")
        return tweets

    except Exception as e:
        db.finish_run(run_id, "failed", str(e))
        return []
