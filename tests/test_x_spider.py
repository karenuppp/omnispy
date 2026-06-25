"""Tests for the X spider's HTML parsing layer.

These tests use Scrapling's `Selector` directly on a fixture HTML file —
no network calls, no LLM, no StealthySession.
"""

from pathlib import Path

from scrapling.parser import Selector

from omnispy.platforms.x.spider import _parse_tweets

FIXTURE = Path(__file__).parent / "fixtures" / "x_user_page.html"


def _page():
    return Selector(FIXTURE.read_text(encoding="utf-8"))


def test_parse_returns_all_distinct_tweets():
    page = _page()
    tweets = _parse_tweets(page, limit=10)
    # Fixture has 3 articles but 2 distinct ids — duplicates are dropped.
    assert len(tweets) == 2


def test_parse_extracts_id_text_time_author():
    page = _page()
    tweets = _parse_tweets(page, limit=10)

    assert tweets[0]["id"] == "1234567890"
    assert "Hello, world" in tweets[0]["text"]
    assert tweets[0]["time"] == "2026-06-25T10:00:00.000Z"
    assert "Test User" in tweets[0]["author"]

    assert tweets[1]["id"] == "1234567891"
    assert "Second tweet with" in tweets[1]["text"]
    assert tweets[1]["time"] == "2026-06-25T11:00:00.000Z"


def test_parse_respects_limit():
    page = _page()
    assert len(_parse_tweets(page, limit=1)) == 1


def test_parse_handles_missing_elements():
    """If a card lacks tweetText/User-Name/time, fields should be None, not crash."""
    html = """
    <html><body>
      <article data-testid="tweet">
        <a href="/u/status/42">link</a>
      </article>
    </body></html>
    """
    page = Selector(html)
    tweets = _parse_tweets(page, limit=10)
    assert tweets == [{"id": "42", "text": None, "time": None, "author": None}]