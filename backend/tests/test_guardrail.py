"""Tests for the Guardrail Agent — schemas, enum values, and agent node."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from app.agents.guardrail.schemas import (
    GuardrailCheck,
    SafetyViolation,
    InterruptionLevel,
)
from app.agents.guardrail.agent import GuardrailAgent


# ========== InterruptionLevel Enum Tests ==========

class TestInterruptionLevel:
    def test_observe_value(self):
        assert InterruptionLevel.OBSERVE == "observe"

    def test_flag_value(self):
        assert InterruptionLevel.FLAG == "flag"

    def test_modify_value(self):
        assert InterruptionLevel.MODIFY == "modify"

    def test_interrupt_value(self):
        assert InterruptionLevel.INTERRUPT == "interrupt"

    def test_all_levels_present(self):
        levels = {level.value for level in InterruptionLevel}
        assert levels == {"observe", "flag", "modify", "interrupt"}


# ========== SafetyViolation Schema Tests ==========

class TestSafetyViolation:
    def test_valid_low_severity(self):
        v = SafetyViolation(
            violation_type="inappropriate_tone",
            description="Tono condescendiente",
            severity="low",
        )
        assert v.severity == "low"
        assert v.node_source == ""  # default

    def test_valid_critical_severity(self):
        v = SafetyViolation(
            violation_type="prescription_with_dose",
            description="Prescribió ibuprofeno 400mg",
            severity="critical",
            node_source="synthesizer",
        )
        assert v.severity == "critical"
        assert v.node_source == "synthesizer"

    def test_invalid_severity_raises(self):
        with pytest.raises(Exception):
            SafetyViolation(
                violation_type="x",
                description="x",
                severity="extreme",  # not a valid literal
            )

    def test_node_source_defaults_to_empty(self):
        v = SafetyViolation(
            violation_type="missing_disclaimer",
            description="Falta disclaimer",
            severity="medium",
        )
        assert v.node_source == ""


# ========== GuardrailCheck Schema Tests ==========

class TestGuardrailCheck:
    def test_approved_true_no_violations(self):
        check = GuardrailCheck(approved=True)
        assert check.approved is True
        assert check.violations == []
        assert check.interruption_level == InterruptionLevel.OBSERVE
        assert check.escalation_required is False
        assert check.escalation_reason == ""

    def test_approved_false_with_violations(self):
        violation = SafetyViolation(
            violation_type="definitive_diagnosis",
            description="Dijo 'tenés diabetes'",
            severity="high",
        )
        check = GuardrailCheck(
            approved=False,
            violations=[violation],
            interruption_level=InterruptionLevel.MODIFY,
        )
        assert check.approved is False
        assert len(check.violations) == 1
        assert check.interruption_level == InterruptionLevel.MODIFY

    def test_default_interruption_level_is_observe(self):
        check = GuardrailCheck(approved=True)
        assert check.interruption_level == InterruptionLevel.OBSERVE

    def test_escalation_required_on_critical(self):
        violation = SafetyViolation(
            violation_type="prescription_with_dose",
            description="Prescribió amoxicilina 500mg",
            severity="critical",
        )
        check = GuardrailCheck(
            approved=False,
            violations=[violation],
            interruption_level=InterruptionLevel.INTERRUPT,
            escalation_required=True,
            escalation_reason="Prescripción con dosis detectada",
        )
        assert check.escalation_required is True
        assert "dosis" in check.escalation_reason.lower()

    def test_modifications_suggested_default_empty(self):
        check = GuardrailCheck(approved=True)
        assert check.modifications_suggested == []

    def test_modifications_suggested_populated(self):
        check = GuardrailCheck(
            approved=False,
            interruption_level=InterruptionLevel.MODIFY,
            modifications_suggested=["Reemplazá 'tenés diabetes' por 'los síntomas son compatibles con...'"],
        )
        assert len(check.modifications_suggested) == 1


# ========== GuardrailAgent Node Tests ==========

def make_state(**overrides):
    """Build a minimal ClinicalCaseState-like dict for testing."""
    base = {
        "case_id": "test-001",
        "user_id": "user-001",
        "messages": [],
        "current_message": "me duele la cabeza",
        "triage_level": "yellow",
        "triage_confidence": 0.9,
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
        "current_node": "guardrail",
        "force_close": False,
        "created_at": "2026-04-09T00:00:00",
        "updated_at": "2026-04-09T00:00:00",
    }
    base.update(overrides)
    return base


def make_agent_with_mock(mock_result: GuardrailCheck) -> GuardrailAgent:
    """Create a GuardrailAgent with mocked LLM ainvoke."""
    agent = GuardrailAgent.__new__(GuardrailAgent)
    agent.llm = MagicMock()
    agent.llm.ainvoke = AsyncMock(return_value=mock_result)
    return agent


class TestGuardrailAgent:
    @pytest.mark.asyncio
    async def test_returns_correct_state_keys(self):
        agent = make_agent_with_mock(GuardrailCheck(approved=True))
        result = await agent(make_state())
        assert "guardrail_violations" in result
        assert "guardrail_interrupt" in result
        assert "current_node" in result
        assert result["current_node"] == "guardrail"

    @pytest.mark.asyncio
    async def test_approved_content_no_violations(self):
        agent = make_agent_with_mock(GuardrailCheck(approved=True))
        state = make_state(
            synthesized_response=(
                "Basándonos en tu consulta, te recomendamos ver un médico. "
                "Esta orientación no reemplaza la consulta médica presencial."
            )
        )
        result = await agent(state)
        assert result["guardrail_violations"] == []
        assert result["guardrail_interrupt"] is False

    @pytest.mark.asyncio
    async def test_approved_false_populates_violations(self):
        violation = SafetyViolation(
            violation_type="definitive_diagnosis",
            description="Diagnóstico definitivo detectado",
            severity="high",
        )
        mock_check = GuardrailCheck(
            approved=False,
            violations=[violation],
            interruption_level=InterruptionLevel.MODIFY,
        )
        agent = make_agent_with_mock(mock_check)
        state = make_state(synthesized_response="Tenés diabetes tipo 2.")
        result = await agent(state)
        assert len(result["guardrail_violations"]) > 0
        assert result["guardrail_interrupt"] is False  # MODIFY, not INTERRUPT

    @pytest.mark.asyncio
    async def test_interrupt_level_sets_guardrail_interrupt_true(self):
        violation = SafetyViolation(
            violation_type="prescription_with_dose",
            description="Prescripción con dosis",
            severity="critical",
        )
        mock_check = GuardrailCheck(
            approved=False,
            violations=[violation],
            interruption_level=InterruptionLevel.INTERRUPT,
            escalation_required=True,
            escalation_reason="Prescripción peligrosa",
        )
        agent = make_agent_with_mock(mock_check)
        state = make_state(synthesized_response="Tomá amoxicilina 500mg cada 8 horas por 7 días.")
        result = await agent(state)
        assert result["guardrail_interrupt"] is True

    @pytest.mark.asyncio
    async def test_empty_state_no_content_to_check(self):
        """No synthesized_response and no specialist_outputs — LLM never called."""
        agent = GuardrailAgent.__new__(GuardrailAgent)
        agent.llm = MagicMock()
        agent.llm.ainvoke = AsyncMock(side_effect=Exception("Should not be called"))
        result = await agent(make_state())
        assert result["guardrail_violations"] == []
        assert result["guardrail_interrupt"] is False

    @pytest.mark.asyncio
    async def test_specialist_outputs_are_checked(self):
        agent = make_agent_with_mock(GuardrailCheck(approved=True))
        state = make_state(
            specialist_outputs={
                "cardiologia": {
                    "clinical_impression": "El paciente tiene hipertensión severa.",
                    "recommendations": ["Consultar cardiólogo"],
                    "alarm_signs": [],
                    "differential_diagnosis": [],
                }
            }
        )
        result = await agent(state)
        agent.llm.ainvoke.assert_called_once()
        assert result["current_node"] == "guardrail"

    # ---- Fix A.2 — modify severity must rewrite the patient response ----

    @pytest.mark.asyncio
    async def test_modify_severity_replaces_response(self):
        """interruption_level=modify MUST overwrite the patient-facing response."""
        violation = SafetyViolation(
            violation_type="prescription_with_dose",
            description="Prescripción con dosis sin receta",
            severity="high",
        )
        suggested = "Te sugiero consultar a tu médico antes de tomar medicación."
        mock_check = GuardrailCheck(
            approved=False,
            violations=[violation],
            interruption_level=InterruptionLevel.MODIFY,
            modifications_suggested=[suggested],
        )
        agent = make_agent_with_mock(mock_check)
        state = make_state(
            synthesized_response="tomá ibuprofeno 400mg cada 8hs"
        )
        result = await agent(state)
        assert result["synthesized_response"] == suggested
        assert "ibuprofeno" not in result["synthesized_response"].lower()

    @pytest.mark.asyncio
    async def test_modify_severity_falls_back_to_original_when_no_suggestion(self):
        """If modifications_suggested is empty, keep original (do not blank it out)."""
        violation = SafetyViolation(
            violation_type="definitive_diagnosis",
            description="Diagnóstico definitivo",
            severity="medium",
        )
        mock_check = GuardrailCheck(
            approved=False,
            violations=[violation],
            interruption_level=InterruptionLevel.MODIFY,
            modifications_suggested=[],
        )
        agent = make_agent_with_mock(mock_check)
        original = "El cuadro es compatible con migraña."
        state = make_state(synthesized_response=original)
        result = await agent(state)
        assert result["synthesized_response"] == original

    @pytest.mark.asyncio
    async def test_observe_severity_does_not_replace_response(self):
        """OBSERVE level must never overwrite the response."""
        mock_check = GuardrailCheck(
            approved=True,
            interruption_level=InterruptionLevel.OBSERVE,
            modifications_suggested=["debería ignorarse"],
        )
        agent = make_agent_with_mock(mock_check)
        original = "Recomendamos descanso e hidratación."
        state = make_state(synthesized_response=original)
        result = await agent(state)
        assert result["synthesized_response"] == original
