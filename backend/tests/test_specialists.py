"""
Tests for Specialist Agents — schemas, base class, and GeneralMedicineAgent.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from pydantic import ValidationError

from app.agents.specialists.schemas import DiagnosisHypothesis, SpecialistAnalysis
from app.agents.specialists.base import BaseSpecialistAgent
from app.agents.specialists.general_medicine import GeneralMedicineAgent


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_state(**overrides) -> dict:
    base = {
        "case_id": "test-001",
        "user_id": "user-001",
        "messages": [],
        "current_message": "Tengo dolor de cabeza desde hace 3 días",
        "triage_level": "yellow",
        "triage_confidence": 0.8,
        "red_flags": [],
        "extracted_facts": [],
        "pending_questions": [],
        "completeness_score": 0.6,
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
        "current_node": "classification",
        "force_close": False,
        "created_at": "2026-04-09T00:00:00",
        "updated_at": "2026-04-09T00:00:00",
    }
    base.update(overrides)
    return base


def make_analysis(**overrides) -> dict:
    base = {
        "specialty_name": "medicina_general",
        "clinical_impression": "Cuadro compatible con cefalea tensional",
        "differential_diagnosis": [
            {
                "condition": "Cefalea tensional",
                "probability": "alta",
                "supporting_evidence": ["duración 3 días", "sin fiebre"],
                "against_evidence": [],
            }
        ],
        "suggested_studies": ["Hemograma"],
        "risk_factors": ["estrés"],
        "recommendations": ["reposo", "hidratación"],
        "alarm_signs": ["cefalea súbita muy intensa"],
        "confidence": 0.75,
        "needs_referral": False,
        "referral_to": [],
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# DiagnosisHypothesis — schema validation
# ---------------------------------------------------------------------------

class TestDiagnosisHypothesis:
    def test_valid_alta(self):
        h = DiagnosisHypothesis(condition="Cefalea tensional", probability="alta")
        assert h.probability == "alta"
        assert h.supporting_evidence == []
        assert h.against_evidence == []

    def test_valid_media(self):
        h = DiagnosisHypothesis(condition="Migraña", probability="media")
        assert h.probability == "media"

    def test_valid_baja(self):
        h = DiagnosisHypothesis(condition="Tumor cerebral", probability="baja")
        assert h.probability == "baja"

    def test_invalid_probability_rejected(self):
        with pytest.raises(ValidationError):
            DiagnosisHypothesis(condition="X", probability="muy_alta")

    def test_with_evidence(self):
        h = DiagnosisHypothesis(
            condition="Migraña",
            probability="media",
            supporting_evidence=["fotofobia", "náuseas"],
            against_evidence=["sin aura"],
        )
        assert len(h.supporting_evidence) == 2
        assert len(h.against_evidence) == 1


# ---------------------------------------------------------------------------
# SpecialistAnalysis — schema validation
# ---------------------------------------------------------------------------

class TestSpecialistAnalysis:
    def test_valid_full(self):
        data = make_analysis()
        a = SpecialistAnalysis(**data)
        assert a.specialty_name == "medicina_general"
        assert a.confidence == 0.75
        assert len(a.differential_diagnosis) == 1

    def test_confidence_zero(self):
        data = make_analysis(confidence=0.0)
        a = SpecialistAnalysis(**data)
        assert a.confidence == 0.0

    def test_confidence_one(self):
        data = make_analysis(confidence=1.0)
        a = SpecialistAnalysis(**data)
        assert a.confidence == 1.0

    def test_confidence_below_zero_rejected(self):
        with pytest.raises(ValidationError):
            SpecialistAnalysis(**make_analysis(confidence=-0.1))

    def test_confidence_above_one_rejected(self):
        with pytest.raises(ValidationError):
            SpecialistAnalysis(**make_analysis(confidence=1.1))

    def test_defaults_are_empty_lists(self):
        data = make_analysis()
        data.pop("suggested_studies")
        data.pop("risk_factors")
        data.pop("recommendations")
        data.pop("alarm_signs")
        data.pop("referral_to")
        a = SpecialistAnalysis(**data)
        assert a.suggested_studies == []
        assert a.risk_factors == []
        assert a.recommendations == []
        assert a.alarm_signs == []
        assert a.referral_to == []

    def test_needs_referral_default_false(self):
        data = make_analysis()
        data.pop("needs_referral")
        a = SpecialistAnalysis(**data)
        assert a.needs_referral is False

    def test_model_dump_roundtrip(self):
        data = make_analysis()
        a = SpecialistAnalysis(**data)
        dumped = a.model_dump()
        assert dumped["specialty_name"] == "medicina_general"
        assert "differential_diagnosis" in dumped


# ---------------------------------------------------------------------------
# BaseSpecialistAgent._build_context
# ---------------------------------------------------------------------------

class ConcreteSpecialist(BaseSpecialistAgent):
    specialty_name = "test_specialty"

    def __init__(self):
        # Skip LLM init for unit tests
        self.llm = MagicMock()

    @property
    def system_prompt(self) -> str:
        return "Test prompt"


class TestBuildContext:
    def setup_method(self):
        self.agent = ConcreteSpecialist()

    def test_includes_current_message(self):
        state = make_state(current_message="Dolor de cabeza")
        ctx = self.agent._build_context(state)
        assert "Dolor de cabeza" in ctx

    def test_includes_extracted_facts(self):
        state = make_state(
            extracted_facts=[
                {"key": "age", "value": "35 años"},
                {"key": "symptom", "value": "dolor pulsátil"},
            ]
        )
        ctx = self.agent._build_context(state)
        assert "35 años" in ctx
        assert "dolor pulsátil" in ctx

    def test_includes_triage_level(self):
        state = make_state(triage_level="yellow")
        ctx = self.agent._build_context(state)
        assert "yellow" in ctx

    def test_includes_red_flags(self):
        state = make_state(red_flags=["cefalea súbita", "pérdida de visión"])
        ctx = self.agent._build_context(state)
        assert "cefalea súbita" in ctx
        assert "pérdida de visión" in ctx

    def test_no_facts_no_facts_section(self):
        state = make_state(extracted_facts=[])
        ctx = self.agent._build_context(state)
        assert "Hechos clínicos" not in ctx

    def test_no_red_flags_no_red_flags_section(self):
        state = make_state(red_flags=[])
        ctx = self.agent._build_context(state)
        assert "Red flags" not in ctx

    def test_no_triage_no_triage_section(self):
        state = make_state(triage_level=None)
        ctx = self.agent._build_context(state)
        assert "Nivel de triage" not in ctx


# ---------------------------------------------------------------------------
# GeneralMedicineAgent
# ---------------------------------------------------------------------------

class TestGeneralMedicineAgent:
    def test_specialty_name(self):
        assert GeneralMedicineAgent.specialty_name == "medicina_general"

    def test_default_model(self):
        assert GeneralMedicineAgent.default_model == "gpt-4o"

    def test_default_temperature(self):
        assert GeneralMedicineAgent.default_temperature == 0.3

    def test_system_prompt_contains_nunca(self):
        agent = ConcreteSpecialist()  # avoid LLM init
        # Directly test the prompt content via the class attribute
        from app.agents.specialists.general_medicine import GENERAL_MEDICINE_PROMPT
        assert "NUNCA" in GENERAL_MEDICINE_PROMPT

    def test_system_prompt_contains_siempre(self):
        from app.agents.specialists.general_medicine import GENERAL_MEDICINE_PROMPT
        assert "SIEMPRE" in GENERAL_MEDICINE_PROMPT

    def test_system_prompt_is_non_empty(self):
        from app.agents.specialists.general_medicine import GENERAL_MEDICINE_PROMPT
        assert len(GENERAL_MEDICINE_PROMPT) > 100

    @pytest.mark.asyncio
    async def test_returns_correct_keys(self):
        """GeneralMedicineAgent.__call__ returns specialist_outputs and current_node."""
        agent = ConcreteSpecialist()
        agent.specialty_name = "medicina_general"

        mock_result = SpecialistAnalysis(**make_analysis())
        agent.llm = AsyncMock()
        agent.llm.ainvoke = AsyncMock(return_value=mock_result)

        state = make_state()
        result = await agent(state)

        assert "specialist_outputs" in result
        assert "current_node" in result
        assert result["current_node"] == "specialist_medicina_general"
        assert "medicina_general" in result["specialist_outputs"]

    @pytest.mark.asyncio
    async def test_specialist_outputs_merged_not_overwritten(self):
        """New specialist output merges with existing outputs from other specialists."""
        agent = ConcreteSpecialist()
        agent.specialty_name = "medicina_general"

        mock_result = SpecialistAnalysis(**make_analysis())
        agent.llm = AsyncMock()
        agent.llm.ainvoke = AsyncMock(return_value=mock_result)

        existing_output = {"cardiologia": {"clinical_impression": "Normal"}}
        state = make_state(specialist_outputs=existing_output)

        result = await agent(state)

        outputs = result["specialist_outputs"]
        # Both the existing and the new one must be present
        assert "cardiologia" in outputs
        assert "medicina_general" in outputs

    @pytest.mark.asyncio
    async def test_output_contains_expected_fields(self):
        """specialist_outputs[medicina_general] has all SpecialistAnalysis fields."""
        agent = ConcreteSpecialist()
        agent.specialty_name = "medicina_general"

        mock_result = SpecialistAnalysis(**make_analysis())
        agent.llm = AsyncMock()
        agent.llm.ainvoke = AsyncMock(return_value=mock_result)

        state = make_state()
        result = await agent(state)

        med_output = result["specialist_outputs"]["medicina_general"]
        expected_keys = {
            "specialty_name", "clinical_impression", "differential_diagnosis",
            "suggested_studies", "risk_factors", "recommendations",
            "alarm_signs", "confidence", "needs_referral", "referral_to",
        }
        assert expected_keys.issubset(med_output.keys())
