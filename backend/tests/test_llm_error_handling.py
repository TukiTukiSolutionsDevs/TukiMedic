"""
LLM error-handling tests.

Verify that every agent that calls `llm.ainvoke(...)` gracefully degrades
when the upstream LLM raises (timeouts, rate limits, transport, validation).
Agents must NEVER propagate the exception — they MUST return a valid state
update built from a fail-safe fallback.
"""
from __future__ import annotations

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock

from app.agents._llm_safe import safe_ainvoke
from app.agents.triage.agent import TriageAgent
from app.agents.triage.schemas import TriageResult
from app.agents.anamnesis.agent import AnamnesisAgent
from app.agents.classifier.agent import ClassifierAgent
from app.agents.devils_advocate.agent import DevilsAdvocateAgent
from app.agents.medical_board.agent import MedicalBoardAgent
from app.agents.synthesizer.agent import SynthesizerAgent
from app.agents.guardrail.agent import GuardrailAgent
from app.agents.specialists.general_medicine import GeneralMedicineAgent
from app.agents.specialists.internal_medicine import InternalMedicineAgent
from app.agents.specialists.pediatrics import PediatricsAgent
from app.agents.specialists.gynecology import GynecologyAgent
from app.agents.specialists.pharmacology import PharmacologyAgent


# ---------------------------------------------------------------------------
# Reusable rate-limit-like exception (no SDK dependency required)
# ---------------------------------------------------------------------------
class FakeRateLimitError(Exception):
    """Stand-in for openai.RateLimitError / anthropic.RateLimitError."""


def _agent_without_init(cls):
    """Bypass __init__ so we don't require API keys."""
    return cls.__new__(cls)


def _make_state(message: str = "me duele la cabeza") -> dict:
    """Minimal ClinicalCaseState-shaped dict accepted by all agents."""
    return {
        "current_message": message,
        "extracted_facts": [],
        "pending_questions": [],
        "messages": [],
        "specialist_outputs": {},
        "challenges": [],
        "triage_level": None,
        "red_flags": [],
        "loop_count": 0,
        "completeness_score": 0.0,
        "debate_rounds": 0,
        "patient_profile": {},
        "kb_context": "",
    }


# ===========================================================================
# safe_ainvoke unit tests
# ===========================================================================

class TestSafeAinvoke:
    @pytest.mark.asyncio
    async def test_returns_result_when_llm_succeeds(self):
        llm = MagicMock()
        llm.ainvoke = AsyncMock(return_value="real-result")
        out = await safe_ainvoke(
            llm, "prompt", fallback="FALLBACK", agent_name="test"
        )
        assert out == "real-result"

    @pytest.mark.asyncio
    async def test_returns_fallback_on_timeout(self):
        llm = MagicMock()
        llm.ainvoke = AsyncMock(side_effect=asyncio.TimeoutError())
        out = await safe_ainvoke(
            llm, "prompt", fallback="FALLBACK", agent_name="test"
        )
        assert out == "FALLBACK"

    @pytest.mark.asyncio
    async def test_returns_fallback_on_rate_limit(self):
        llm = MagicMock()
        llm.ainvoke = AsyncMock(side_effect=FakeRateLimitError("429"))
        out = await safe_ainvoke(
            llm, "prompt", fallback="FALLBACK", agent_name="test"
        )
        assert out == "FALLBACK"

    @pytest.mark.asyncio
    async def test_returns_fallback_on_generic_exception(self):
        llm = MagicMock()
        llm.ainvoke = AsyncMock(side_effect=RuntimeError("boom"))
        out = await safe_ainvoke(
            llm, "prompt", fallback="FALLBACK", agent_name="test"
        )
        assert out == "FALLBACK"

    @pytest.mark.asyncio
    async def test_does_not_raise_on_failure(self):
        llm = MagicMock()
        llm.ainvoke = AsyncMock(side_effect=Exception("any"))
        # Must not raise — pytest will surface any exception otherwise.
        await safe_ainvoke(
            llm, "prompt", fallback={"k": "v"}, agent_name="test"
        )


# ===========================================================================
# Per-agent fail-safe tests — TimeoutError + RateLimitError
# ===========================================================================

