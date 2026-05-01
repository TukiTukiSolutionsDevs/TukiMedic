"""
Retry behavior for `safe_ainvoke` — exponential backoff for transient LLM errors.

Provider stack: `langchain_openai.ChatOpenAI` against the Gemini OpenAI-compat
endpoint. Transient errors are surfaced as `openai.*` (NOT `google.api_core.*`).

Categories:
- Transient (RETRY): 5xx HTTP, RateLimitError (429), APITimeoutError,
  APIConnectionError, asyncio.TimeoutError.
- Permanent (FAIL-FAST → fallback): 4xx (BadRequest/Auth/Permission),
  pydantic.ValidationError, generic Exception.
"""
from __future__ import annotations

import asyncio
import logging
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import openai
import pytest

from app.agents import _llm_safe
from app.agents._llm_safe import safe_ainvoke


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _http_response(code: int) -> httpx.Response:
    return httpx.Response(
        status_code=code,
        request=httpx.Request("POST", "http://x"),
    )


def _status_err(code: int) -> openai.APIStatusError:
    """Build a real openai.APIStatusError with the given HTTP status."""
    return openai.APIStatusError(
        message=f"http {code}",
        response=_http_response(code),
        body=None,
    )


@pytest.fixture(autouse=True)
def _no_sleep():
    """Make the backoff sleeps instant inside this module.

    Uses ``create=True`` so the RED commit (where ``_async_sleep`` doesn't
    exist yet on the module) still imports cleanly. Once the GREEN commit
    lands the attribute exists and the patch is a real no-op replacement.
    """
    with patch.object(
        _llm_safe, "_async_sleep", new=AsyncMock(return_value=None), create=True
    ):
        yield


# ---------------------------------------------------------------------------
# Mandatory RED tests (4)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_returns_result_on_first_success():
    llm = MagicMock()
    llm.ainvoke = AsyncMock(return_value="ok")

    out = await safe_ainvoke(llm, "p", fallback="FB", agent_name="t")

    assert out == "ok"
    assert llm.ainvoke.await_count == 1


@pytest.mark.asyncio
async def test_retries_on_503_then_succeeds():
    llm = MagicMock()
    llm.ainvoke = AsyncMock(
        side_effect=[_status_err(503), _status_err(503), "ok"]
    )

    out = await safe_ainvoke(llm, "p", fallback="FB", agent_name="t")

    assert out == "ok"
    assert llm.ainvoke.await_count == 3


@pytest.mark.asyncio
async def test_returns_fallback_after_retries_exhausted():
    llm = MagicMock()
    # 4 attempts max (1 original + 3 retries). All fail with 503.
    llm.ainvoke = AsyncMock(side_effect=[_status_err(503)] * 4)

    out = await safe_ainvoke(llm, "p", fallback="FB", agent_name="t")

    assert out == "FB"
    assert llm.ainvoke.await_count == 4


@pytest.mark.asyncio
async def test_does_not_retry_on_400_bad_request():
    llm = MagicMock()
    llm.ainvoke = AsyncMock(side_effect=_status_err(400))

    out = await safe_ainvoke(llm, "p", fallback="FB", agent_name="t")

    assert out == "FB"
    assert llm.ainvoke.await_count == 1


# ---------------------------------------------------------------------------
# Recommended RED tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_retries_on_rate_limit_429():
    llm = MagicMock()
    err = openai.RateLimitError(
        message="429",
        response=_http_response(429),
        body=None,
    )
    llm.ainvoke = AsyncMock(side_effect=[err, "ok"])

    out = await safe_ainvoke(llm, "p", fallback="FB", agent_name="t")

    assert out == "ok"
    assert llm.ainvoke.await_count == 2


@pytest.mark.asyncio
async def test_retries_on_asyncio_timeout():
    llm = MagicMock()
    llm.ainvoke = AsyncMock(side_effect=[asyncio.TimeoutError(), "ok"])

    out = await safe_ainvoke(llm, "p", fallback="FB", agent_name="t")

    assert out == "ok"
    assert llm.ainvoke.await_count == 2


