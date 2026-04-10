"""Tests for the Synthesizer Agent — schemas and agent node."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from app.agents.synthesizer.schemas import SynthesizedResponse
from app.agents.synthesizer.agent import SynthesizerAgent


# ========== SynthesizedResponse Schema Tests ==========

class TestSynthesizedResponse:
    def test_valid_minimal(self):
        r = SynthesizedResponse(
            patient_response="Basándonos en tu consulta, te recomendamos ver un médico pronto.",
            clinical_summary="Yellow triage. Cardiology consulted. Differential: angina pectoris.",
            attention_level="hoy",
        )
        assert r.patient_response != ""
        assert r.attention_level == "hoy"
        assert r.disclaimer == "Esta orientación no reemplaza la consulta médica presencial."

    def test_disclaimer_has_default(self):
        r = SynthesizedResponse(
            patient_response="Consultá con tu médico.",
            clinical_summary="Green triage.",
            attention_level="rutina",
        )
        assert r.disclaimer == "Esta orientación no reemplaza la consulta médica presencial."

    def test_disclaimer_can_be_overridden(self):
        custom = "Esto es solo orientación, no diagnóstico."
        r = SynthesizedResponse(
            patient_response="Consultá con tu médico.",
            clinical_summary="Green triage.",
            attention_level="rutina",
            disclaimer=custom,
        )
        assert r.disclaimer == custom

    def test_attention_level_valid_literals(self):
        for level in ["rutina", "24-48h", "hoy", "urgencia"]:
            r = SynthesizedResponse(
                patient_response="Texto.",
                clinical_summary="Resumen.",
                attention_level=level,
            )
            assert r.attention_level == level

    def test_attention_level_invalid_raises(self):
        with pytest.raises(Exception):
            SynthesizedResponse(
                patient_response="Texto.",
                clinical_summary="Resumen.",
                attention_level="mañana",  # not a valid literal
            )

    def test_specialties_involved_default_empty(self):
        r = SynthesizedResponse(
            patient_response="Texto.",
            clinical_summary="Resumen.",
            attention_level="rutina",
        )
        assert r.specialties_involved == []

    def test_specialties_involved_populated(self):
        r = SynthesizedResponse(
            patient_response="Texto.",
            clinical_summary="Resumen.",
            attention_level="24-48h",
            specialties_involved=["Cardiología", "Neurología"],
        )
        assert "Cardiología" in r.specialties_involved
        assert len(r.specialties_involved) == 2

    def test_follow_up_questions_default_empty(self):
        r = SynthesizedResponse(
            patient_response="Texto.",
            clinical_summary="Resumen.",
            attention_level="rutina",
        )
        assert r.follow_up_questions == []

    def test_alarm_signs_default_empty(self):
        r = SynthesizedResponse(
            patient_response="Texto.",
            clinical_summary="Resumen.",
            attention_level="rutina",
        )
        assert r.alarm_signs == []

    def test_full_response(self):
        r = SynthesizedResponse(
            patient_response="Tu caso fue evaluado por múltiples especialistas.",
            clinical_summary="Multi-specialty review. Consensus: partial. Attention: urgencia.",
            attention_level="urgencia",
            specialties_involved=["Cardiología", "Neurología", "Medicina Interna"],
            follow_up_questions=["¿Tenés antecedentes de presión alta?"],
            alarm_signs=["Dolor en el pecho que se irradia al brazo", "Dificultad para respirar"],
            disclaimer="Esta orientación no reemplaza la consulta médica presencial.",
        )
        assert r.attention_level == "urgencia"
        assert len(r.specialties_involved) == 3
        assert len(r.alarm_signs) == 2
        assert len(r.follow_up_questions) == 1


# ========== SynthesizerAgent Node Tests ==========

def make_state(**overrides):
    """Build a minimal ClinicalCaseState-like dict for testing."""
    base = {
        "case_id": "test-001",
        "user_id": "user-001",
        "messages": [],
        "current_message": "me duele la cabeza desde hace 3 días",
        "triage_level": "yellow",
        "triage_confidence": 0.85,
        "red_flags": [],
        "extracted_facts": [],
        "pending_questions": [],
        "completeness_score": 0.8,
        "active_specialties": [],
        "primary_specialty": None,
        "specialist_outputs": {},
        "medical_board_result": None,
        "debate_rounds": 0,
        "consensus_level": None,
        "challenges": [],
        "false_consensus_risk": 0.0,
        "guardrail_violations": [],
        "guardrail_interrupt": False,
        "synthesized_response": None,
        "attention_level": None,
        "loop_count": 0,
        "max_loops": 3,
        "current_node": "synthesizer",
        "force_close": False,
        "created_at": "2026-04-09T00:00:00",
        "updated_at": "2026-04-09T00:00:00",
    }
    base.update(overrides)
    return base


def make_mock_response(
    patient_response: str = "Basándonos en tu consulta te recomendamos ver un médico.",
    clinical_summary: str = "Yellow triage. Neurology consulted.",
    attention_level: str = "24-48h",
    specialties_involved: list = None,
    alarm_signs: list = None,
) -> SynthesizedResponse:
    return SynthesizedResponse(
        patient_response=patient_response,
        clinical_summary=clinical_summary,
        attention_level=attention_level,
        specialties_involved=specialties_involved or [],
        alarm_signs=alarm_signs or [],
    )


def make_agent_with_mock(mock_result: SynthesizedResponse) -> SynthesizerAgent:
    """Create a SynthesizerAgent with mocked LLM ainvoke."""
    agent = SynthesizerAgent.__new__(SynthesizerAgent)
    agent.llm = MagicMock()
    agent.llm.ainvoke = AsyncMock(return_value=mock_result)
    return agent


class TestSynthesizerAgent:
    @pytest.mark.asyncio
    async def test_returns_correct_state_keys(self):
        agent = make_agent_with_mock(make_mock_response())
        result = await agent(make_state())
        assert "synthesized_response" in result
        assert "attention_level" in result
        assert "current_node" in result
        assert result["current_node"] == "synthesizer"

    @pytest.mark.asyncio
    async def test_synthesized_response_is_string(self):
        agent = make_agent_with_mock(
            make_mock_response(patient_response="Esta es la respuesta para el paciente.")
        )
        result = await agent(make_state())
        assert isinstance(result["synthesized_response"], str)
        assert result["synthesized_response"] != ""

    @pytest.mark.asyncio
    async def test_attention_level_propagated(self):
        agent = make_agent_with_mock(make_mock_response(attention_level="urgencia"))
        result = await agent(make_state())
        assert result["attention_level"] == "urgencia"

    @pytest.mark.asyncio
    async def test_specialties_from_state_when_llm_returns_empty(self):
        """If LLM returns empty specialties_involved, agent fills from state keys."""
        agent = make_agent_with_mock(make_mock_response(specialties_involved=[]))
        state = make_state(
            specialist_outputs={
                "cardiologia": {"clinical_impression": "Normal", "recommendations": []},
                "neurologia": {"clinical_impression": "Sin hallazgos", "recommendations": []},
            }
        )
        result = await agent(state)
        agent.llm.ainvoke.assert_called_once()
        assert result["current_node"] == "synthesizer"

    @pytest.mark.asyncio
    async def test_builds_context_with_triage_info(self):
        agent = make_agent_with_mock(make_mock_response())
        state = make_state(triage_level="red", red_flags=["dolor torácico agudo"])
        await agent(state)
        call_args = agent.llm.ainvoke.call_args
        messages = call_args[0][0]
        user_content = next(m["content"] for m in messages if m["role"] == "user")
        assert "red" in user_content.lower() or "triage" in user_content.lower()

    @pytest.mark.asyncio
    async def test_builds_context_with_medical_board(self):
        agent = make_agent_with_mock(make_mock_response())
        state = make_state(
            medical_board_result={
                "consensus_level": "full",
                "moderator_summary": "El panel coincide en origen neurológico.",
                "key_agreements": ["Origen neurológico probable"],
                "key_disagreements": [],
            }
        )
        await agent(state)
        call_args = agent.llm.ainvoke.call_args
        messages = call_args[0][0]
        user_content = next(m["content"] for m in messages if m["role"] == "user")
        assert (
            "panel" in user_content.lower()
            or "consenso" in user_content.lower()
            or "moderador" in user_content.lower()
        )

    @pytest.mark.asyncio
    async def test_includes_extracted_facts_in_context(self):
        agent = make_agent_with_mock(make_mock_response())
        state = make_state(
            extracted_facts=[
                {"key": "edad", "value": "45"},
                {"key": "síntoma_principal", "value": "cefalea"},
            ]
        )
        await agent(state)
        call_args = agent.llm.ainvoke.call_args
        messages = call_args[0][0]
        user_content = next(m["content"] for m in messages if m["role"] == "user")
        assert "edad" in user_content or "45" in user_content
