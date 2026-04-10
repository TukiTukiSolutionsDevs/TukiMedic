"""
Tests for new Specialist Agents — internal_medicine, pediatrics, gynecology, pharmacology.

Tests TDD (RED first):
1. test_internal_medicine_agent — returns SpecialistAnalysis
2. test_pediatrics_agent — returns SpecialistAnalysis
3. test_gynecology_agent — returns SpecialistAnalysis
4. test_pharmacology_agent — returns PharmacologyAnalysis with interactions
5. test_pharmacology_empty_meds — no medications → empty analysis
"""

import pytest
from unittest.mock import AsyncMock, MagicMock

from app.agents.specialists.schemas import SpecialistAnalysis, DiagnosisHypothesis


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_state(**overrides) -> dict:
    base = {
        "case_id": "test-001",
        "user_id": "user-001",
        "messages": [],
        "current_message": "Tengo dolor de cabeza",
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
        "document_context": {},
        "created_at": "2026-04-10T00:00:00",
        "updated_at": "2026-04-10T00:00:00",
    }
    base.update(overrides)
    return base


def make_analysis(specialty_name: str = "test") -> dict:
    return {
        "specialty_name": specialty_name,
        "clinical_impression": f"Impresión clínica de {specialty_name}",
        "differential_diagnosis": [
            {
                "condition": "Condición de prueba",
                "probability": "media",
                "supporting_evidence": ["evidencia 1"],
                "against_evidence": [],
            }
        ],
        "suggested_studies": ["Hemograma"],
        "risk_factors": ["factor 1"],
        "recommendations": ["recomendación 1"],
        "alarm_signs": ["signo 1"],
        "confidence": 0.7,
        "needs_referral": False,
        "referral_to": [],
    }


def _make_agent_no_llm(agent_class):
    """Instantiate agent without triggering ChatOpenAI init."""
    agent = object.__new__(agent_class)
    agent.llm = MagicMock()
    return agent


# ---------------------------------------------------------------------------
# InternalMedicineAgent
# ---------------------------------------------------------------------------

class TestInternalMedicineAgent:
    def test_specialty_name(self):
        from app.agents.specialists.internal_medicine import InternalMedicineAgent
        assert InternalMedicineAgent.specialty_name == "medicina_interna"

    def test_system_prompt_non_empty(self):
        from app.agents.specialists.internal_medicine import InternalMedicineAgent
        agent = _make_agent_no_llm(InternalMedicineAgent)
        assert len(agent.system_prompt) > 100

    def test_system_prompt_mentions_interna(self):
        from app.agents.specialists.internal_medicine import InternalMedicineAgent
        agent = _make_agent_no_llm(InternalMedicineAgent)
        prompt_lower = agent.system_prompt.lower()
        assert "interna" in prompt_lower or "internist" in prompt_lower

    @pytest.mark.asyncio
    async def test_internal_medicine_returns_specialist_analysis(self):
        """InternalMedicineAgent.__call__ returns specialist_outputs with SpecialistAnalysis."""
        from app.agents.specialists.internal_medicine import InternalMedicineAgent

        agent = _make_agent_no_llm(InternalMedicineAgent)
        mock_result = SpecialistAnalysis(**make_analysis("medicina_interna"))
        agent.llm = AsyncMock()
        agent.llm.ainvoke = AsyncMock(return_value=mock_result)

        state = make_state()
        result = await agent(state)

        assert "specialist_outputs" in result
        assert "current_node" in result
        assert "medicina_interna" in result["specialist_outputs"]
        assert result["current_node"] == "specialist_medicina_interna"

    @pytest.mark.asyncio
    async def test_internal_medicine_merges_existing_outputs(self):
        """Does not overwrite other specialist outputs already in state."""
        from app.agents.specialists.internal_medicine import InternalMedicineAgent

        agent = _make_agent_no_llm(InternalMedicineAgent)
        mock_result = SpecialistAnalysis(**make_analysis("medicina_interna"))
        agent.llm = AsyncMock()
        agent.llm.ainvoke = AsyncMock(return_value=mock_result)

        existing = {"medicina_general": {"clinical_impression": "General impression"}}
        state = make_state(specialist_outputs=existing)
        result = await agent(state)

        outputs = result["specialist_outputs"]
        assert "medicina_general" in outputs
        assert "medicina_interna" in outputs


# ---------------------------------------------------------------------------
# PediatricsAgent
# ---------------------------------------------------------------------------

class TestPediatricsAgent:
    def test_specialty_name(self):
        from app.agents.specialists.pediatrics import PediatricsAgent
        assert PediatricsAgent.specialty_name == "pediatria"

    def test_system_prompt_non_empty(self):
        from app.agents.specialists.pediatrics import PediatricsAgent
        agent = _make_agent_no_llm(PediatricsAgent)
        assert len(agent.system_prompt) > 100

    def test_system_prompt_mentions_pediatrics(self):
        from app.agents.specialists.pediatrics import PediatricsAgent
        agent = _make_agent_no_llm(PediatricsAgent)
        prompt_lower = agent.system_prompt.lower()
        assert "pediatr" in prompt_lower or "niño" in prompt_lower or "infant" in prompt_lower

    @pytest.mark.asyncio
    async def test_pediatrics_returns_specialist_analysis(self):
        """PediatricsAgent.__call__ returns specialist_outputs with SpecialistAnalysis."""
        from app.agents.specialists.pediatrics import PediatricsAgent

        agent = _make_agent_no_llm(PediatricsAgent)
        mock_result = SpecialistAnalysis(**make_analysis("pediatria"))
        agent.llm = AsyncMock()
        agent.llm.ainvoke = AsyncMock(return_value=mock_result)

        state = make_state()
        result = await agent(state)

        assert "specialist_outputs" in result
        assert "pediatria" in result["specialist_outputs"]
        assert result["current_node"] == "specialist_pediatria"