@pytest.mark.asyncio
async def test_retries_on_api_connection_error():
    llm = MagicMock()
    err = openai.APIConnectionError(request=httpx.Request("POST", "http://x"))
    llm.ainvoke = AsyncMock(side_effect=[err, "ok"])

    out = await safe_ainvoke(llm, "p", fallback="FB", agent_name="t")

    assert out == "ok"
    assert llm.ainvoke.await_count == 2


@pytest.mark.asyncio
async def test_does_not_retry_on_authentication_error():
    llm = MagicMock()
    err = openai.AuthenticationError(
        message="bad token",
        response=_http_response(401),
        body=None,
    )
    llm.ainvoke = AsyncMock(side_effect=err)

    out = await safe_ainvoke(llm, "p", fallback="FB", agent_name="t")

    assert out == "FB"
    assert llm.ainvoke.await_count == 1


@pytest.mark.asyncio
async def test_does_not_retry_on_generic_exception():
    """Generic exceptions stay on the existing fail-open path (1 attempt)."""
    llm = MagicMock()
    llm.ainvoke = AsyncMock(side_effect=RuntimeError("boom"))

    out = await safe_ainvoke(llm, "p", fallback="FB", agent_name="t")

    assert out == "FB"
    assert llm.ainvoke.await_count == 1


@pytest.mark.asyncio
async def test_backoff_delays_follow_exponential_schedule():
    """Verify sleep schedule: ~1s, ~3s, ~9s with ±20% jitter."""
    llm = MagicMock()
    llm.ainvoke = AsyncMock(side_effect=[_status_err(503)] * 4)
    sleep_calls: list[float] = []

    async def _record_sleep(d: float) -> None:
        sleep_calls.append(d)

    with patch.object(_llm_safe, "_async_sleep", new=_record_sleep, create=True):
        out = await safe_ainvoke(llm, "p", fallback="FB", agent_name="t")

    assert out == "FB"
    assert len(sleep_calls) == 3
    # Bands account for ±20% jitter.
    assert 0.8 <= sleep_calls[0] <= 1.2
    assert 2.4 <= sleep_calls[1] <= 3.6
    assert 7.2 <= sleep_calls[2] <= 10.8


@pytest.mark.asyncio
async def test_logs_warning_per_retry(caplog: pytest.LogCaptureFixture):
    llm = MagicMock()
    llm.ainvoke = AsyncMock(
        side_effect=[_status_err(503), _status_err(503), "ok"]
    )

    with caplog.at_level(logging.WARNING, logger="app.agents._llm_safe"):
        await safe_ainvoke(llm, "p", fallback="FB", agent_name="myagent")

    transient_records = [
        r for r in caplog.records if "transient" in r.getMessage().lower()
    ]
    assert len(transient_records) == 2
    assert all("myagent" in r.getMessage() for r in transient_records)


@pytest.mark.asyncio
async def test_504_gateway_timeout_is_transient():
    """504 (and 502, 500) all retry like 503."""
    llm = MagicMock()
    llm.ainvoke = AsyncMock(side_effect=[_status_err(504), "ok"])

    out = await safe_ainvoke(llm, "p", fallback="FB", agent_name="t")

    assert out == "ok"
    assert llm.ainvoke.await_count == 2


@pytest.mark.asyncio
async def test_404_is_permanent():
    """404 NotFound is a routing/config error — fail fast."""
    llm = MagicMock()
    err = openai.NotFoundError(
        message="model not found",
        response=_http_response(404),
        body=None,
    )
    llm.ainvoke = AsyncMock(side_effect=err)

    out = await safe_ainvoke(llm, "p", fallback="FB", agent_name="t")

    assert out == "FB"
    assert llm.ainvoke.await_count == 1
