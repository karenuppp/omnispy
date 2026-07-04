"""Tests for the X LightAgent tool wrappers.

Covers tool_info metadata. Does not exercise the spider itself (covered by
tests/test_x_spider.py).
"""

from omnispy.platforms.x.tools import fetch_x_user_tweets, search_x_tweets
from omnispy.platforms.x import tools as tools_module


def test_tool_attached_to_function():
    assert hasattr(fetch_x_user_tweets, "tool_info")
    assert callable(fetch_x_user_tweets)


def test_tool_info_required_fields():
    info = fetch_x_user_tweets.tool_info
    assert info["tool_name"] == "fetch_x_user_tweets"
    assert isinstance(info["tool_description"], str) and info["tool_description"]
    assert isinstance(info["tool_params"], list) and info["tool_params"]


def test_tool_info_handle_param():
    params = {p["name"]: p for p in fetch_x_user_tweets.tool_info["tool_params"]}
    assert params["handle"]["type"] == "string"
    assert params["handle"]["required"] is True


def test_tool_info_limit_param():
    params = {p["name"]: p for p in fetch_x_user_tweets.tool_info["tool_params"]}
    assert params["limit"]["type"] == "integer"
    assert params["limit"]["required"] is False


def test_tool_delegates_to_spider(monkeypatch):
    """fetch_x_user_tweets should call spider.fetch_user_tweets with same args."""
    calls = []

    def fake_fetch(handle, limit=10):
        calls.append((handle, limit))
        return [{"id": "1", "text": "x", "time": "t", "author": "a"}]

    monkeypatch.setattr(tools_module, "_fetch_user_tweets", fake_fetch)

    result = fetch_x_user_tweets("elonmusk", 3)
    assert calls == [("elonmusk", 3)]
    assert result == [{"id": "1", "text": "x", "time": "t", "author": "a"}]


# ---------------------------------------------------------------------------
# search_x_tweets tool
# ---------------------------------------------------------------------------


def test_search_tool_attached():
    assert hasattr(search_x_tweets, "tool_info")
    assert callable(search_x_tweets)


def test_search_tool_info_required_fields():
    info = search_x_tweets.tool_info
    assert info["tool_name"] == "search_x_tweets"
    assert isinstance(info["tool_description"], str) and info["tool_description"]
    assert isinstance(info["tool_params"], list) and info["tool_params"]


def test_search_tool_info_params():
    params = {p["name"]: p for p in search_x_tweets.tool_info["tool_params"]}
    assert params["keywords"]["type"] == "array"
    assert params["keywords"]["required"] is False
    assert params["from_users"]["type"] == "array"
    assert params["from_users"]["required"] is False
    assert params["query"]["type"] == "string"
    assert params["sort"]["type"] == "string"
    assert params["limit"]["type"] == "integer"
    assert params["since"]["type"] == "string"
    assert params["since"]["required"] is False
    assert params["until"]["type"] == "string"
    assert params["until"]["required"] is False


def test_search_tool_delegates_to_spider(monkeypatch):
    """search_x_tweets should call spider.search_tweets with same args."""
    calls = []

    def fake_search(keywords=None, from_users=None, query=None, sort="top", limit=20, since=None, until=None):
        calls.append((keywords, from_users, query, sort, limit, since, until))
        return [{"id": "1", "text": "x", "time": "t", "author": "a"}]

    monkeypatch.setattr(tools_module, "_search_tweets", fake_search)

    result = search_x_tweets(
        keywords=["香港"], from_users=["elonmusk"], query="min_faves:10",
        sort="top", limit=10,
    )
    assert calls == [(["香港"], ["elonmusk"], "min_faves:10", "top", 10, None, None)]
    assert result == [{"id": "1", "text": "x", "time": "t", "author": "a"}]