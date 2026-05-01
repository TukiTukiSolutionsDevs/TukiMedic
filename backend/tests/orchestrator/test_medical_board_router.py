"""Unit tests for medical_board_router — devils_advocate gating.

Before this change, the router invoked devils_advocate on any
(extra_round + disagreement) signal. This produced latency outliers
(gi-002=255s, trauma-001=181s) for benign cases where the LLM-reported
"disagreement" was noise.

Tightened condition for invoking devils_advocate:
  - resolution_path == "extra_round"
  - consensus_level == "disagreement"
  - false_consensus_risk >= 0.5
  - triage_level != "green"
  - debate_rounds budget not exhausted

When any condition fails, route to "synthesis" (close the loop).
Clarification path is unaffected.
"""

import pytest

from app.agents.medical_board.agent import medical_board_router, MAX_EXTRA_ROUNDS


def _state(
    *,
    consensus_level: str | None = None,
    resolution_path: str = "synthesis",
    debate_rounds: int = 1,
    triage_level: str | None = "yellow",
    false_consensus_risk: float = 0.0,
) -> dict:
    return {
        "medical_board_result": {
            "resolution_path": resolution_path,
            "consensus_level": consensus_level,
        },
        "consensus_level": consensus_level,
        "debate_rounds": debate_rounds,
        "triage_level": triage_level,
        "false_consensus_risk": false_consensus_risk,
    }


class TestDevilsAdvocateInvocation:
    def test_all_conditions_met_invokes_devils(self):
        state = _state(
            resolution_path="extra_round",
            consensus_level="disagreement",
            triage_level="yellow",
            false_consensus_risk=0.7,
            debate_rounds=1,
        )
        assert medical_board_router(state) == "devils_advocate"

    def test_low_false_consensus_risk_skips_devils(self):
        state = _state(
            resolution_path="extra_round",
            consensus_level="disagreement",
            triage_level="yellow",
            false_consensus_risk=0.3,  # below threshold
            debate_rounds=1,
        )
        assert medical_board_router(state) == "synthesis"

    def test_green_triage_skips_devils(self):
        # Green should never reach the board (specialists_router bypasses),
        # but defensive: if it does, no extra deliberation.
        state = _state(
            resolution_path="extra_round",
            consensus_level="disagreement",
            triage_level="green",
            false_consensus_risk=0.9,
            debate_rounds=1,
        )
        assert medical_board_router(state) == "synthesis"

    def test_partial_consensus_skips_devils(self):
        state = _state(
            resolution_path="extra_round",
            consensus_level="partial",
            triage_level="yellow",
            false_consensus_risk=0.7,
            debate_rounds=1,
        )
        assert medical_board_router(state) == "synthesis"

    def test_full_consensus_skips_devils(self):
        state = _state(
            resolution_path="extra_round",
            consensus_level="full",
            triage_level="yellow",
            false_consensus_risk=0.7,
            debate_rounds=1,
        )
        assert medical_board_router(state) == "synthesis"


class TestRoundBudget:
    def test_exhausted_rounds_force_synthesis(self):
        state = _state(
            resolution_path="extra_round",
            consensus_level="disagreement",
            triage_level="yellow",
            false_consensus_risk=0.9,
            debate_rounds=MAX_EXTRA_ROUNDS + 2,
        )
        assert medical_board_router(state) == "synthesis"


class TestClarificationPath:
    def test_clarification_overrides_devils(self):
        state = _state(
            resolution_path="clarification",
            consensus_level="disagreement",
            triage_level="yellow",
            false_consensus_risk=0.9,
            debate_rounds=1,
        )
        assert medical_board_router(state) == "clarification"


class TestDefaultPath:
    def test_synthesis_resolution_returns_synthesis(self):
        state = _state(
            resolution_path="synthesis",
            consensus_level="full",
            debate_rounds=1,
        )
        assert medical_board_router(state) == "synthesis"
