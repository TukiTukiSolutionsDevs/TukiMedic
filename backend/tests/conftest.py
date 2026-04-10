"""
Global test fixtures for the medagent backend test suite.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.fixture(autouse=True)
def mock_memory_redis_client():
    """
    Prevent real Redis connections in ALL tests.

    redis_window.redis_client is a module-level async Redis client created at
    import time.  Any test that exercises code paths touching chat.py (which
    calls load_messages) will fail with ConnectionError unless this client is
    patched.

    Tests that need specific return values (test_redis_memory.py) override this
    fixture locally via patch.object(rw, "redis_client", my_mock) — that context
    manager takes precedence inside its own scope.
    """
    mock_r = MagicMock()
    mock_r.lrange = AsyncMock(return_value=[])
    mock_r.rpush = AsyncMock(return_value=2)
    mock_r.ltrim = AsyncMock(return_value=True)
    mock_r.expire = AsyncMock(return_value=True)
    mock_r.delete = AsyncMock(return_value=1)

    with patch("app.memory.redis_window.redis_client", mock_r):
        yield mock_r
