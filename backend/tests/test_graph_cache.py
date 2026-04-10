"""
Tests for app.core.graph_cache — TTL graph cache with asyncio.Lock.

TDD order: write tests → RED → implement → GREEN.
"""

import asyncio
import time
import pytest
from unittest.mock import MagicMock, patch

import app.core.graph_cache as graph_cache_module


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_mock_graph(name: str = "graph") -> MagicMock:
    g = MagicMock()
    g.name = name
    return g


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def clear_cache():
    """Clear the module-level TTLCache before and after each test."""
    graph_cache_module._cache.clear()
    yield
    graph_cache_module._cache.clear()


# ---------------------------------------------------------------------------
# Cache miss / hit
# ---------------------------------------------------------------------------

class TestCacheMissAndHit:

    @pytest.mark.asyncio
    async def test_cache_miss_calls_build_graph_once(self):
        """On cache miss, build_graph is called exactly once with the given api_key."""
        mock_graph = _make_mock_graph("fresh")
        with patch("app.core.graph_cache.build_graph", return_value=mock_graph) as mock_build:
            result = await graph_cache_module.get_or_build_graph("user-1", "sk-test")
            assert result is mock_graph
            mock_build.assert_called_once_with("sk-test")

    @pytest.mark.asyncio
    async def test_cache_hit_returns_same_graph_without_rebuilding(self):
        """Second call for the same user_id returns cached graph — build_graph NOT called again."""
        mock_graph = _make_mock_graph("cached")
        with patch("app.core.graph_cache.build_graph", return_value=mock_graph) as mock_build:
            first = await graph_cache_module.get_or_build_graph("user-1", "sk-test")
            second = await graph_cache_module.get_or_build_graph("user-1", "sk-test")
            assert first is second is mock_graph
            mock_build.assert_called_once()  # NOT twice

    @pytest.mark.asyncio
    async def test_different_user_ids_get_different_cache_entries(self):
        """Each user_id is a separate cache key — build_graph called once per user."""
        graph_a = _make_mock_graph("graph-a")
        graph_b = _make_mock_graph("graph-b")
        graphs = iter([graph_a, graph_b])

        with patch("app.core.graph_cache.build_graph", side_effect=lambda _: next(graphs)) as mock_build:
            result_a = await graph_cache_module.get_or_build_graph("user-a", "sk-test")
            result_b = await graph_cache_module.get_or_build_graph("user-b", "sk-test")

            assert result_a is graph_a
            assert result_b is graph_b
            assert result_a is not result_b
            assert mock_build.call_count == 2


# ---------------------------------------------------------------------------
# TTL expiry
# ---------------------------------------------------------------------------

class TestTTLExpiry:

    @pytest.mark.asyncio
    async def test_expired_entry_triggers_rebuild(self):
        """After TTL expires, next access rebuilds the graph (cache miss again)."""
        from cachetools import TTLCache

        original_cache = graph_cache_module._cache
        # Use a tiny TTL so we can expire it in the test
        graph_cache_module._cache = TTLCache(maxsize=100, ttl=0.05)  # 50 ms

        try:
            graph_v1 = _make_mock_graph("v1")
            graph_v2 = _make_mock_graph("v2")
            graphs = iter([graph_v1, graph_v2])

            with patch("app.core.graph_cache.build_graph", side_effect=lambda _: next(graphs)) as mock_build:
                first = await graph_cache_module.get_or_build_graph("user-1", "sk-test")
                assert first is graph_v1

                time.sleep(0.1)  # wait past TTL (50 ms)

                second = await graph_cache_module.get_or_build_graph("user-1", "sk-test")
                assert second is graph_v2
                assert mock_build.call_count == 2
        finally:
            graph_cache_module._cache = original_cache


# ---------------------------------------------------------------------------
# Concurrency — thundering herd protection
# ---------------------------------------------------------------------------

class TestConcurrency:

    @pytest.mark.asyncio
    async def test_concurrent_cache_misses_call_build_graph_only_once(self):
        """
        When multiple coroutines race to build the same user_id simultaneously,
        asyncio.Lock ensures build_graph is called exactly once — no thundering herd.
        """
        build_count = 0

        def counting_build(api_key: str) -> MagicMock:
            nonlocal build_count
            build_count += 1
            return _make_mock_graph(f"graph-{build_count}")

        with patch("app.core.graph_cache.build_graph", side_effect=counting_build):
            results = await asyncio.gather(
                graph_cache_module.get_or_build_graph("user-concurrent", "sk-test"),
                graph_cache_module.get_or_build_graph("user-concurrent", "sk-test"),
                graph_cache_module.get_or_build_graph("user-concurrent", "sk-test"),
                graph_cache_module.get_or_build_graph("user-concurrent", "sk-test"),
                graph_cache_module.get_or_build_graph("user-concurrent", "sk-test"),
            )

        # build_graph must have been called exactly once
        assert build_count == 1
        # Every coroutine must have received the same graph instance
        assert all(r is results[0] for r in results)
