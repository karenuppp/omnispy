"""LightAgent tool wrappers for X scraping.

Each tool is a plain Python function with a `tool_info` dict attached, as
required by LightAgent. Keep the docstring + tool_description aligned —
LightAgent feeds both to the LLM.
"""

from .spider import fetch_user_tweets as _fetch_user_tweets
from .spider import search_tweets as _search_tweets


def fetch_x_user_tweets(handle: str, limit: int = 10) -> list[dict]:
    """Fetch the most recent tweets from a specific X (Twitter) user timeline.

    Args:
        handle: The X username without the leading @ (e.g. 'elonmusk').
        limit:  Maximum number of tweets to return (default 10).

    Returns:
        A list of dicts with keys 'id', 'text', 'time', 'author'.
    """
    return _fetch_user_tweets(handle, limit)


fetch_x_user_tweets.tool_info = {
    "tool_name": "fetch_x_user_tweets",
    "tool_description": (
        "Fetch the most recent tweets from a specific X (Twitter) user timeline. "
        "Use this when the user wants tweets/posts from a particular X account."
    ),
    "tool_params": [
        {
            "name": "handle",
            "description": "X username without the leading @ (e.g. 'elonmusk').",
            "type": "string",
            "required": True,
        },
        {
            "name": "limit",
            "description": "Maximum number of tweets to return (default 10).",
            "type": "integer",
            "required": False,
        },
    ],
}


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


search_x_tweets.tool_info = {
    "tool_name": "search_x_tweets",
    "tool_description": (
        "Search X (Twitter) for tweets matching keywords and/or from specific users. "
        "Use this when the user wants to search by topic, keyword, or from multiple "
        "users. NOT for fetching a single user's timeline — use fetch_x_user_tweets "
        "for that."
    ),
    "tool_params": [
        {
            "name": "keywords",
            "description": "List of search keywords (OR-combined).",
            "type": "array",
            "required": False,
        },
        {
            "name": "from_users",
            "description": "List of X handles without the leading @ (OR-combined).",
            "type": "array",
            "required": False,
        },
        {
            "name": "query",
            "description": "Raw X search query snippet for advanced filters.",
            "type": "string",
            "required": False,
        },
        {
            "name": "sort",
            "description": "'top' for hot tweets, 'latest' for real-time.",
            "type": "string",
            "required": False,
        },
        {
            "name": "limit",
            "description": "Maximum tweets to return (default 20, up to ~20 per page).",
            "type": "integer",
            "required": False,
        },
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
    ],
}