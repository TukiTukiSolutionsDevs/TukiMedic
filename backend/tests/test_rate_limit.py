"""
TDD — Rate limiter: must be configured with Redis storage URI.

Strict TDD: written BEFORE the fix. Fails while Limiter uses the default
MemoryStorage (no storage_uri). Passes once storage_uri=settings.REDIS_URL
is set in app/core/rate_limit.py.

Why this matters: MemoryStorage is per-process. In a multi-worker/multi-replica
deployment each instance maintains its own counter, so the rate limit is never
enforced globally. Redis provides a shared, atomic counter for all replicas.

Note: conftest._mock_rate_limiter_storage replaces _storage with MemoryStorage
in tests so auth tests (limiter.reset()) never need a live Redis connection.
This test checks _storage_uri (the configured URI), not the runtime storage
object — so the conftest swap does not affect this assertion.

Run: cd backend && poetry run pytest tests/test_rate_limit.py -v
"""


def test_limiter_configured_with_redis_storage_uri():
    """Limiter must have storage_uri set to a Redis URI — not in-memory default.

    RED: _storage_uri is None  (Limiter(key_func=...) with no storage_uri)
    GREEN: _storage_uri starts with redis://  (after adding storage_uri=settings.REDIS_URL)
    """
    from app.core.rate_limit import limiter

    uri = getattr(limiter, "_storage_uri", None)
    assert uri is not None, (
        "Limiter._storage_uri is None — the limiter is using in-memory (per-process) "
        "storage. Add storage_uri=settings.REDIS_URL to the Limiter constructor in "
        "app/core/rate_limit.py to share counters across replicas."
    )
    assert "redis://" in str(uri).lower(), (
        f"Expected a redis:// URI in _storage_uri, got: {uri!r}"
    )
