"""
Tests for DevilsAdvocateAgent — schemas and agent behaviour.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock
from pydantic import ValidationError

from app.agents.devils_advocate.schemas import Challenge, ChallengeResult
from app.agents.devils_advocate.agent import DevilsAdvocateAgent


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
        "specialist_outputs": {
            "medicina_general": {
                "specialty_name": "medicina_general",
                "clinical_impression": "Cefalea tensional probable",
                "differential_diagnosis": [
                    {
                        "condition": "Cefalea tensional",
                        "probability": "alta",
                        "supporting_evidence": ["3 días de duración", "sin fiebre"],
                        "against_evidence": [],
                    }
                ],
                "suggested_studies": ["Hemograma"],
                "risk_factors": ["estrés"],
                "recommendations": ["reposo", "analgésicos"],
                "alarm_signs": ["cefalea en trueno"],
                "confidence": 0.75,
                "needs_referral": False,
                "referral_to": [],
            },
            "neurologia": {
                "specialty_name": "neurologia",
                "clinical_impression": "Cefalea primaria, posiblemente tensional o migraña",
                "differential_diagnosis": [
                    {
                        "condition": "Migraña sin aura",
                        "probability": "media",
                        "supporting_evidence": ["carácter pulsátil"],
                        "against_evidence": ["sin náuseas reportadas"],
                    }
                ],
                "suggested_studies": ["RM cerebral si persiste"],
                "risk_factors": [],
                "recommendations": ["triptanos si migraña confirmada"],
                "alarm_signs": ["déficit neurológico focal"],
                "confidence": 0.6,
                "needs_referral": False,
                "referral_to": [],
            },
        },
        "medical_board_result": None,
        "debate_rounds": 1,
        "consensus_level": "partial",
        "challenges": [],
        "false_consensus_risk": 0.0,
        "guardrail_violations": [],
        "guardrail_interrupt": False,
        "synthesized_response": None,
        "attention_level": None,
        "loop_count": 0,
        "max_loops": 3,
        "current_node": "devils_advocate",
        "force_close": False,
        "created_at": "2026-04-09T00:00:00",
        "updated_at": "2026-04-09T00:00:00",
    }
    base.update(overrides)
    return base


def make_challenge(**overrides) -> dict:
    base = {
        "specialist": "medicina_general",
        "challenge": "¿Por qué descartó meningitis sin pruebas?",
        "alternative_hypothesis": "Meningitis bacteriana inicial",
        "unexamined_assumption": "Asume ausencia de fiebre sin confirmación",
    }
    base.update(overrides)
    return base


def make_challenge_result(**overrides) -> dict:
    base = {
        "challenges_per_specialist": [make_challenge()],
        "alternative_hypotheses": ["Meningitis viral", "Hipertensión intracraneal"],
        "unexamined_assumptions": ["Ausencia de fiebre no verificada"],
        "false_consensus_risk": 0.4,
        "critical_questions": ["¿Hay rigidez nucal?", "¿Cuánto exactamente dura el dolor?"],
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# Challenge — schema validation
# ---------------------------------------------------------------------------

class TestChallenge:
    def test_valid_full(self):
        c = Challenge(**make_challenge())
        assert c.specialist == "medicina_general"
        assert c.alternative_hypothesis != ""

    def test_unexamined_assumption_defaults_to_empty(self):
        data = make_challenge()
        data.pop("unexamined_assumption")
        c = Challenge(**data)
        assert c.unexamined_assumption == ""

    def test_missing_required_field_rejected(self):
        with pytest.raises(ValidationError):
            Challenge(specialist="x", challenge="y")  # missing alternative_hypothesis

    def test_all_required_fields_present(self):
        c = Challenge(
            specialist="neurologia",
            challenge="¿Descartó HSA?",
            alternative_hypothesis="Hemorragia subaracnoidea",
        )
        assert c.specialist == "neurologia"
        assert c.challenge == "¿Descartó HSA?"
        assert c.alternative_hypothesis == "Hemorragia subaracnoidea"


# ---------------------------------------------------------------------------
# ChallengeResult — schema validation
# ---------------------------------------------------------------------------

class TestChallengeResult:
    def test_valid_full(self):
        r = ChallengeResult(**make_challenge_result())
        assert len(r.challenges_per_specialist) == 1
        assert r.false_consensus_risk == 0.4

    def test_false_consensus_risk_zero(self):
        r = ChallengeResult(**make_challenge_result(false_consensus_risk=0.0))
        assert r.false_consensus_risk == 0.0

    def test_false_consensus_risk_one(self):
        r = ChallengeResult(**make_challenge_result(false_consensus_risk=1.0))
        assert r.false_consensus_risk == 1.0

    def test_false_consensus_risk_below_zero_rejected(self):
        with pytest.raises(ValidationError):
            ChallengeResult(**make_challenge_result(false_consensus_risk=-0.1))

    def test_false_consensus_risk_above_one_rejected(self):
        with pytest.raises(ValidationError):
            ChallengeResult(**make_challenge_result(false_consensus_risk=1.1))

    def test_multiple_challenges(self):
        challenges = [
            make_challenge(specialist="medicina_general"),
            make_challenge(specialist="neurologia", challenge="¿Descartó HSA?",
                           alternative_hypothesis="HSA"),
        ]
        r = ChallengeResult(**make_challenge_result(challenges_per_specialist=challenges))
        assert len(r.challenges_per_specialist) == 2

    def test_defaults_are_empty_lists(self):
        data = make_challenge_result()
        data.pop("alternative_hypotheses")
        data.pop("unexamined_assumptions")
        data.pop("critical_questions")
        r = ChallengeResult(**data)
        assert r.alternative_hypotheses == []
        assert r.unexamined_assumptions == []
        assert r.critical_questions == []

    def test_model_dump_roundtrip(self):
        r = ChallengeResult(**make_challenge_result())
        dumped = r.model_dump()
        assert "challenges_per_specialist" in dumped
        assert "false_consensus_risk" in dumped
        assert isinstance(dumped["challenges_per_specialist"], list)

    def test_challenge_nested_in_result(self):
        r = ChallengeResult(**make_challenge_result())
        first = r.challenges_per_specialist[0]
        assert isinstance(first, Challenge)
        assert first.specialist == "medicina_general"


# ---------------------------------------------------------------------------
# DevilsAdvocateAgent — behaviour with mocked LLM
# ---------------------------------------------------------------------------

class ConcreteDevil:
    """Minimal stand-in that skips LLM init."""
    def __init__(self):
        self.llm = MagicMock()

    _format_specialist_analyses = DevilsAdvocateAgent._format_specialist_analyses
    __call__ = DevilsAdvocateAgent.__call__


class TestDevilsAdvocateAgent:
    @pytest.mark.asyncio
    async def test_returns_required_state_keys(self):
        agent = ConcreteDevil()
        mock_result = ChallengeResult(**make_challenge_result())
        agent.llm = AsyncMock()
        agent.llm.ainvoke = AsyncMock(return_value=mock_result)

        result = await agent(make_state())

        assert "challenges" in result
        assert "false_consensus_risk" in result
        assert "current_node" in result

    @pytest.mark.asyncio
    async def test_current_node_is_devils_advocate(self):
        agent = ConcreteDevil()
        mock_result = ChallengeResult(**make_challenge_result())
        agent.llm = AsyncMock()
        agent.llm.ainvoke = AsyncMock(return_value=mock_result)

        result = await agent(make_state())
        assert result["current_node"] == "devils_advocate"

    @pytest.mark.asyncio
    async def test_challenges_is_list_of_dicts(self):
        agent = ConcreteDevil()
        mock_result = ChallengeResult(**make_challenge_result())
        agent.llm = AsyncMock()
        agent.llm.ainvoke = AsyncMock(return_value=mock_result)

        result = await agent(make_state())
        assert isinstance(result["challenges"], list)
        assert all(isinstance(c, dict) for c in result["challenges"])

    @pytest.mark.asyncio
    async def test_false_consensus_risk_propagated(self):
        agent = ConcreteDevil()
        mock_result = ChallengeResult(**make_challenge_result(false_consensus_risk=0.7))
        agent.llm = AsyncMock()
        agent.llm.ainvoke = AsyncMock(return_value=mock_result)

        result = await agent(make_state())
        assert result["false_consensus_risk"] == 0.7

    @pytest.mark.asyncio
    async def test_reads_specialist_outputs_from_state(self):
        """The agent passes specialist_outputs content to the LLM."""
        agent = ConcreteDevil()
        mock_result = ChallengeResult(**make_challenge_result())
        agent.llm = AsyncMock()
        agent.llm.ainvoke = AsyncMock(return_value=mock_result)

        state = make_state()
        await agent(state)

        call_args = agent.llm.ainvoke.call_args[0][0]
        user_message = call_args[1]["content"]
        # Both specialists should appear in the prompt
        assert "medicina_general" in user_message
        assert "neurologia" in user_message

    @pytest.mark.asyncio
    async def test_challenges_contain_specialist_field(self):
        agent = ConcreteDevil()
        mock_result = ChallengeResult(**make_challenge_result())
        agent.llm = AsyncMock()
        agent.llm.ainvoke = AsyncMock(return_value=mock_result)

        result = await agent(make_state())
        for ch in result["challenges"]:
            assert "specialist" in ch
            assert "challenge" in ch
            assert "alternative_hypothesis" in ch

    @pytest.mark.asyncio
    async def test_empty_specialist_outputs_handled(self):
        """Agent does not crash when specialist_outputs is empty."""
        agent = ConcreteDevil()
        mock_result = ChallengeResult(**make_challenge_result(challenges_per_specialist=[]))
        agent.llm = AsyncMock()
        agent.llm.ainvoke = AsyncMock(return_value=mock_result)

        state = make_state(specialist_outputs={})
        result = await agent(state)
        assert result["challenges"] == []
