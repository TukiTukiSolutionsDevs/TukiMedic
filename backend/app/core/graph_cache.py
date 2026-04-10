"""
Graph cache — TTL-based cache for compiled LangGraph instances.

Prevents rebuilding the graph on every WebSocket message.
Uses asyncio.Lock to avoid thundering herd on concurrent cache misses.

MVP: one server-wide API key → cache key is user_id only.
Future BYOK: cache key becomes sha256(user_id + api_key).
"""

import asyncio

from cachetools import TTLCache

from app.orchestrator.graph import build_graph

# ---------------------------------------------------------------------------
# Module-level constants (patchable in tests)
# ---------------------------------------------------------------------------

CACHE_TTL = 300      # seconds — 5 min idle eviction
CACHE_MAXSIZE = 100  # max concurrent user graphs in RAM

# ---------------------------------------------------------------------------
# Module-level state (NOT thread-safe — protected by asyncio.Lock)
# ---------------------------------------------------------------------------

_cache: TTLCache = TTLCache(maxsize=CACHE_MAXSIZE, ttl=CACHE_TTL)
_lock: asyncio.Lock = asyncio.Lock()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def get_or_build_graph(user_id: str, api_key: str):
    """Return a compiled LangGraph for user_id, building fresh if missing or expired.

    Args:
        user_id: Cache key — one graph per user.
        api_key: Passed to build_graph on cache miss (server-wide in MVP).

    Returns:
        Compiled LangGraph StateGraph ready for astream_events().

    Thread safety:
        asyncio.Lock serialises concurrent coroutines on cache miss.
        Only the first coroutine calls build_graph; the rest get the cached result.
    """
    async with _lock:
        if user_id in _cache:
            return _cache[user_id]
        graph = build_graph(api_key)
        _cache[user_id] = graph
        return graph
