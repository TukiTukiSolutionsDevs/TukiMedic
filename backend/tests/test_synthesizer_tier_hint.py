"""
TDD — hard blocker #1 batch 2B (synthesizer upgrade hint when tier gated).

When `state['tier_gated_specialists']` is True (free user whose specialist
analysis was skipped at the orchestrator level), the synthesized response
shown to the patient MUST tell them the multi-specialist analysis is a
paid-tier feature. Without this hint the gating is invisible — the user
gets a degraded answer with no signal as to why.

Public surface introduced:
  - `app.agents.synthesizer.agent.TIER_UPGRADE_HINT`  — stable string constant
  - `_compose_patient_text(..., upgrade_hint: str | None = None)` — optional kw
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agents.synthesizer.agent import (
    BASE_DISCLAIMER,
    DISCLAIMER_SEPARATOR,
    TIER_UPGRADE_HINT,
    SynthesizerAgent,
    _compose_patient_text,
)
from app.agents.synthesizer.schemas import SynthesizedResponse


# ---------------------------------------------------------------------------
# 1-3. _compose_patient_text helper
# ---------------------------------------------------------------------------


def test_compose_patient_text_appends_upgrade_hint_when_provided():
    out = _compose_patient_text(
        "Tomá descanso e hidratate.",
        "Custom disclaimer.",
        upgrade_hint=TIER_UPGRADE_HINT,
    )
    assert TIER_UPGRADE_HINT in out
    # Hint, body and disclaimer all coexist; order matters for readability:
    # body first, then hint, then disclaimer.
    body_pos = out.find("Tomá descanso")
    hint_pos = out.find(TIER_UPGRADE_HINT)
    disc_pos = out.find("Custom disclaimer.")
    assert body_pos < hint_pos < disc_pos


def test_compose_patient_text_no_hint_by_default():
    """Backward compatibility: existing calls must not change behaviour."""
    out = _compose_patient_text("Body.", "Disclaimer.")
    assert TIER_UPGRADE_HINT not in out
    assert out == f"Body.{DISCLAIMER_SEPARATOR}Disclaimer."


def test_compose_patient_text_falls_back_to_base_disclaimer_with_hint():
    """Even when the LLM disclaimer is empty, the hint must appear and the
    BASE_DISCLAIMER must still close the message."""
    out = _compose_patient_text(
        "Body.",
        "",
        upgrade_hint=TIER_UPGRADE_HINT,
    )
    assert TIER_UPGRADE_HINT in out
    assert BASE_DISCLAIMER in out


# ---------------------------------------------------------------------------
# 4. SynthesizerAgent integration — emits the hint when state flags it
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_synthesizer_includes_upgrade_hint_when_tier_gated():
    fake_response = SynthesizedResponse(
        patient_response="Tomá agua y descansá.",
        clinical_summary="Green triage.",
        attention_level="rutina",
    )

    fake_llm = MagicMock()
    fake_llm.with_structured_output = MagicMock(return_value=fake_llm)

    agent = SynthesizerAgent(chat_model=fake_llm)

    state = {
        "case_id": "c1",
        "user_id": "u1",
        "current_message": "me duele la cabeza",
        "triage_level": "green",
        "red_flags": [],
        "extracted_facts": [],
        "specialist_outputs": {},
        "tier_gated_specialists": True,
    }

    with patch(
        "app.agents.synthesizer.agent.safe_ainvoke",
        new=AsyncMock(return_value=fake_response),
    ):
        result = await agent(state)

    assert TIER_UPGRADE_HINT in result["synthesized_response"]


@pytest.mark.asyncio
async def test_synthesizer_omits_upgrade_hint_when_paid():
    """Paid users (or any state without the flag) must NOT see the hint."""
    fake_response = SynthesizedResponse(
        patient_response="Resultados completos.",
        clinical_summary="Yellow triage with cardio consult.",
        attention_level="hoy",
    )

    fake_llm = MagicMock()
    fake_llm.with_structured_output = MagicMock(return_value=fake_llm)

    agent = SynthesizerAgent(chat_model=fake_llm)

    state = {
        "case_id": "c1",
        "user_id": "u1",
        "current_message": "dolor en pecho leve",
        "triage_level": "yellow",
        "red_flags": [],
        "extracted_facts": [],
        "specialist_outputs": {"cardiologia": {"clinical_impression": "estable"}},
        # tier_gated_specialists absent — paid path
    }

    with patch(
        "app.agents.synthesizer.agent.safe_ainvoke",
        new=AsyncMock(return_value=fake_response),
    ):
        result = await agent(state)

    assert TIER_UPGRADE_HINT not in result["synthesized_response"]
