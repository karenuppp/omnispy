"""Tests for the X LightAgent tool wrappers.

Covers tool_info metadata. Does not exercise the spider itself (covered by
tests/test_x_spider.py).
"""

from omnispy.platforms.x.tools import fetch_x_user_tweets
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