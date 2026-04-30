"""
Global test fixtures for the medagent backend test suite.
"""
import base64
import os
import secrets

# Force strong, deterministic-per-process secrets BEFORE any `app.*` import.
# The validators in `app.core.config` and `app.core.crypto` reject missing /
# placeholder values at import time, which would otherwise prevent collection.
os.environ.setdefault("ENVIRONMENT", "test")
os.environ["SECRET_KEY"] = secrets.token_urlsafe(48)
# AES-256-GCM master key for the encrypted credential vault (S4.0.c).
os.environ["VAULT_MASTER_KEY"] = base64.b64encode(os.urandom(32)).decode()

import pytest  # noqa: E402
from unittest.mock import AsyncMock, MagicMock, patch  # noqa: E402


# ---------------------------------------------------------------------------
# @live_llm marker — opt-in tests that hit a real LLM endpoint
# (e.g. Meridian shim on http://localhost:4568/v1, OpenAI, Anthropic).
#
# By default these are SKIPPED. Enable with RUN_LIVE_LLM=1 or by passing
# --live-llm. Use sparingly: they cost tokens and depend on network.
# ---------------------------------------------------------------------------


def pytest_addoption(parser):
    parser.addoption(
        "--live-llm",
        action="store_true",
        default=False,
        help="Run tests marked @pytest.mark.live_llm (real LLM calls).",
    )


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "live_llm: marks tests that hit a real LLM endpoint (deselect with -m 'not live_llm')",
    )


def pytest_collection_modifyitems(config, items):
    """Skip @live_llm tests unless --live-llm or RUN_LIVE_LLM=1."""
    enabled = config.getoption("--live-llm") or os.environ.get("RUN_LIVE_LLM") == "1"
    if enabled:
        return
    skip_live = pytest.mark.skip(
        reason="live_llm: pass --live-llm or set RUN_LIVE_LLM=1 to enable"
    )
    for item in items:
        if "live_llm" in item.keywords:
            item.add_marker(skip_live)


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
