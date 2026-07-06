"""Tests for server.service orchestration layer."""

from pathlib import Path
from unittest.mock import patch

import pytest

from server.db import Database
from server.service import run_manual_search


@pytest.fixture
def db(tmp_path: Path) -> Database:
    _db = Database(str(tmp_path / "test.db"))
    _db.connect()
    yield _db
    _db.close()


def fake_fetch_user_tweets(handle: str, limit: int = 10) -> list[dict]:
    return [{
        "id": f"user_{handle}_1",
        "text": f"Tweet from {handle}",
        "time": "2026-07-04T10:00:00Z",
        "author": handle,
    }]


def fake_search_tweets(keywords=None, from_users=None, query=None, sort="top",
                       limit=20, since=None, until=None) -> list[dict]:
    kw = (keywords or ["unknown"])[0]
    return [{
        "id": f"kw_{kw}_1",
        "text": f"About {kw}",
        "time": "2026-07-04T10:00:00Z",
        "author": "someone",
    }]


@patch("server.service.fetch_user_tweets", fake_fetch_user_tweets)
def test_run_manual_search_users(db):
    """Manual search for a list of users returns 1 tweet each, merged."""
    tweets = run_manual_search(
        query_type="user",
        keywords="",
        users="elonmusk,lexfridman",
        limit=1,
        db=db,
    )
    assert len(tweets) == 2
    user_ids = {t["author"] for t in tweets}
    assert user_ids == {"elonmusk", "lexfridman"}


@patch("server.service.search_tweets", fake_search_tweets)
def test_run_manual_search_keywords(db):
    """Manual search for multiple keywords returns merged results."""
    tweets = run_manual_search(
        query_type="keyword",
        keywords="AI,GPT",
        users="",
        limit=10,
        db=db,
    )
    assert len(tweets) == 2
    texts = {t["text"] for t in tweets}
    assert "About AI" in texts
    assert "About GPT" in texts


@patch("server.service.search_tweets", fake_search_tweets)
def test_run_manual_search_creates_log(db):
    run_manual_search(
        query_type="keyword",
        keywords="AI",
        users="",
        limit=10,
        db=db,
    )
    stats = db.get_stats()
    assert stats is not None


@patch("server.service.fetch_user_tweets", lambda h, limit=10: [])
def test_run_manual_search_empty_result(db):
    tweets = run_manual_search("user", "", "nobody", limit=1, db=db)
    assert tweets == []


def test_run_manual_search_no_params(db):
    tweets = run_manual_search("keyword", "", "", limit=1, db=db)
    assert tweets == []


@patch("server.service.fetch_user_tweets", lambda h, limit=10: [
    {"id": "dup_1", "text": "a", "time": "2026-01-01T00:00:00Z", "author": h},
    {"id": "dup_1", "text": "a", "time": "2026-01-01T00:00:00Z", "author": h},
])
def test_run_manual_search_dedup(db):
    """Even if spider returns duplicates, service deduplicates."""
    tweets = run_manual_search("user", "", "user1", limit=10, db=db)
    assert len(tweets) == 1