@pytest.mark.asyncio
async def test_triage_agent_handles_llm_timeout_gracefully():
    agent = _agent_without_init(TriageAgent)
    agent.llm = MagicMock()
    agent.llm.ainvoke = AsyncMock(side_effect=asyncio.TimeoutError())

    result = await agent(_make_state("me siento mal"))
    assert isinstance(result, dict)
    # Fail-safe: defaults to yellow so user is told to seek attention.
    assert result["triage_level"] in ("green", "yellow", "red")
    assert "current_node" in result


@pytest.mark.asyncio
async def test_triage_agent_handles_rate_limit_gracefully():
    agent = _agent_without_init(TriageAgent)
    agent.llm = MagicMock()
    agent.llm.ainvoke = AsyncMock(side_effect=FakeRateLimitError("429"))

    result = await agent(_make_state("me siento mal"))
    assert isinstance(result, dict)
    assert "triage_level" in result


@pytest.mark.asyncio
async def test_anamnesis_agent_handles_llm_timeout_gracefully():
    agent = _agent_without_init(AnamnesisAgent)
    agent.llm = MagicMock()
    agent.llm.ainvoke = AsyncMock(side_effect=asyncio.TimeoutError())

    result = await agent(_make_state())
    assert isinstance(result, dict)
    assert "extracted_facts" in result


@pytest.mark.asyncio
async def test_classifier_agent_handles_rate_limit_gracefully():
    agent = _agent_without_init(ClassifierAgent)
    agent.llm = MagicMock()
    agent.llm.ainvoke = AsyncMock(side_effect=FakeRateLimitError("429"))

    result = await agent(_make_state())
    assert isinstance(result, dict)
    assert "active_specialties" in result


@pytest.mark.asyncio
async def test_devils_advocate_handles_llm_timeout_gracefully():
    agent = _agent_without_init(DevilsAdvocateAgent)
    agent.llm = MagicMock()
    agent.llm.ainvoke = AsyncMock(side_effect=asyncio.TimeoutError())

    state = _make_state()
    state["specialist_outputs"] = {"general": {"clinical_impression": "x"}}
    result = await agent(state)
    assert isinstance(result, dict)
    assert "challenges" in result


@pytest.mark.asyncio
async def test_medical_board_handles_rate_limit_gracefully():
    agent = _agent_without_init(MedicalBoardAgent)
    agent.llm = MagicMock()
    agent.llm.ainvoke = AsyncMock(side_effect=FakeRateLimitError("429"))

    result = await agent(_make_state())
    assert isinstance(result, dict)
    assert "consensus_level" in result


@pytest.mark.asyncio
async def test_synthesizer_handles_llm_timeout_gracefully():
    agent = _agent_without_init(SynthesizerAgent)
    agent.llm = MagicMock()
    agent.llm.ainvoke = AsyncMock(side_effect=asyncio.TimeoutError())

    result = await agent(_make_state())
    assert isinstance(result, dict)
    assert "synthesized_response" in result
    assert isinstance(result["synthesized_response"], str)


@pytest.mark.asyncio
async def test_guardrail_handles_rate_limit_gracefully():
    agent = _agent_without_init(GuardrailAgent)
    agent.llm = MagicMock()
    agent.llm.ainvoke = AsyncMock(side_effect=FakeRateLimitError("429"))

    state = _make_state()
    state["synthesized_response"] = "Tomá un paracetamol"
    result = await agent(state)
    assert isinstance(result, dict)
    assert "guardrail_violations" in result


# Specialists — all share BaseSpecialistAgent except Pharmacology.
@pytest.mark.parametrize("agent_cls", [
    GeneralMedicineAgent,
    InternalMedicineAgent,
    PediatricsAgent,
    GynecologyAgent,
])
@pytest.mark.asyncio
async def test_specialists_handle_llm_timeout_gracefully(agent_cls):
    agent = _agent_without_init(agent_cls)
    agent.llm = MagicMock()
    agent.llm.ainvoke = AsyncMock(side_effect=asyncio.TimeoutError())

    result = await agent(_make_state())
    assert isinstance(result, dict)
    assert "specialist_outputs" in result


@pytest.mark.asyncio
async def test_pharmacology_handles_rate_limit_gracefully():
    agent = _agent_without_init(PharmacologyAgent)

    structured_llm = MagicMock()
    structured_llm.ainvoke = AsyncMock(side_effect=FakeRateLimitError("429"))

    base_llm = MagicMock()
    base_llm.with_structured_output = MagicMock(return_value=structured_llm)
    agent.llm = base_llm

    result = await agent(_make_state())
    assert isinstance(result, dict)
    assert "specialist_outputs" in result
