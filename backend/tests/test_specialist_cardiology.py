"""
Tests for CardiologyAgent — TDD RED first.

Coverage:
1. Class metadata: specialty_name, prompt non-empty, prompt mentions cardio core.
2. Behavior: __call__ returns SpecialistAnalysis under "cardiologia" key in
   specialist_outputs and emits the right current_node string.
3. Integration with the registry + dispatcher routing path:
   - Registered under the canonical key "cardiologia".
   - The classifier-style accented variant "Cardiología" resolves through
     `_normalize_specialty` to the same agent.
   - get_specialist returns an instance type-correct with the agent class.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.agents.specialists.schemas import SpecialistAnalysis


# ---------------------------------------------------------------------------
# Helpers (kept local to avoid coupling to test_specialist_agents.py module)
# ---------------------------------------------------------------------------

def _make_state(**overrides) -> dict:
    base = {
        "case_id": "test-cardio-001",
        "user_id": "user-001",
        "messages": [],
        "current_message": "Dolor opresivo en el pecho desde hace 30 minutos",
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
        "patient_profile": {},
        "kb_context": "",
        "created_at": "2026-05-01T00:00:00",
        "updated_at": "2026-05-01T00:00:00",
    }
    base.update(overrides)
    return base


def _make_analysis(specialty_name: str = "cardiologia") -> dict:
    return {
        "specialty_name": specialty_name,
        "clinical_impression": (
            "Dolor torácico con características compatibles con angina típica; "
            "estratificar SCA con ECG y troponina."
        ),
        "differential_diagnosis": [
            {
                "condition": "Síndrome coronario agudo (descartar)",
                "probability": "media",
                "supporting_evidence": ["dolor opresivo", "irradiación a brazo izquierdo"],
                "against_evidence": [],
            }
        ],
        "suggested_studies": ["ECG 12 derivaciones", "Troponina alta sensibilidad"],
        "risk_factors": ["HTA", "tabaquismo"],
        "recommendations": [
            "Consulta inmediata a guardia para descartar SCA"
        ],
        "alarm_signs": ["dolor opresivo > 20 min"],
        "confidence": 0.7,
        "needs_referral": True,
        "referral_to": ["Guardia de cardiología"],
    }


def _make_agent_no_llm(agent_class):
    """Bypass __init__ so tests don't need API keys / network."""
    agent = object.__new__(agent_class)
    agent.llm = MagicMock()
    return agent


# ---------------------------------------------------------------------------
# Class metadata
# ---------------------------------------------------------------------------

class TestCardiologyAgentMetadata:
    def test_specialty_name_is_canonical_snake_case(self):
        from app.agents.specialists.cardiology import CardiologyAgent
        assert CardiologyAgent.specialty_name == "cardiologia"

    def test_system_prompt_non_empty(self):
        from app.agents.specialists.cardiology import CardiologyAgent
        agent = _make_agent_no_llm(CardiologyAgent)
        assert len(agent.system_prompt) > 200

    def test_system_prompt_mentions_core_cardio_concepts(self):
        from app.agents.specialists.cardiology import CardiologyAgent
        agent = _make_agent_no_llm(CardiologyAgent)
        prompt_lower = agent.system_prompt.lower()
        # Must mention at least these clinical anchors so the LLM has the
        # right priors when reasoning about cardiac complaints.
        assert "dolor torácico" in prompt_lower or "dolor toracico" in prompt_lower
        assert "ecg" in prompt_lower
        assert any(token in prompt_lower for token in ("sca", "síndrome coronario", "sindrome coronario"))
        assert "insuficiencia cardíaca" in prompt_lower or "insuficiencia cardiaca" in prompt_lower

    def test_system_prompt_mentions_red_flags(self):
        """The prompt MUST surface red flags so the agent escalates correctly."""
        from app.agents.specialists.cardiology import CardiologyAgent
        agent = _make_agent_no_llm(CardiologyAgent)
        prompt_lower = agent.system_prompt.lower()
        assert "guardia" in prompt_lower or "emergencia" in prompt_lower
        assert "síncope" in prompt_lower or "sincope" in prompt_lower