# ---------------------------------------------------------------------------
# GynecologyAgent
# ---------------------------------------------------------------------------

class TestGynecologyAgent:
    def test_specialty_name(self):
        from app.agents.specialists.gynecology import GynecologyAgent
        assert GynecologyAgent.specialty_name == "ginecologia"

    def test_system_prompt_non_empty(self):
        from app.agents.specialists.gynecology import GynecologyAgent
        agent = _make_agent_no_llm(GynecologyAgent)
        assert len(agent.system_prompt) > 100

    def test_system_prompt_mentions_gynecology(self):
        from app.agents.specialists.gynecology import GynecologyAgent
        agent = _make_agent_no_llm(GynecologyAgent)
        prompt_lower = agent.system_prompt.lower()
        assert "ginecol" in prompt_lower or "obstetri" in prompt_lower or "reproduct" in prompt_lower

    @pytest.mark.asyncio
    async def test_gynecology_returns_specialist_analysis(self):
        """GynecologyAgent.__call__ returns specialist_outputs with SpecialistAnalysis."""
        from app.agents.specialists.gynecology import GynecologyAgent

        agent = _make_agent_no_llm(GynecologyAgent)
        mock_result = SpecialistAnalysis(**make_analysis("ginecologia"))
        agent.llm = AsyncMock()
        agent.llm.ainvoke = AsyncMock(return_value=mock_result)

        state = make_state()
        result = await agent(state)

        assert "specialist_outputs" in result
        assert "ginecologia" in result["specialist_outputs"]
        assert result["current_node"] == "specialist_ginecologia"


# ---------------------------------------------------------------------------
# PharmacologyAgent
# ---------------------------------------------------------------------------

class TestPharmacologyAgent:
    def test_specialty_name(self):
        from app.agents.specialists.pharmacology import PharmacologyAgent
        assert PharmacologyAgent.specialty_name == "farmacologia"

    def test_does_not_extend_base_specialist(self):
        """PharmacologyAgent has its own schema — NOT a BaseSpecialistAgent."""
        from app.agents.specialists.pharmacology import PharmacologyAgent
        from app.agents.specialists.base import BaseSpecialistAgent
        assert not issubclass(PharmacologyAgent, BaseSpecialistAgent)

    def test_pharmacology_analysis_schema(self):
        """PharmacologyAnalysis schema validates correctly."""
        from app.agents.specialists.pharmacology import PharmacologyAnalysis, DrugInteraction

        interaction = DrugInteraction(
            drug_a="ibuprofeno",
            drug_b="warfarina",
            severity="severe",
            mechanism="Inhibición COX-1 aumenta riesgo de sangrado",
            recommendation="Evitar combinación, monitorear INR",
        )
        analysis = PharmacologyAnalysis(
            medications_identified=["ibuprofeno", "warfarina"],
            interactions=[interaction],
            warnings=["Riesgo de sangrado elevado"],
            recommendations=["Consultar médico antes de combinar"],
        )
        assert len(analysis.medications_identified) == 2
        assert len(analysis.interactions) == 1
        assert analysis.interactions[0].severity == "severe"

    @pytest.mark.asyncio
    async def test_pharmacology_agent_returns_pharmacology_analysis(self):
        """PharmacologyAgent.__call__ returns specialist_outputs with PharmacologyAnalysis."""
        from app.agents.specialists.pharmacology import PharmacologyAgent, PharmacologyAnalysis, DrugInteraction

        agent = object.__new__(PharmacologyAgent)

        mock_result = PharmacologyAnalysis(
            medications_identified=["ibuprofeno", "paracetamol"],
            interactions=[
                DrugInteraction(
                    drug_a="ibuprofeno",
                    drug_b="paracetamol",
                    severity="mild",
                    mechanism="Ambos son analgésicos — carga hepática",
                    recommendation="Monitorear función hepática con uso prolongado",
                )
            ],
            warnings=["Monitorear función hepática"],
            recommendations=["No exceder dosis recomendada"],
        )

        mock_structured = MagicMock()
        mock_structured.ainvoke = AsyncMock(return_value=mock_result)
        mock_llm = MagicMock()
        mock_llm.with_structured_output.return_value = mock_structured
        agent.llm = mock_llm

        state = make_state(
            messages=[{"role": "user", "content": "Tomo ibuprofeno y paracetamol juntos"}],
            extracted_facts=[{"key": "medication", "value": "ibuprofeno 400mg"}],
        )
        result = await agent(state)

        assert "specialist_outputs" in result
        assert "farmacologia" in result["specialist_outputs"]
        output = result["specialist_outputs"]["farmacologia"]
        assert "medications_identified" in output
        assert "ibuprofeno" in output["medications_identified"]
        assert "interactions" in output

    @pytest.mark.asyncio
    async def test_pharmacology_empty_meds(self):
        """No medications in state → PharmacologyAnalysis with empty lists."""
        from app.agents.specialists.pharmacology import PharmacologyAgent, PharmacologyAnalysis

        agent = object.__new__(PharmacologyAgent)

        empty_result = PharmacologyAnalysis(
            medications_identified=[],
            interactions=[],
            warnings=[],
            recommendations=[],
        )

        mock_structured = MagicMock()
        mock_structured.ainvoke = AsyncMock(return_value=empty_result)
        mock_llm = MagicMock()
        mock_llm.with_structured_output.return_value = mock_structured
        agent.llm = mock_llm

        state = make_state()
        result = await agent(state)

        assert "specialist_outputs" in result
        output = result["specialist_outputs"]["farmacologia"]
        assert output["medications_identified"] == []
        assert output["interactions"] == []
        assert output["warnings"] == []
