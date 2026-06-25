"""LightAgent tool wrappers for X scraping.

Each tool is a plain Python function with a `tool_info` dict attached, as
required by LightAgent. Keep the docstring + tool_description aligned —
LightAgent feeds both to the LLM.
"""

from .spider import fetch_user_tweets as _fetch_user_tweets


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