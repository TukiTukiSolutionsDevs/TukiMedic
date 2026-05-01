"""
Tests for TraumatologyAgent + alias resolution — TDD RED first.

Coverage:
1. Class metadata: specialty_name, prompt non-empty, MSK / Ottawa / red flag
   anchors present in the prompt.
2. Behavior: __call__ returns SpecialistAnalysis under "traumatologia" and
   emits the right `current_node` string. Falls open under LLM failure.
3. Registry + dispatcher routing path:
   - Registered under canonical "traumatologia".
   - Accented classifier variant "Traumatología" resolves correctly.
   - Multi-word variants "Traumatología y Ortopedia" and "Medicina Deportiva"
     resolve to the same agent via the ALIASES table (eval ROI: +3 cases).
4. Existing aliases for other specialties keep working (regression coverage).
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agents.specialists.schemas import SpecialistAnalysis


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_state(**overrides) -> dict:
    base = {
        "case_id": "test-trauma-001",
        "user_id": "user-001",
        "messages": [],
        "current_message": (
            "Me caí jugando al fútbol y me lastimé el tobillo derecho, "
            "está hinchado y no puedo apoyar."
        ),
        "triage_level": "yellow",
        "triage_confidence": 0.7,
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
        "patient_profile": {},
        "kb_context": "",
        "created_at": "2026-05-01T00:00:00",
        "updated_at": "2026-05-01T00:00:00",
    }
    base.update(overrides)
    return base


def _make_analysis(specialty_name: str = "traumatologia") -> dict:
    return {
        "specialty_name": specialty_name,
        "clinical_impression": (
            "Esguince de tobillo grado II probable; descartar fractura "
            "con criterios de Ottawa."
        ),
        "differential_diagnosis": [
            {
                "condition": "Esguince ligamentario lateral grado II",
                "probability": "alta",
                "supporting_evidence": ["mecanismo inversión", "edema", "imposibilidad de carga"],
                "against_evidence": [],
            }
        ],
        "suggested_studies": ["Rx tobillo AP + perfil"],
        "risk_factors": ["práctica deportiva"],
        "recommendations": ["RICE 48-72h", "consulta traumatológica programada"],
        "alarm_signs": ["deformidad o crepitación → fractura"],
        "confidence": 0.7,
        "needs_referral": False,
        "referral_to": [],
    }


def _make_agent_no_llm(agent_class):
    agent = object.__new__(agent_class)
    agent.llm = MagicMock()
    return agent


# ---------------------------------------------------------------------------
# Class metadata
# ---------------------------------------------------------------------------

class TestTraumatologyAgentMetadata:
    def test_specialty_name_is_canonical(self):
        from app.agents.specialists.traumatology import TraumatologyAgent
        assert TraumatologyAgent.specialty_name == "traumatologia"

    def test_system_prompt_non_empty(self):
        from app.agents.specialists.traumatology import TraumatologyAgent
        agent = _make_agent_no_llm(TraumatologyAgent)
        assert len(agent.system_prompt) > 200

    def test_system_prompt_mentions_core_msk_concepts(self):
        from app.agents.specialists.traumatology import TraumatologyAgent
        agent = _make_agent_no_llm(TraumatologyAgent)
        prompt_lower = agent.system_prompt.lower()
        # Clinical anchors a traumatology agent must carry.
        assert "lumbalgia" in prompt_lower
        assert "ottawa" in prompt_lower
        assert "esguince" in prompt_lower or "esguinces" in prompt_lower
        assert "fractura" in prompt_lower

    def test_system_prompt_mentions_red_flags(self):
        from app.agents.specialists.traumatology import TraumatologyAgent
        agent = _make_agent_no_llm(TraumatologyAgent)
        prompt_lower = agent.system_prompt.lower()
        # Cauda equina is THE textbook red flag for low back pain.
        assert "cauda equina" in prompt_lower
        # Plus a generic emergency-routing keyword.
        assert "guardia" in prompt_lower or "emergencia" in prompt_lower


# ---------------------------------------------------------------------------
# Behavior — __call__
# ---------------------------------------------------------------------------

class TestTraumatologyAgentBehavior:
    @pytest.mark.asyncio
    async def test_call_returns_outputs_under_traumatologia_key(self):
        from app.agents.specialists.traumatology import TraumatologyAgent

        agent = _make_agent_no_llm(TraumatologyAgent)
        mock_result = SpecialistAnalysis(**_make_analysis("traumatologia"))
        agent.llm = AsyncMock()
        agent.llm.ainvoke = AsyncMock(return_value=mock_result)

        result = await agent(_make_state())

        assert "specialist_outputs" in result
        assert "traumatologia" in result["specialist_outputs"]
        assert result["current_node"] == "specialist_traumatologia"

    @pytest.mark.asyncio
    async def test_call_does_not_overwrite_other_specialists(self):
        from app.agents.specialists.traumatology import TraumatologyAgent

        agent = _make_agent_no_llm(TraumatologyAgent)
        mock_result = SpecialistAnalysis(**_make_analysis("traumatologia"))
        agent.llm = AsyncMock()
        agent.llm.ainvoke = AsyncMock(return_value=mock_result)

        existing = {"medicina_general": {"clinical_impression": "general"}}
        result = await agent(_make_state(specialist_outputs=existing))

        outputs = result["specialist_outputs"]
        assert "medicina_general" in outputs
        assert "traumatologia" in outputs

    @pytest.mark.asyncio
    async def test_call_fail_open_on_llm_failure(self):
        from app.agents.specialists.traumatology import TraumatologyAgent

        agent = _make_agent_no_llm(TraumatologyAgent)
        agent.llm = AsyncMock()
        agent.llm.ainvoke = AsyncMock(side_effect=RuntimeError("upstream gone"))

        result = await agent(_make_state())

        out = result["specialist_outputs"]["traumatologia"]
        assert out["specialty_name"] == "traumatologia"
        assert out["confidence"] == 0.0
        assert out["needs_referral"] is True


# ---------------------------------------------------------------------------
# Registry + alias wiring
# ---------------------------------------------------------------------------

class TestTraumatologyRegistryWiring:
    def test_registry_contains_traumatologia(self):
        from app.agents import specialists  # noqa: F401  (triggers register)
        from app.agents.specialists.registry import REGISTRY
        from app.agents.specialists.traumatology import TraumatologyAgent

        assert "traumatologia" in REGISTRY
        assert REGISTRY["traumatologia"] is TraumatologyAgent

    def test_accented_traumatologia_resolves(self):
        from app.agents.specialists.registry import _normalize_specialty
        assert _normalize_specialty("Traumatología") == "traumatologia"
        assert _normalize_specialty("TRAUMATOLOGÍA") == "traumatologia"

    @pytest.mark.parametrize("classifier_name", [
        "Traumatología y Ortopedia",
        "traumatología y ortopedia",
        "Ortopedia",
        "Medicina Deportiva",
        "medicina deportiva",
    ])
    def test_alias_resolves_to_traumatology(self, classifier_name):
        """Multi-word classifier outputs route to TraumatologyAgent."""
        from app.agents.specialists.cardiology import CardiologyAgent  # noqa: F401
        from app.agents.specialists.traumatology import TraumatologyAgent
        from app.agents.specialists.registry import get_specialist

        with patch("app.agents.specialists.base.ChatOpenAI") as mock_chat:
            mock_chat.return_value.with_structured_output.return_value = MagicMock()
            instance = get_specialist(classifier_name, api_key="x")

        assert instance is not None, f"alias for '{classifier_name}' did not resolve"
        assert isinstance(instance, TraumatologyAgent)


# ---------------------------------------------------------------------------
# Alias regression — other specialties keep their existing aliases
# ---------------------------------------------------------------------------

class TestExistingAliasesStillWork:
    @pytest.mark.parametrize("classifier_name,expected_canonical", [
        ("Medicina Familiar", "medicina_general"),
        ("Medicina General/Familiar", "medicina_general"),
        ("Obstetricia", "ginecologia"),
        ("Ginecología y Obstetricia", "ginecologia"),
    ])
    def test_alias_dispatches_to_expected_specialty(
        self, classifier_name, expected_canonical
    ):
        from app.agents.specialists.registry import get_specialist, REGISTRY

        with patch("app.agents.specialists.base.ChatOpenAI") as mock_chat:
            mock_chat.return_value.with_structured_output.return_value = MagicMock()
            instance = get_specialist(classifier_name, api_key="x")

        assert instance is not None
        # The instance class should match the expected canonical specialty.
        assert isinstance(instance, REGISTRY[expected_canonical])
