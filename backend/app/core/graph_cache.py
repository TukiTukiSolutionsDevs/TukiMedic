"""
Graph cache — TTL-based cache for compiled LangGraph instances.

Prevents rebuilding the graph on every WebSocket message.
Uses asyncio.Lock to avoid thundering herd on concurrent cache misses.

On credential write/rotate/activate/delete, call clear() so the next request
picks up the new active credential via the LLM router.
"""

import asyncio

from cachetools import TTLCache

from app.orchestrator.graph import build_graph
from app.services.llm_router import get_active_credential

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

def clear() -> None:
    """Evict all cached graph instances.

    Called by credential write/activate/rotate/delete endpoints so the LLM
    router picks up the new active credential on the next request.
    """
    _cache.clear()


async def get_or_build_graph(user_id: str):
    """Return a compiled LangGraph for user_id, building fresh if missing or expired.

    On cache miss, resolves the active provider credential from the vault
    via ``get_active_credential()`` and builds a new graph with it.

    Args:
        user_id: Cache key — one graph per user.

    Returns:
        Compiled LangGraph StateGraph ready for astream_events().

    Raises:
        NoActiveCredentialError: propagated from get_active_credential() if
            no active credential is configured. Caller should handle as 503.

    Thread safety:
        asyncio.Lock serialises concurrent coroutines on cache miss.
        Only the first coroutine calls build_graph; the rest get the cached result.
    """
    async with _lock:
        if user_id in _cache:
            return _cache[user_id]
        cred = await get_active_credential()   # defaults to "gemini"
        graph = build_graph(cred)
        _cache[user_id] = graph
        return graph
