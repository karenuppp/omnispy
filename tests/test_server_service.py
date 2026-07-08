"""Tests for server service layer — multi-route search, merge dedup."""

from unittest.mock import patch

import pytest


class TestExpandQueries:
    """_expand_queries: each keyword → 4 routes"""

    def test_expand_single_keyword(self):
        from server.service import _expand_queries
        queries = _expand_queries(["AI"])
        assert len(queries) == 4
        sorts = {q["sort"] for q in queries}
        assert sorts == {"top", "live"}
        qstrings = {q["q"] for q in queries}
        assert qstrings == {"AI", "#AI"}

    def test_expand_multiple_keywords(self):
        from server.service import _expand_queries
        queries = _expand_queries(["AI", "GPT"])
        assert len(queries) == 8
        assert all(q["sort"] in ("top", "live") for q in queries)

    def test_expand_strips_whitespace(self):
        from server.service import _expand_queries
        queries = _expand_queries(["  AI ", "GPT "])
        assert len(queries) == 8

    def test_expand_empty_list(self):
        from server.service import _expand_queries
        assert _expand_queries([]) == []


class TestMergeDedup:
    """_merge_and_dedup: merge multi-route results, remove duplicates"""

    def test_merge_no_duplicates(self):
        from server.service import _merge_and_dedup
        results = [
            {"id": "1", "text": "a"},
            {"id": "2", "text": "b"},
            {"id": "3", "text": "c"},
        ]
        merged = _merge_and_dedup(results)
        assert len(merged) == 3

    def test_merge_removes_duplicates(self):
        from server.service import _merge_and_dedup
        results = [
            {"id": "1", "text": "a"},
            {"id": "2", "text": "b"},
            {"id": "1", "text": "a"},
        ]
        merged = _merge_and_dedup(results)
        assert len(merged) == 2
        assert [t["id"] for t in merged] == ["1", "2"]

    def test_merge_preserves_first_seen_order(self):
        from server.service import _merge_and_dedup
        results = [
            {"id": "3", "text": "third"},
            {"id": "1", "text": "first"},
            {"id": "2", "text": "second"},
            {"id": "1", "text": "first"},
        ]
        merged = _merge_and_dedup(results)
        assert [t["id"] for t in merged] == ["3", "1", "2"]

    def test_merge_skips_missing_id(self):
        from server.service import _merge_and_dedup
        results = [
            {"id": "1", "text": "a"},
            {"no_id": True},
            {"id": "2", "text": "b"},
        ]
        merged = _merge_and_dedup(results)
        assert len(merged) == 2
        assert merged[0]["id"] == "1"
        assert merged[-1]["id"] == "2"


class TestMultiSearch:
    """_multi_search: concurrent dispatch + merge dedup"""

    def test_dispatches_all_queries(self):
        from server.service import _multi_search

        dispatched = []

        def fake_search_tweets(keywords, sort, limit, since, until):
            dispatched.append((keywords[0], sort))
            return []

        with patch("server.service.search_tweets", fake_search_tweets):
            _multi_search(
                keywords=["AI"],
                since="2026-07-07",
                until="2026-07-08",
                limit_per_route=5,
            )

        assert len(dispatched) == 4  # 4 routes per keyword

    def test_merged_and_deduped(self):
        from server.service import _multi_search

        call_count = 0

        def fake_search_tweets(keywords, sort, limit, since, until):
            nonlocal call_count
            call_count += 1
            return [
                {"id": "1", "text": f"found in route {call_count}", "author": "U", "time": "2026-07-07T12:00:00Z"},
            ]

        with patch("server.service.search_tweets", fake_search_tweets):
            results = _multi_search(
                keywords=["AI"],
                since="2026-07-06",
                limit_per_route=10,
            )

        assert len(results) == 1  # deduped to 1
        assert results[0]["id"] == "1"

    def test_empty_results(self):
        from server.service import _multi_search

        def fake_search_tweets(keywords, sort, limit, since, until):
            return []

        with patch("server.service.search_tweets", fake_search_tweets):
            results = _multi_search(keywords=["AI"])
            assert results == []

    def test_dispatches_multiple_keywords(self):
        from server.service import _multi_search

        dispatched = []

        def fake_search_tweets(keywords, sort, limit, since, until):
            dispatched.append(keywords[0])
            return []

        with patch("server.service.search_tweets", fake_search_tweets):
            _multi_search(keywords=["AI", "GPT"], limit_per_route=5)

        assert len(dispatched) == 8  # 2 keywords × 4 routes
