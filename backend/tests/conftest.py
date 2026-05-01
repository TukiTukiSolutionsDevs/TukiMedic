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
    parser.addoption(
        "--integration",
        action="store_true",
        default=False,
        help="Run tests marked @pytest.mark.integration (require Docker/testcontainers).",
    )


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "live_llm: marks tests that hit a real LLM endpoint (deselect with -m 'not live_llm')",
    )
    config.addinivalue_line(
        "markers",
        "integration: marks tests that require Docker/testcontainers "
        "(run with --integration or RUN_INTEGRATION=1)",
    )


def pytest_collection_modifyitems(config, items):
    """Skip @live_llm and @integration tests unless explicitly enabled."""
    run_live_llm = config.getoption("--live-llm") or os.environ.get("RUN_LIVE_LLM") == "1"
    run_integration = config.getoption("--integration") or os.environ.get("RUN_INTEGRATION") == "1"

    skip_live = pytest.mark.skip(
        reason="live_llm: pass --live-llm or set RUN_LIVE_LLM=1 to enable"
    )
    skip_integration = pytest.mark.skip(
        reason="integration: pass --integration or set RUN_INTEGRATION=1 to enable"
    )

    for item in items:
        if "live_llm" in item.keywords and not run_live_llm:
            item.add_marker(skip_live)
        if "integration" in item.keywords and not run_integration:
            item.add_marker(skip_integration)


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


@pytest.fixture(autouse=True)
def _stub_llm_safe_sleep():
    """Make `safe_ainvoke` retry sleeps instant in unit tests.

    `app.agents._llm_safe.safe_ainvoke` retries transient upstream errors
    with an exponential backoff (1s/3s/9s plus jitter). In production this
    cushions Gemini 503 hiccups; in unit tests it would add ~13s per error
    case (we have ~10 such tests in `test_llm_error_handling.py` →
    ~2 minutes of dead wait). Patching the indirected sleep keeps the suite
    fast without altering the retry attempt count.

    Tests that need to inspect the sleep schedule itself (see
    `tests/test_llm_safe_retry.py::test_backoff_delays_follow_exponential_schedule`)
    re-patch `_async_sleep` locally; the inner patch wins over this autouse.
    """
    from app.agents import _llm_safe

    with patch.object(_llm_safe, "_async_sleep", new=AsyncMock(return_value=None)):
        yield


@pytest.fixture(autouse=True, scope="session")
def _mock_rate_limiter_storage():
    """Replace slowapi's RedisStorage with MemoryStorage for the test session.

    Production code sets storage_uri=REDIS_URL on the Limiter, which creates a
    RedisStorage. Tests must not require a live Redis connection for rate limiting.
    Swapping to MemoryStorage preserves all auth tests that call limiter.reset()
    between runs.

    test_rate_limit.py checks limiter._storage_uri (the configured URI), not the
    runtime storage object, so this swap does not affect that assertion.
    """
    from limits.storage import MemoryStorage

    from app.core.rate_limit import limiter

    mem = MemoryStorage()
    orig_storage = limiter._storage
    orig_limiter_storage = limiter._limiter.storage

    limiter._storage = mem
    limiter._limiter.storage = mem

    yield

    limiter._storage = orig_storage
    limiter._limiter.storage = orig_limiter_storage
