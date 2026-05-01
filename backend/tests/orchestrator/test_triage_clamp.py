"""Unit tests for _clamp_triage — defensive demotion when LLM
escalates to red without supporting evidence.

The clamp is the type-safe analogue of `_clamp_attention` in the synthesizer:
LLM categorical contracts cannot be trusted in isolation; we anchor to
deterministic evidence (pre-LLM red_flag_checker matches) and the LLM's
own self-reported `red_flags_detected`.

Rule:
    if level == "red" AND not deterministic_matches AND not red_flags_detected:
        demote to "yellow"
    else:
        leave unchanged

This addresses the over-triage failures gi-001 / green-002 / green-003
where the LLM returned `red` despite producing an empty `red_flags_detected`
list and no deterministic match upstream.
"""

import pytest

from app.agents.triage.agent import _clamp_triage


class TestClampTriageDemotes:
    """RED level without supporting evidence MUST demote to yellow."""

    def test_red_without_evidence_demotes_to_yellow(self):
        result = _clamp_triage(
            level="red",
            red_flags_detected=[],
            deterministic_matches=[],
        )
        assert result == "yellow"

    def test_red_without_evidence_demotes_even_with_high_confidence(self):
        # Confidence is irrelevant — the rule is structural.
        result = _clamp_triage(
            level="red",
            red_flags_detected=[],
            deterministic_matches=[],
        )
        assert result == "yellow"


class TestClampTriagePreservesRed:
    """RED level with evidence MUST be preserved — never demote real emergencies."""

    def test_red_with_deterministic_match_kept(self):
        result = _clamp_triage(
            level="red",
            red_flags_detected=[],
            deterministic_matches=["dolor torácico irradiado al brazo"],
        )
        assert result == "red"

    def test_red_with_llm_reported_flag_kept(self):
        result = _clamp_triage(
            level="red",
            red_flags_detected=["disnea súbita severa"],
            deterministic_matches=[],
        )
        assert result == "red"

    def test_red_with_both_evidence_kept(self):
        result = _clamp_triage(
            level="red",
            red_flags_detected=["debilidad unilateral"],
            deterministic_matches=["pérdida de habla súbita"],
        )
        assert result == "red"


class TestClampTriagePassthrough:
    """Non-red levels are never altered by the clamp."""

    def test_yellow_unchanged(self):
        result = _clamp_triage(
            level="yellow",
            red_flags_detected=[],
            deterministic_matches=[],
        )
        assert result == "yellow"

    def test_green_unchanged(self):
        result = _clamp_triage(
            level="green",
            red_flags_detected=[],
            deterministic_matches=[],
        )
        assert result == "green"

    def test_yellow_with_spurious_flags_unchanged(self):
        # If yellow somehow comes back with red_flags, we don't promote — that's
        # not the clamp's job. Promotion only happens deterministically pre-LLM.
        result = _clamp_triage(
            level="yellow",
            red_flags_detected=["dolor leve"],
            deterministic_matches=[],
        )
        assert result == "yellow"


class TestClampTriageEdgeCases:
    """Defensive cases — invalid inputs must not throw or escalate."""

    def test_empty_strings_in_evidence_treated_as_no_evidence(self):
        # An LLM might return [""] which is technically truthy but semantically empty.
        # We treat any non-empty truthy value as evidence; "" is filtered.
        result = _clamp_triage(
            level="red",
            red_flags_detected=["", "  "],
            deterministic_matches=[],
        )
        assert result == "yellow"
