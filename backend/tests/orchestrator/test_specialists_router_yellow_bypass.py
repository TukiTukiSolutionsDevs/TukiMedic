"""Unit tests for _specialists_router yellow-with-consensus bypass.

Extends the green-bypass introduced in commit 0b049cd (which routes
green-triage cases directly to the synthesizer, skipping medical_board
to save 15-30s of smart-tier latency).

This adds an analogous bypass for YELLOW cases when the dispatched
specialists already agree:
  - All specialists have confidence >= 0.8
  - All specialists' top differential diagnosis matches (case-insensitive)

When both conditions hold, the medical_board's deliberative debate adds
limited value (the patient gets the same answer faster). When they don't,
we keep the full deliberation path.

Red triage never reaches this router (triage_router escalates first).
"""

import pytest

from app.orchestrator.graph import _specialists_router


def _state(triage_level: str | None = None, specialist_outputs: dict | None = None) -> dict:
    return {
        "triage_level": triage_level,
        "specialist_outputs": specialist_outputs or {},
    }


class TestGreenBypassUnchanged:
    def test_green_bypasses_to_synthesizer_regardless_of_outputs(self):
        assert _specialists_router(_state("green", {})) == "synthesizer"
        assert _specialists_router(_state("green", {"x": {"confidence": 0.1}})) == "synthesizer"


class TestYellowConsensusBypass:
    def test_yellow_with_high_confidence_consensus_bypasses(self):
        outputs = {
            "Cardiología": {
                "confidence": 0.85,
                "differential_diagnosis": [{"condition": "Hipertensión esencial"}],
            },
            "Medicina General": {
                "confidence": 0.9,
                "differential_diagnosis": [{"condition": "hipertensión esencial"}],
            },
        }
        assert _specialists_router(_state("yellow", outputs)) == "synthesizer"

    def test_yellow_with_disagreement_uses_medical_board(self):
        outputs = {
            "Cardiología": {
                "confidence": 0.85,
                "differential_diagnosis": [{"condition": "Pericarditis"}],
            },
            "Medicina General": {
                "confidence": 0.85,
                "differential_diagnosis": [{"condition": "Costocondritis"}],
            },
        }
        assert _specialists_router(_state("yellow", outputs)) == "medical_board"

    def test_yellow_with_low_confidence_uses_medical_board(self):
        outputs = {
            "Cardiología": {
                "confidence": 0.7,
                "differential_diagnosis": [{"condition": "X"}],
            },
            "Medicina General": {
                "confidence": 0.65,
                "differential_diagnosis": [{"condition": "X"}],
            },
        }
        assert _specialists_router(_state("yellow", outputs)) == "medical_board"

    def test_yellow_with_single_specialist_uses_medical_board(self):
        # Single specialist is not a consensus; keep deliberation.
        outputs = {
            "Cardiología": {
                "confidence": 0.95,
                "differential_diagnosis": [{"condition": "X"}],
            },
        }
        assert _specialists_router(_state("yellow", outputs)) == "medical_board"

    def test_yellow_with_no_outputs_uses_medical_board(self):
        assert _specialists_router(_state("yellow", {})) == "medical_board"

    def test_yellow_with_missing_confidence_uses_medical_board(self):
        outputs = {
            "Cardiología": {"differential_diagnosis": [{"condition": "X"}]},
            "Medicina General": {"differential_diagnosis": [{"condition": "X"}]},
        }
        assert _specialists_router(_state("yellow", outputs)) == "medical_board"


class TestUnknownTriageLevels:
    def test_none_triage_uses_medical_board(self):
        # Defensive: if triage_level is missing, deliberation is the safer default.
        assert _specialists_router(_state(None, {})) == "medical_board"

    def test_red_triage_uses_medical_board_if_reached(self):
        # Red never reaches this router in practice (triage_router escalates),
        # but defensively we keep deliberation rather than silently bypassing.
        assert _specialists_router(_state("red", {})) == "medical_board"
