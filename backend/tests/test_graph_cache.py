"""
Tests for app.core.graph_cache — TTL graph cache with asyncio.Lock.

S4.0.d-5: Updated for router-backed build — get_or_build_graph no longer
takes api_key; get_active_credential is mocked in all cache tests.
"""

import asyncio
import time
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

import app.core.graph_cache as graph_cache_module
from app.services.llm_router import ProviderCredentialDTO


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_mock_graph(name: str = "graph") -> MagicMock:
    g = MagicMock()
    g.name = name
    return g


def _make_cred(api_key: str = "sk-test") -> ProviderCredentialDTO:
    return ProviderCredentialDTO(provider="gemini", api_key=api_key, base_url=None)


def _cred_patch(cred: ProviderCredentialDTO | None = None):
    """Patch get_active_credential to return a mock DTO (no DB hit)."""
    return patch(
        "app.core.graph_cache.get_active_credential",
        AsyncMock(return_value=cred or _make_cred()),
    )


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
        """On cache miss, get_active_credential + build_graph called exactly once."""
        mock_graph = _make_mock_graph("fresh")
        mock_cred = _make_cred()
        with _cred_patch(mock_cred):
            with patch("app.core.graph_cache.build_graph", return_value=mock_graph) as mock_build:
                result = await graph_cache_module.get_or_build_graph("user-1")
                assert result is mock_graph
                mock_build.assert_called_once_with(mock_cred)

    @pytest.mark.asyncio
    async def test_cache_hit_returns_same_graph_without_rebuilding(self):
        """Second call for same user_id returns cached graph — no rebuild."""
        mock_graph = _make_mock_graph("cached")
        with _cred_patch():
            with patch("app.core.graph_cache.build_graph", return_value=mock_graph) as mock_build:
                first = await graph_cache_module.get_or_build_graph("user-1")
                second = await graph_cache_module.get_or_build_graph("user-1")
                assert first is second is mock_graph
                mock_build.assert_called_once()  # NOT twice

    @pytest.mark.asyncio
    async def test_different_user_ids_get_different_cache_entries(self):
        """Each user_id is a separate cache key — build_graph called once per user."""
        graph_a = _make_mock_graph("graph-a")
        graph_b = _make_mock_graph("graph-b")
        graphs = iter([graph_a, graph_b])

        with _cred_patch():
            with patch("app.core.graph_cache.build_graph", side_effect=lambda _: next(graphs)) as mock_build:
                result_a = await graph_cache_module.get_or_build_graph("user-a")
                result_b = await graph_cache_module.get_or_build_graph("user-b")

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
        graph_cache_module._cache = TTLCache(maxsize=100, ttl=0.05)  # 50 ms

        try:
            graph_v1 = _make_mock_graph("v1")
            graph_v2 = _make_mock_graph("v2")
            graphs = iter([graph_v1, graph_v2])

            with _cred_patch():
                with patch("app.core.graph_cache.build_graph", side_effect=lambda _: next(graphs)) as mock_build:
                    first = await graph_cache_module.get_or_build_graph("user-1")
                    assert first is graph_v1

                    time.sleep(0.1)  # wait past TTL (50 ms)

                    second = await graph_cache_module.get_or_build_graph("user-1")
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
        Multiple coroutines racing on same user_id → build_graph called once.
        asyncio.Lock prevents thundering herd.
        """
        build_count = 0

        def counting_build(cred: ProviderCredentialDTO) -> MagicMock:
            nonlocal build_count
            build_count += 1
            return _make_mock_graph(f"graph-{build_count}")

        with _cred_patch():
            with patch("app.core.graph_cache.build_graph", side_effect=counting_build):
                results = await asyncio.gather(
                    graph_cache_module.get_or_build_graph("user-concurrent"),
                    graph_cache_module.get_or_build_graph("user-concurrent"),
                    graph_cache_module.get_or_build_graph("user-concurrent"),
                    graph_cache_module.get_or_build_graph("user-concurrent"),
                    graph_cache_module.get_or_build_graph("user-concurrent"),
                )

        assert build_count == 1
        assert all(r is results[0] for r in results)


# ---------------------------------------------------------------------------
# S4.0.d-5: Cache invalidation — clear() wipes all entries
# ---------------------------------------------------------------------------


class TestCacheClear:
    @pytest.mark.asyncio
    async def test_clear_empties_cache(self):
        """clear() removes all cached entries."""
        mock_graph = _make_mock_graph("to-be-cleared")
        with _cred_patch():
            with patch("app.core.graph_cache.build_graph", return_value=mock_graph):
                await graph_cache_module.get_or_build_graph("user-1")
                assert "user-1" in graph_cache_module._cache

        graph_cache_module.clear()
        assert len(graph_cache_module._cache) == 0

    @pytest.mark.asyncio
    async def test_clear_forces_rebuild_on_next_access(self):
        """After clear(), next get_or_build_graph triggers a fresh build."""
        graph_v1 = _make_mock_graph("v1")
        graph_v2 = _make_mock_graph("v2")
        graphs = iter([graph_v1, graph_v2])

        with _cred_patch():
            with patch("app.core.graph_cache.build_graph", side_effect=lambda _: next(graphs)) as mock_build:
                first = await graph_cache_module.get_or_build_graph("user-1")
                assert first is graph_v1
                assert mock_build.call_count == 1

                graph_cache_module.clear()

                second = await graph_cache_module.get_or_build_graph("user-1")
                assert second is graph_v2
                assert mock_build.call_count == 2
