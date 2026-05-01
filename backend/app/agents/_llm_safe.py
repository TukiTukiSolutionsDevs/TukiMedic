"""
Safe LLM invocation wrapper for all agents.

Centralizes error handling around `llm.ainvoke(...)`:

* Transient upstream errors (5xx HTTP, 429 rate-limit, network timeouts,
  connection drops) are retried with exponential backoff and ±20% jitter
  (3 retries scheduled at 1s / 3s / 9s, worst-case ~13s of added latency).
* Permanent errors (4xx auth/validation/bad-request, structured-output
  parse failures, generic exceptions) fall through immediately and the
  caller receives the supplied fallback. The fail-open contract is
  preserved: agents NEVER raise to the orchestrator graph.

Provider stack: `langchain_openai.ChatOpenAI` against the Gemini
OpenAI-compatible endpoint, so the SDK that surfaces transient errors is
`openai`, not `google.api_core` (the latter would only apply if the native
`langchain-google-genai` client were wired in).

Usage:
    result = await safe_ainvoke(
        self.llm,
        messages,
        fallback=TriageResult(...),
        agent_name="triage",
    )

Test seam:
    `_async_sleep` is the indirected sleep coroutine. Unit tests monkeypatch
    it (see `tests/conftest.py::_stub_llm_safe_sleep`) so the suite stays
    fast even when the retry path is exercised.
"""

from __future__ import annotations

import asyncio
import logging
import random
from typing import Any, TypeVar

import openai

log = logging.getLogger(__name__)

T = TypeVar("T")

# Indirected for monkeypatching in unit tests so the suite stays fast.
_async_sleep = asyncio.sleep

# Backoff schedule in seconds. Length = max retry count (the original attempt
# is performed before any sleep). Total worst-case wait ≈ 1 + 3 + 9 = 13s,
# plus ±20% jitter. With 4 attempts total this leaves P95 well under any
# reasonable HTTP timeout (the eval P95 today is ~132s).
_BACKOFF_SECONDS: tuple[float, ...] = (1.0, 3.0, 9.0)
_JITTER_RATIO = 0.2  # ±20% multiplicative jitter on each delay.

# HTTP status codes considered transient when surfaced via APIStatusError.
_TRANSIENT_HTTP_STATUS = frozenset({500, 502, 503, 504})


def _is_transient(exc: BaseException) -> bool:
    """Classify an exception as recoverable upstream condition.

    The set of retry-eligible exception types is intentionally narrow: only
    network/server-side hiccups and rate limits. Validation, auth, and
    permission errors mean the request itself is wrong — retrying would
    waste tokens without changing the outcome.
    """
    if isinstance(
        exc,
        (
            asyncio.TimeoutError,
            openai.APITimeoutError,
            openai.APIConnectionError,
            openai.RateLimitError,
        ),
    ):
        return True
    if isinstance(exc, openai.APIStatusError):
        return getattr(exc, "status_code", None) in _TRANSIENT_HTTP_STATUS
    return False


def _jittered(base: float) -> float:
    """Return ``base`` perturbed by ±_JITTER_RATIO."""
    delta = base * _JITTER_RATIO
    return base + random.uniform(-delta, delta)


async def safe_ainvoke(
    llm: Any, prompt: Any, *, fallback: T, agent_name: str
) -> T:
    """Invoke an LLM and return the result, retrying transient errors.

    Args:
        llm: a LangChain Runnable (typically
            `ChatOpenAI(...).with_structured_output(...)`).
        prompt: messages list / string / whatever the runnable expects.
        fallback: value returned when the call fails after all retries.
            Must be the same shape the agent would normally consume —
            usually a Pydantic model with fail-safe defaults.
        agent_name: short identifier used in log records.

    Returns:
        Either the LLM result or the fallback. Never raises.
    """
    max_attempts = len(_BACKOFF_SECONDS) + 1  # 1 original + 3 retries = 4

    for attempt in range(1, max_attempts + 1):
        try:
            return await llm.ainvoke(prompt)
        except Exception as exc:  # noqa: BLE001 — intentional broad catch
            if _is_transient(exc) and attempt < max_attempts:
                sleep_s = _jittered(_BACKOFF_SECONDS[attempt - 1])
                log.warning(
                    "agent.%s LLM transient error (attempt %d/%d, "
                    "sleeping %.2fs): %s",
                    agent_name,
                    attempt,
                    max_attempts,
                    sleep_s,
                    type(exc).__name__,
                )
                await _async_sleep(sleep_s)
                continue
            log.exception(
                "agent.%s LLM call failed (%s); returning fallback",
                agent_name,
                type(exc).__name__,
            )
            return fallback

    # Unreachable: the loop always returns within the try/except above.
    return fallback  # pragma: no cover
