"""
TDD — hard blocker #1 batch 2 (specialist analysis gating in WS chat).

Specialist dispatch (8-agent fan-out) is paid-tier only. Gating happens
INSIDE the orchestrator graph at `specialist_node` so that:
  - dispatch_specialists is never called for free users → 0 LLM tokens of
    the smart tier, real cost-control.
  - state['specialist_outputs'] is set to {} and a sentinel
    state['tier_gated_specialists'] = True is emitted, so downstream nodes
    (synthesizer, medical_board router) can react.

Public surface introduced:
  - `app.orchestrator.graph._should_gate_specialists(state) -> bool`
  - `app.orchestrator.graph._maybe_dispatch_specialists(state, chat_model_factory)
        -> dict`
  - `ClinicalCaseState.subscription_tier: str | None`
  - `ClinicalCaseState.tier_gated_specialists: bool`
"""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest  # noqa: F401 — kept for asyncio-mode=auto plugin discovery

from app.orchestrator.graph import (
    _maybe_dispatch_specialists,
    _should_gate_specialists,
)

# NOTE: --asyncio-mode=auto handles the async tests; we don't apply a module-
# level pytest.mark.asyncio because half of these tests are sync (predicate
# unit tests) and the marker would emit a noisy warning on those.


# ---------------------------------------------------------------------------
# 1-4. Predicate
# ---------------------------------------------------------------------------


def test_should_gate_specialists_true_for_free_user():
    assert _should_gate_specialists({"subscription_tier": "free"}) is True


def test_should_gate_specialists_false_for_paid_user():
    assert _should_gate_specialists({"subscription_tier": "paid"}) is False


def test_should_gate_specialists_true_when_tier_missing():
    """Defensive default: missing tier MUST NOT silently grant access."""
    assert _should_gate_specialists({}) is True


def test_should_gate_specialists_true_for_unknown_tier():
    """Garbage in DB must not silently grant access."""
    assert _should_gate_specialists({"subscription_tier": "legacy_x"}) is True


# ---------------------------------------------------------------------------
# 5-6. Helper integration with dispatch_specialists
# ---------------------------------------------------------------------------


async def test_maybe_dispatch_specialists_skips_when_gated():
    """Free user → dispatch_specialists is NOT called, returns empty
    outputs + tier_gated flag."""
    factory_called = False

    def _factory():
        nonlocal factory_called
        factory_called = True
        return object()

    with patch(
        "app.orchestrator.graph.dispatch_specialists",
        new=AsyncMock(return_value={"specialist_outputs": {"cardio": {"x": 1}}}),
    ) as dispatch_mock:
        result = await _maybe_dispatch_specialists(
            {"subscription_tier": "free", "case_id": "c1"},
            _factory,
        )

    assert dispatch_mock.await_count == 0
    assert factory_called is False  # No LLM model instantiation either
    assert result == {
        "specialist_outputs": {},
        "tier_gated_specialists": True,
    }


async def test_maybe_dispatch_specialists_runs_when_paid():
    """Paid user → dispatch_specialists IS called with the model from factory."""
    sentinel_model = object()
    expected = {"specialist_outputs": {"cardio": {"verdict": "stable"}}}

    with patch(
        "app.orchestrator.graph.dispatch_specialists",
        new=AsyncMock(return_value=expected),
    ) as dispatch_mock:
        result = await _maybe_dispatch_specialists(
            {"subscription_tier": "paid", "case_id": "c1"},
            lambda: sentinel_model,
        )

    assert dispatch_mock.await_count == 1
    # Confirm it was called with the model from the factory.
    _, kwargs = dispatch_mock.await_args
    assert kwargs.get("chat_model") is sentinel_model
    assert result is expected
