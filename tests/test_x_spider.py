"""Tests for the X spider's HTML parsing layer.

These tests use Scrapling's `Selector` directly on a fixture HTML file —
no network calls, no LLM, no StealthySession.
"""

from pathlib import Path

from scrapling.parser import Selector

from omnispy.platforms.x.spider import _build_search_query, _parse_tweets

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
    """Cards with no tweet text (image-only, etc.) are skipped, not crashed."""
    html = """
    <html><body>
      <article data-testid="tweet">
        <a href="/u/status/42">link</a>
      </article>
    </body></html>
    """
    page = Selector(html)
    tweets = _parse_tweets(page, limit=10)
    assert tweets == []


# ---------------------------------------------------------------------------
# _build_search_query
# ---------------------------------------------------------------------------


def test_search_query_keywords_only():
    assert _build_search_query(keywords=["香港"]) == "香港"


def test_search_query_keywords_multi():
    q = _build_search_query(keywords=["香港", "Hong Kong"])
    assert q == '(香港 OR "Hong Kong")'


def test_search_query_from_users_only():
    q = _build_search_query(from_users=["elonmusk"])
    assert q == "from:@elonmusk"


def test_search_query_from_users_multi():
    q = _build_search_query(from_users=["elonmusk", "grok"])
    assert q == "(from:@elonmusk OR from:@grok)"


def test_search_query_from_users_strips_at():
    q = _build_search_query(from_users=["@elonmusk", "@grok"])
    assert q == "(from:@elonmusk OR from:@grok)"


def test_search_query_keywords_and_users():
    q = _build_search_query(keywords=["AI"], from_users=["elonmusk", "grok"])
    assert q == 'AI (from:@elonmusk OR from:@grok)'


def test_search_query_raw_only():
    assert _build_search_query(raw="min_faves:100") == "min_faves:100"


def test_search_query_combined_with_raw():
    q = _build_search_query(keywords=["香港"], raw="min_faves:100 filter:links")
    assert q == '香港 min_faves:100 filter:links'


def test_search_query_all_empty():
    assert _build_search_query() == ""


def test_search_query_with_since():
    q = _build_search_query(keywords=["香港"], since="2026-06-01")
    assert q == '香港 since:2026-06-01'


def test_search_query_with_since_until():
    q = _build_search_query(keywords=["香港"], since="2026-06-01", until="2026-06-30")
    assert q == '香港 since:2026-06-01 until:2026-06-30'


def test_search_query_with_until_only():
    q = _build_search_query(keywords=["香港"], until="2026-06-30")
    assert q == '香港 until:2026-06-30'


def test_search_query_since_until_no_keywords():
    q = _build_search_query(since="2026-06-01", until="2026-06-30")
    assert q == 'since:2026-06-01 until:2026-06-30'


# ---------------------------------------------------------------------------
# search page parsing
# ---------------------------------------------------------------------------

SEARCH_FIXTURE = Path(__file__).parent / "fixtures" / "x_search_page.html"


def _search_page():
    return Selector(SEARCH_FIXTURE.read_text(encoding="utf-8"))


def test_parse_search_results():
    page = _search_page()
    tweets = _parse_tweets(page, limit=10)
    assert len(tweets) == 3

    assert tweets[0]["id"] == "99900001"
    assert "香港用户" in tweets[0]["author"]
    assert "香港今日天气晴朗" in tweets[0]["text"]

    assert tweets[1]["id"] == "99900002"
    assert "News HK" in tweets[1]["author"]
    assert "Hong Kong news" in tweets[1]["text"]

    assert tweets[2]["id"] == "99900003"


def test_parse_search_results_respects_limit():
    page = _search_page()
    assert len(_parse_tweets(page, limit=2)) == 2