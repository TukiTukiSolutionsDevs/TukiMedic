"""
E2E — Test 3: WebSocket rate limiting is Redis-backed.

Patches RATE_LIMIT_MAX=3 / RATE_LIMIT_WINDOW=10s so the test runs in <15s.
Sends 4 messages over one WS connection — the 4th must be rate_limited.

Assertions:
  ✓ 4th message returns error with code=rate_limited
  ✓ Redis key ws:ratelimit:{user_id} exists with count > 3
  ✓ Redis TTL is set (key will eventually expire)
  ✓ A fresh redis.asyncio client sees the same count (state is Redis-backed,
    not in-process memory)
"""
from __future__ import annotations

import pytest
import redis.asyncio as redis_aio
import websockets

import app.api.v1.chat as chat_mod
from tests.integration.e2e._helpers import ws_auth, ws_message


@pytest.fixture(autouse=True)
def _lower_rate_limit():
    """Reduce limits so the test stays well under 30 s."""
    orig_max = chat_mod.RATE_LIMIT_MAX
    orig_window = chat_mod.RATE_LIMIT_WINDOW
    chat_mod.RATE_LIMIT_MAX = 3
    chat_mod.RATE_LIMIT_WINDOW = 10
    yield
    chat_mod.RATE_LIMIT_MAX = orig_max
    chat_mod.RATE_LIMIT_WINDOW = orig_window


@pytest.mark.integration
async def test_ws_chat_rate_limit(
    ws_url,
    seed_user,
    e2e_redis_client,
    e2e_redis_url,
):
    user, token = await seed_user()
    user_id = str(user.id)
    rate_key = f"ws:ratelimit:{user_id}"

    # Ensure no leftover counter from a previous test run
    await e2e_redis_client.delete(rate_key)

    rate_limited: list[dict] = []
    succeeded: list[dict] = []

    async with websockets.connect(ws_url + "/api/v1/chat/ws") as ws:
        auth_resp = await ws_auth(ws, token)
        assert auth_resp["type"] == "auth_ok", f"Auth failed: {auth_resp}"

        # Send 4 messages — first 3 should succeed, 4th rate_limited
        for i in range(4):
            frames = await ws_message(ws, f"Consulta número {i + 1}")
            for frame in frames:
                if frame.get("type") == "error" and frame.get("code") == "rate_limited":
                    rate_limited.append(frame)
                elif frame.get("type") == "done":
                    succeeded.append(frame)

    # ── Assertion 1: at least one rate_limited response ───────────────
    assert rate_limited, (
        f"Expected rate_limited error after {chat_mod.RATE_LIMIT_MAX} messages, "
        f"got none. succeeded={len(succeeded)} frames."
    )
    assert rate_limited[0]["code"] == "rate_limited"

    # ── Assertion 2: first N messages succeeded ───────────────────────
    assert len(succeeded) >= chat_mod.RATE_LIMIT_MAX, (
        f"Expected at least {chat_mod.RATE_LIMIT_MAX} successful messages "
        f"before rate limit, got {len(succeeded)}."
    )

    # ── Assertion 3: Redis key holds count > limit ────────────────────
    count_raw = await e2e_redis_client.get(rate_key)
    assert count_raw is not None, (
        f"Rate limit key '{rate_key}' not found in Redis. "
        "The WS rate limiter must use Redis (not in-process memory)."
    )
    assert int(count_raw) > chat_mod.RATE_LIMIT_MAX, (
        f"Redis counter={count_raw}, expected > {chat_mod.RATE_LIMIT_MAX}. "
        "Counter may have expired or was never set."
    )

    # ── Assertion 4: TTL is set (key expires after window) ───────────
    ttl = await e2e_redis_client.ttl(rate_key)
    assert ttl > 0, (
        f"Rate limit key has no TTL (ttl={ttl}). "
        "Without a TTL the limit never resets."
    )
    assert ttl <= chat_mod.RATE_LIMIT_WINDOW, (
        f"TTL={ttl} exceeds window={chat_mod.RATE_LIMIT_WINDOW}. "
        "EXPIRE may have been called with the wrong value."
    )

    # ── Assertion 5: state is Redis-backed (second client sees same count)
    # Create a brand-new client with no shared connection state — if the
    # counter were stored in-process (MemoryStorage) this would return None.
    fresh = redis_aio.from_url(e2e_redis_url, decode_responses=True)
    count_fresh = await fresh.get(rate_key)
    await fresh.aclose()
    assert count_fresh is not None, (
        "Second Redis client cannot see the rate limit key — "
        "limit is stored in-process, not in Redis."
    )
    assert int(count_fresh) == int(count_raw), (
        f"Second client count ({count_fresh}) != first ({count_raw}). "
        "Possible race condition or two separate counters."
    )
