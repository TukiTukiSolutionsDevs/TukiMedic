"""
Redis sliding window memory — Level 1.

Stores the last WINDOW_SIZE messages per (user_id, case_id) pair.
Uses a Redis LIST with RPUSH + LTRIM for O(1) sliding window writes.
TTL resets on every write so active sessions stay alive.
"""

import json

import redis.asyncio as aioredis

from app.core.config import settings

# ---------------------------------------------------------------------------
# Module-level async redis client (separate from the sync client in core/redis.py
# which is used for rate limiting).  Tests patch this name directly.
# ---------------------------------------------------------------------------
redis_client: aioredis.Redis = aioredis.from_url(
    settings.REDIS_URL, decode_responses=True
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
KEY_PREFIX = "medagent:memory"
WINDOW_SIZE = 20       # total messages (10 user + 10 assistant exchanges)
TTL_SECONDS = 7200     # 2 h idle timeout; resets on every write


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _key(user_id: str, case_id: str) -> str:
    """Build a namespaced, user-scoped Redis key."""
    return f"{KEY_PREFIX}:{user_id}:{case_id}"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def load_messages(user_id: str, case_id: str) -> list[dict]:
    """
    Return the last WINDOW_SIZE messages for this (user, case) pair.

    Returns an empty list if the key does not exist or has no messages.
    """
    key = _key(user_id, case_id)
    raw: list[str] = await redis_client.lrange(key, 0, -1)
    return [json.loads(m) for m in raw]


async def append_messages(
    user_id: str,
    case_id: str,
    user_content: str,
    assistant_content: str,
) -> None:
    """
    Append one exchange (user + assistant) to the sliding window.

    Operations (in order):
      1. RPUSH  — append both messages atomically
      2. LTRIM  — keep only the last WINDOW_SIZE messages
      3. EXPIRE — reset TTL so active sessions don't expire mid-conversation
    """
    key = _key(user_id, case_id)
    user_msg = json.dumps({"role": "user", "content": user_content})
    assistant_msg = json.dumps({"role": "assistant", "content": assistant_content})

    await redis_client.rpush(key, user_msg, assistant_msg)
    await redis_client.ltrim(key, -WINDOW_SIZE, -1)
    await redis_client.expire(key, TTL_SECONDS)


async def clear_messages(user_id: str, case_id: str) -> None:
    """Delete all stored messages for this (user, case) pair."""
    key = _key(user_id, case_id)
    await redis_client.delete(key)
