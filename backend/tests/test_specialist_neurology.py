"""
Tests for NeurologyAgent — TDD RED first.

Coverage:
1. Class metadata: specialty_name, prompt non-empty, prompt mentions core
   neurological concepts and red flags.
2. Behavior: __call__ returns SpecialistAnalysis under "neurologia" and
   emits the right `current_node` string. Falls open under LLM failure.
3. Registry integration: registered, accented variant resolves correctly.
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
        "case_id": "test-neuro-001",
        "user_id": "user-001",
        "messages": [],
        "current_message": (
            "Tengo la peor cefalea de mi vida, empezó de golpe hace una hora "
            "y no se alivia con nada."
        ),
        "triage_level": "red",
        "triage_confidence": 0.9,
        "red_flags": ["cefalea en estallido"],
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


def _make_analysis(specialty_name: str = "neurologia") -> dict:
    return {
        "specialty_name": specialty_name,
        "clinical_impression": (
            "Cefalea en estallido — sospecha de hemorragia subaracnoidea "
            "hasta demostrar lo contrario; requiere TC craneal urgente."
        ),
        "differential_diagnosis": [
            {
                "condition": "Hemorragia subaracnoidea",
                "probability": "media",
                "supporting_evidence": ["thunderclap", "primera vez", "sin alivio"],
                "against_evidence": [],
            }
        ],
        "suggested_studies": ["TC craneal sin contraste urgente", "punción lumbar si TC normal"],
        "risk_factors": [],
        "recommendations": ["Derivación inmediata a guardia"],
        "alarm_signs": ["thunderclap"],
        "confidence": 0.7,
        "needs_referral": True,
        "referral_to": ["Guardia"],
    }


def _make_agent_no_llm(agent_class):
    agent = object.__new__(agent_class)
    agent.llm = MagicMock()
    return agent


# ---------------------------------------------------------------------------
# Class metadata
# ---------------------------------------------------------------------------

class TestNeurologyAgentMetadata:
    def test_specialty_name_is_canonical(self):
        from app.agents.specialists.neurology import NeurologyAgent
        assert NeurologyAgent.specialty_name == "neurologia"

    def test_system_prompt_non_empty(self):
        from app.agents.specialists.neurology import NeurologyAgent
        agent = _make_agent_no_llm(NeurologyAgent)
        assert len(agent.system_prompt) > 200

    def test_system_prompt_mentions_core_neuro_concepts(self):
        from app.agents.specialists.neurology import NeurologyAgent
        agent = _make_agent_no_llm(NeurologyAgent)
        prompt_lower = agent.system_prompt.lower()
        # AVC / FAST + cefalea + TC are the textbook anchors.
        assert "avc" in prompt_lower or "stroke" in prompt_lower
        assert "fast" in prompt_lower
        assert "cefalea" in prompt_lower
        assert "tc craneal" in prompt_lower or "tc cráneal" in prompt_lower

    def test_system_prompt_mentions_red_flags(self):
        from app.agents.specialists.neurology import NeurologyAgent
        agent = _make_agent_no_llm(NeurologyAgent)
        prompt_lower = agent.system_prompt.lower()
        # Thunderclap → HSA is the most catastrophic miss; must be there.
        assert "thunderclap" in prompt_lower or "estallido" in prompt_lower
        assert "hsa" in prompt_lower or "subaracnoidea" in prompt_lower
        # Status epileptico / meningitis as additional anchors.
        assert "meningitis" in prompt_lower
        assert "status" in prompt_lower or "epiléptico" in prompt_lower or "epileptico" in prompt_lower


# ---------------------------------------------------------------------------
# Behavior — __call__
# ---------------------------------------------------------------------------

class TestNeurologyAgentBehavior:
    @pytest.mark.asyncio
    async def test_call_returns_outputs_under_neurologia_key(self):
        from app.agents.specialists.neurology import NeurologyAgent

        agent = _make_agent_no_llm(NeurologyAgent)
        mock_result = SpecialistAnalysis(**_make_analysis("neurologia"))
        agent.llm = AsyncMock()
        agent.llm.ainvoke = AsyncMock(return_value=mock_result)

        result = await agent(_make_state())

        assert "specialist_outputs" in result
        assert "neurologia" in result["specialist_outputs"]
        assert result["current_node"] == "specialist_neurologia"

    @pytest.mark.asyncio
    async def test_call_does_not_overwrite_other_specialists(self):
        from app.agents.specialists.neurology import NeurologyAgent

        agent = _make_agent_no_llm(NeurologyAgent)
        mock_result = SpecialistAnalysis(**_make_analysis("neurologia"))
        agent.llm = AsyncMock()
        agent.llm.ainvoke = AsyncMock(return_value=mock_result)

        existing = {"medicina_general": {"clinical_impression": "general"}}
        result = await agent(_make_state(specialist_outputs=existing))

        outputs = result["specialist_outputs"]
        assert "medicina_general" in outputs
        assert "neurologia" in outputs

    @pytest.mark.asyncio
    async def test_call_fail_open_on_llm_failure(self):
        from app.agents.specialists.neurology import NeurologyAgent

        agent = _make_agent_no_llm(NeurologyAgent)
        agent.llm = AsyncMock()
        agent.llm.ainvoke = AsyncMock(side_effect=RuntimeError("upstream gone"))

        result = await agent(_make_state())

        out = result["specialist_outputs"]["neurologia"]
        assert out["specialty_name"] == "neurologia"
        assert out["confidence"] == 0.0
        assert out["needs_referral"] is True


# ---------------------------------------------------------------------------
# Registry integration
# ---------------------------------------------------------------------------

class TestNeurologyRegistryWiring:
    def test_registry_contains_neurologia(self):
        from app.agents import specialists  # noqa: F401
        from app.agents.specialists.registry import REGISTRY
        from app.agents.specialists.neurology import NeurologyAgent

        assert "neurologia" in REGISTRY
        assert REGISTRY["neurologia"] is NeurologyAgent

    @pytest.mark.parametrize("classifier_name", [
        "Neurología",
        "NEUROLOGÍA",
        "neurología",
        " Neurología ",
    ])
    def test_accented_variants_resolve(self, classifier_name):
        from app.agents.specialists.neurology import NeurologyAgent
        from app.agents.specialists.registry import get_specialist

        with patch("app.agents.specialists.base.ChatOpenAI") as mock_chat:
            mock_chat.return_value.with_structured_output.return_value = MagicMock()
            instance = get_specialist(classifier_name, api_key="x")

        assert isinstance(instance, NeurologyAgent)
