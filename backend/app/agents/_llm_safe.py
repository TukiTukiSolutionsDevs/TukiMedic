"""
Safe LLM invocation wrapper for all agents.

Centralizes error handling around `llm.ainvoke(...)`. Any exception raised
by the underlying LLM client (rate limits, timeouts, transport errors, schema
validation errors) is logged and swallowed; the caller receives the supplied
fallback value instead. This prevents a single LLM hiccup from killing the
whole orchestrator graph or leaking provider error strings to clients.

Usage:
    result = await safe_ainvoke(
        self.llm,
        messages,
        fallback=TriageResult(...),
        agent_name="triage",
    )
"""

from __future__ import annotations

import logging
from typing import Any, TypeVar

log = logging.getLogger(__name__)

T = TypeVar("T")


async def safe_ainvoke(llm: Any, prompt: Any, *, fallback: T, agent_name: str) -> T:
    """Invoke an LLM and return `fallback` on any exception.

    Args:
        llm: a LangChain Runnable (typically `ChatOpenAI(...).with_structured_output(...)`).
        prompt: messages list / string / whatever the runnable expects.
        fallback: value returned when the call fails. Must be the same shape
            the agent would normally consume (usually a Pydantic model
            instance configured for fail-safe defaults).
        agent_name: short identifier used in log records.

    Returns:
        Either the LLM result or the fallback. Never raises.
    """
    try:
        return await llm.ainvoke(prompt)
    except Exception as exc:  # noqa: BLE001 — intentional broad catch
        log.exception(
            "agent.%s LLM call failed (%s); returning fallback",
            agent_name,
            type(exc).__name__,
        )
        return fallback
