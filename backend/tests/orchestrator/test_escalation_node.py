"""TDD — Bug fix: `_escalation_node` over-escalates non-emergency cases.

Surfaced by clinical eval baseline (commit 4082086): 8 of 9 failing cases were
yellow/green triage that ended up with `attention_level="urgencia"` because the
guardrail interrupt routes to `_escalation_node`, which hardcodes urgencia and
overwrites the synthesized response with an ER message.

`_escalation_node` is reached by TWO paths:
1. triage_router with `triage_level == "red"` AND red_flags present → real emergency
2. _guardrail_router with `guardrail_interrupt == True` → safety filter, NOT
   medical urgency

The node must discriminate so guardrail-triggered escalations don't look like
ER alerts to non-emergency patients.
"""
from __future__ import annotations

import pytest

from app.orchestrator.graph import _escalation_node
from app.agents.synthesizer.agent import BASE_DISCLAIMER


# ---------------------------------------------------------------------------
# Path 1: real medical emergency (triage red + red_flags) — current behavior
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_red_triage_with_flags_returns_urgencia_and_er_message():
    state = {
        "triage_level": "red",
        "red_flags": ["dolor en el pecho", "irradiación a brazo"],
        "synthesized_response": None,
    }
    result = await _escalation_node(state)

    assert result["attention_level"] == "urgencia"
    assert "ATENCIÓN" in result["synthesized_response"]
    assert "urgencias" in result["synthesized_response"].lower()
    assert BASE_DISCLAIMER in result["synthesized_response"]
    assert result["current_node"] == "escalation"


@pytest.mark.asyncio
async def test_red_triage_without_flags_still_urgencia():
    """Triage classified red but no flags surfaced — still emergency."""
    state = {
        "triage_level": "red",
        "red_flags": [],
        "synthesized_response": None,
    }
    result = await _escalation_node(state)
    assert result["attention_level"] == "urgencia"


# ---------------------------------------------------------------------------
# Path 2: guardrail-triggered escalation on non-emergency triage
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_yellow_triage_guardrail_interrupt_preserves_yellow_attention_level():
    """Guardrail interrupted on a yellow case — attention_level must NOT be urgencia."""
    state = {
        "triage_level": "yellow",
        "red_flags": [],
        "synthesized_response": "Tu consulta fue revisada por especialistas. Recomendamos consulta médica.",
    }
    result = await _escalation_node(state)

    assert result["attention_level"] in ("24-48h", "hoy"), (
        f"yellow triage must map to 24-48h or hoy, got {result['attention_level']}"
    )
    assert result["attention_level"] != "urgencia"
    # Disclaimer must still be present
    assert BASE_DISCLAIMER in result["synthesized_response"]
    # Should NOT contain the alarmist ER message
    assert "ATENCIÓN" not in result["synthesized_response"]
    assert "emergencia" not in result["synthesized_response"].lower()


@pytest.mark.asyncio
async def test_green_triage_guardrail_interrupt_preserves_rutina():
    """Guardrail on a green case — attention_level must be rutina (or 24-48h max)."""
    state = {
        "triage_level": "green",
        "red_flags": [],
        "synthesized_response": "Tu consulta es de rutina. Consultá si los síntomas persisten.",
    }
    result = await _escalation_node(state)

    assert result["attention_level"] in ("rutina", "24-48h"), (
        f"green triage must NOT escalate to urgencia/hoy, got {result['attention_level']}"
    )
    assert result["attention_level"] != "urgencia"


@pytest.mark.asyncio
async def test_yellow_no_synthesized_response_returns_neutral_safety_message():
    """If synthesizer never ran (or response is empty), return a neutral safety
    message — NOT the ER alarm — so attention_level stays mapped to triage."""
    state = {
        "triage_level": "yellow",
        "red_flags": [],
        "synthesized_response": None,
    }
    result = await _escalation_node(state)

    assert result["attention_level"] != "urgencia"
    assert result["synthesized_response"]
    assert BASE_DISCLAIMER in result["synthesized_response"]
    # No ER alarm
    assert "ATENCIÓN" not in result["synthesized_response"]


@pytest.mark.asyncio
async def test_existing_disclaimer_not_duplicated():
    state = {
        "triage_level": "yellow",
        "red_flags": [],
        "synthesized_response": (
            "Recomendamos consulta médica.\n\n---\n\n"
            + BASE_DISCLAIMER
        ),
    }
    result = await _escalation_node(state)
    # Disclaimer present exactly once
    assert result["synthesized_response"].lower().count(BASE_DISCLAIMER.lower()) == 1