# ---------------------------------------------------------------------------
# Behavior — __call__
# ---------------------------------------------------------------------------

class TestCardiologyAgentBehavior:
    @pytest.mark.asyncio
    async def test_call_returns_specialist_outputs_under_cardiologia_key(self):
        from app.agents.specialists.cardiology import CardiologyAgent

        agent = _make_agent_no_llm(CardiologyAgent)
        mock_result = SpecialistAnalysis(**_make_analysis("cardiologia"))
        agent.llm = AsyncMock()
        agent.llm.ainvoke = AsyncMock(return_value=mock_result)

        result = await agent(_make_state())

        assert "specialist_outputs" in result
        assert "current_node" in result
        assert "cardiologia" in result["specialist_outputs"]
        assert result["current_node"] == "specialist_cardiologia"

    @pytest.mark.asyncio
    async def test_call_does_not_overwrite_other_specialists(self):
        from app.agents.specialists.cardiology import CardiologyAgent

        agent = _make_agent_no_llm(CardiologyAgent)
        mock_result = SpecialistAnalysis(**_make_analysis("cardiologia"))
        agent.llm = AsyncMock()
        agent.llm.ainvoke = AsyncMock(return_value=mock_result)

        existing = {
            "medicina_general": {"clinical_impression": "general view"},
        }
        result = await agent(_make_state(specialist_outputs=existing))

        outputs = result["specialist_outputs"]
        assert "medicina_general" in outputs
        assert "cardiologia" in outputs

    @pytest.mark.asyncio
    async def test_call_uses_safe_ainvoke_fail_open_on_llm_failure(self):
        """If the LLM raises, the agent must still return a usable dict."""
        from app.agents.specialists.cardiology import CardiologyAgent

        agent = _make_agent_no_llm(CardiologyAgent)
        agent.llm = AsyncMock()
        agent.llm.ainvoke = AsyncMock(side_effect=RuntimeError("upstream gone"))

        result = await agent(_make_state())

        assert "specialist_outputs" in result
        # Fallback shape: confidence=0.0, needs_referral=True, agent_name set.
        out = result["specialist_outputs"]["cardiologia"]
        assert out["specialty_name"] == "cardiologia"
        assert out["confidence"] == 0.0
        assert out["needs_referral"] is True


# ---------------------------------------------------------------------------
# Registry integration
# ---------------------------------------------------------------------------

class TestCardiologyRegistryWiring:
    def test_registry_contains_cardiologia(self):
        # Importing the package triggers @register on import.
        from app.agents import specialists  # noqa: F401
        from app.agents.specialists.registry import REGISTRY
        from app.agents.specialists.cardiology import CardiologyAgent

        assert "cardiologia" in REGISTRY
        assert REGISTRY["cardiologia"] is CardiologyAgent

    def test_classifier_accented_name_resolves_to_cardiology(self):
        """The classifier emits 'Cardiología' (accented, capitalized).

        The normalizer must resolve it to the same registry key — this is
        the bug fix from e7d2885 applied to a NEW specialty.
        """
        from app.agents.specialists.registry import _normalize_specialty
        assert _normalize_specialty("Cardiología") == "cardiologia"
        assert _normalize_specialty("CARDIOLOGÍA") == "cardiologia"
        assert _normalize_specialty(" cardiología ") == "cardiologia"

    def test_get_specialist_returns_cardiology_instance(self):
        """get_specialist with an accented name must build a CardiologyAgent."""
        # Patch ChatOpenAI inside base.py so __init__ doesn't hit network.
        from unittest.mock import patch
        from app.agents.specialists.cardiology import CardiologyAgent
        from app.agents.specialists.registry import get_specialist

        with patch("app.agents.specialists.base.ChatOpenAI") as mock_chat:
            mock_chat.return_value.with_structured_output.return_value = MagicMock()
            instance = get_specialist("Cardiología", api_key="x")

        assert isinstance(instance, CardiologyAgent)
