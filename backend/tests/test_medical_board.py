"""
Tests for MedicalBoardAgent — schemas, router, and agent behaviour.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock
from pydantic import ValidationError

from app.agents.medical_board.schemas import MedicalBoardResult, ChallengeResponse
from app.agents.medical_board.agent import MedicalBoardAgent, medical_board_router, MAX_EXTRA_ROUNDS


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_state(**overrides) -> dict:
    base = {
        "case_id": "test-001",
        "user_id": "user-001",
        "messages": [],
        "current_message": "Tengo dolor abdominal intenso",
        "triage_level": "yellow",
        "triage_confidence": 0.8,
        "red_flags": [],
        "extracted_facts": [],
        "pending_questions": [],
        "completeness_score": 0.7,
        "active_specialties": [],
        "primary_specialty": None,
        "specialist_outputs": {
            "medicina_general": {
                "specialty_name": "medicina_general",
                "clinical_impression": "Posible gastritis",
                "differential_diagnosis": [
                    {"condition": "Gastritis", "probability": "alta",
                     "supporting_evidence": ["dolor epigastrico"], "against_evidence": []},
                ],
                "suggested_studies": ["Hemograma"],
                "risk_factors": [],
                "recommendations": ["dieta blanda"],
                "alarm_signs": ["hematemesis"],
                "confidence": 0.75,
                "needs_referral": False,
                "referral_to": [],
            },
            "medicina_interna": {
                "specialty_name": "medicina_interna",
                "clinical_impression": "Descartar ulcera peptica",
                "differential_diagnosis": [
                    {"condition": "Ulcera peptica", "probability": "media",
                     "supporting_evidence": ["dolor nocturno"], "against_evidence": []},
                ],
                "suggested_studies": ["Endoscopia"],
                "risk_factors": ["AINES"],
                "recommendations": ["omeprazol empirico"],
                "alarm_signs": ["melena"],
                "confidence": 0.65,
                "needs_referral": False,
                "referral_to": [],
            },
        },
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
        "current_node": "medical_board",
        "force_close": False,
        "created_at": "2026-04-09T00:00:00",
        "updated_at": "2026-04-09T00:00:00",
    }
    base.update(overrides)
    return base


def make_board_result(**overrides) -> dict:
    base = {
        "consensus_level": "partial",
        "debate_rounds": 1,
        "key_agreements": ["Proceso digestivo alto"],
        "key_disagreements": ["Gravedad del cuadro"],
        "resolution_path": "synthesis",
        "moderator_summary": "Los especialistas coinciden en origen digestivo.",
        "challenges_addressed": [],
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# ChallengeResponse schema
# ---------------------------------------------------------------------------

class TestChallengeResponse:
    def test_valid_no_change(self):
        cr = ChallengeResponse(
            specialist="medicina_general",
            original_position="Gastritis probable",
            response_to_challenge="Mantengo mi posicion basado en clinica",
            position_changed=False,
        )
        assert cr.position_changed is False
        assert cr.adjusted_analysis == ""

    def test_valid_with_change(self):
        cr = ChallengeResponse(
            specialist="medicina_interna",
            original_position="Ulcera peptica",
            response_to_challenge="Reconozco que ERGE tambien es posible",
            position_changed=True,
            adjusted_analysis="Agrego ERGE como diferencial media",
        )
        assert cr.position_changed is True
        assert "ERGE" in cr.adjusted_analysis

    def test_adjusted_analysis_defaults_to_empty(self):
        cr = ChallengeResponse(
            specialist="x",
            original_position="pos",
            response_to_challenge="resp",
            position_changed=False,
        )
        assert cr.adjusted_analysis == ""

    def test_missing_required_fields_rejected(self):
        with pytest.raises(ValidationError):
            ChallengeResponse(specialist="x")


# ---------------------------------------------------------------------------
# MedicalBoardResult schema
# ---------------------------------------------------------------------------

class TestMedicalBoardResult:
    def test_full_consensus(self):
        r = MedicalBoardResult(**make_board_result(consensus_level="full", resolution_path="synthesis"))
        assert r.consensus_level == "full"
        assert r.debate_rounds >= 1

    def test_partial_consensus(self):
        r = MedicalBoardResult(**make_board_result(consensus_level="partial"))
        assert r.consensus_level == "partial"

    def test_disagreement(self):
        r = MedicalBoardResult(**make_board_result(
            consensus_level="disagreement", resolution_path="extra_round"
        ))
        assert r.consensus_level == "disagreement"
        assert r.resolution_path == "extra_round"

    def test_clarification_path(self):
        r = MedicalBoardResult(**make_board_result(resolution_path="clarification"))
        assert r.resolution_path == "clarification"

    def test_debate_rounds_minimum_1(self):
        r = MedicalBoardResult(**make_board_result(debate_rounds=1))
        assert r.debate_rounds == 1

    def test_debate_rounds_below_1_rejected(self):
        with pytest.raises(ValidationError):
            MedicalBoardResult(**make_board_result(debate_rounds=0))

    def test_invalid_consensus_level_rejected(self):
        with pytest.raises(ValidationError):
            MedicalBoardResult(**make_board_result(consensus_level="unknown"))

    def test_invalid_resolution_path_rejected(self):
        with pytest.raises(ValidationError):
            MedicalBoardResult(**make_board_result(resolution_path="unknown"))

    def test_defaults_are_empty_lists(self):
        data = make_board_result()
        data.pop("key_agreements")
        data.pop("key_disagreements")
        data.pop("challenges_addressed")
        r = MedicalBoardResult(**data)
        assert r.key_agreements == []
        assert r.key_disagreements == []
        assert r.challenges_addressed == []

    def test_with_challenge_responses(self):
        cr = {
            "specialist": "medicina_general",
            "original_position": "Gastritis",
            "response_to_challenge": "Mantengo",
            "position_changed": False,
            "adjusted_analysis": "",
        }
        r = MedicalBoardResult(**make_board_result(challenges_addressed=[cr]))
        assert len(r.challenges_addressed) == 1
        assert r.challenges_addressed[0].specialist == "medicina_general"

    def test_model_dump_roundtrip(self):
        r = MedicalBoardResult(**make_board_result())
        dumped = r.model_dump()
        assert "consensus_level" in dumped
        assert "debate_rounds" in dumped
        assert "resolution_path" in dumped


# ---------------------------------------------------------------------------
# medical_board_router
# ---------------------------------------------------------------------------

class TestMedicalBoardRouter:
    def test_full_consensus_routes_to_synthesis(self):
        state = make_state(
            consensus_level="full",
            debate_rounds=1,
            medical_board_result=make_board_result(
                consensus_level="full", resolution_path="synthesis"
            ),
        )
        assert medical_board_router(state) == "synthesis"

    def test_partial_consensus_routes_to_synthesis(self):
        state = make_state(
            consensus_level="partial",
            debate_rounds=1,
            medical_board_result=make_board_result(
                consensus_level="partial", resolution_path="synthesis"
            ),
        )
        assert medical_board_router(state) == "synthesis"

    def test_disagreement_under_max_routes_to_devils_advocate(self):
        state = make_state(
            consensus_level="disagreement",
            debate_rounds=1,
            medical_board_result=make_board_result(
                consensus_level="disagreement", resolution_path="extra_round"
            ),
        )
        assert medical_board_router(state) == "devils_advocate"

    def test_clarification_routes_to_clarification(self):
        state = make_state(
            consensus_level="disagreement",
            debate_rounds=1,
            medical_board_result=make_board_result(
                consensus_level="disagreement", resolution_path="clarification"
            ),
        )
        assert medical_board_router(state) == "clarification"

    def test_max_rounds_exceeded_forces_synthesis(self):
        over_budget = MAX_EXTRA_ROUNDS + 2
        state = make_state(
            consensus_level="disagreement",
            debate_rounds=over_budget,
            medical_board_result=make_board_result(
                consensus_level="disagreement", resolution_path="extra_round"
            ),
        )
        assert medical_board_router(state) == "synthesis"

    def test_exactly_at_max_still_routes_to_devils_advocate(self):
        boundary = MAX_EXTRA_ROUNDS + 1
        state = make_state(
            consensus_level="disagreement",
            debate_rounds=boundary,
            medical_board_result=make_board_result(
                consensus_level="disagreement", resolution_path="extra_round"
            ),
        )
        assert medical_board_router(state) == "devils_advocate"


# ---------------------------------------------------------------------------
# MedicalBoardAgent — mocked LLM
# ---------------------------------------------------------------------------

class ConcreteBoard:
    """Minimal stand-in that skips LLM init."""
    def __init__(self):
        self.llm = MagicMock()

    _format_specialist_analyses = MedicalBoardAgent._format_specialist_analyses
    _format_challenges = MedicalBoardAgent._format_challenges
    __call__ = MedicalBoardAgent.__call__


class TestMedicalBoardAgent:
    @pytest.mark.asyncio
    async def test_returns_required_state_keys(self):
        agent = ConcreteBoard()
        mock_result = MedicalBoardResult(**make_board_result())
        agent.llm = AsyncMock()
        agent.llm.ainvoke = AsyncMock(return_value=mock_result)

        result = await agent(make_state())
        assert "medical_board_result" in result
        assert "consensus_level" in result
        assert "debate_rounds" in result
        assert "current_node" in result

    @pytest.mark.asyncio
    async def test_current_node_is_medical_board(self):
        agent = ConcreteBoard()
        mock_result = MedicalBoardResult(**make_board_result())
        agent.llm = AsyncMock()
        agent.llm.ainvoke = AsyncMock(return_value=mock_result)

        result = await agent(make_state())
        assert result["current_node"] == "medical_board"

    @pytest.mark.asyncio
    async def test_debate_rounds_increments_from_zero(self):
        agent = ConcreteBoard()
        mock_result = MedicalBoardResult(**make_board_result())
        agent.llm = AsyncMock()
        agent.llm.ainvoke = AsyncMock(return_value=mock_result)

        result = await agent(make_state(debate_rounds=0))
        assert result["debate_rounds"] == 1

    @pytest.mark.asyncio
    async def test_debate_rounds_increments_from_existing(self):
        agent = ConcreteBoard()
        mock_result = MedicalBoardResult(**make_board_result())
        agent.llm = AsyncMock()
        agent.llm.ainvoke = AsyncMock(return_value=mock_result)

        result = await agent(make_state(debate_rounds=2))
        assert result["debate_rounds"] == 3

    @pytest.mark.asyncio
    async def test_medical_board_result_is_dict(self):
        agent = ConcreteBoard()
        mock_result = MedicalBoardResult(**make_board_result())
        agent.llm = AsyncMock()
        agent.llm.ainvoke = AsyncMock(return_value=mock_result)

        result = await agent(make_state())
        assert isinstance(result["medical_board_result"], dict)

    @pytest.mark.asyncio
    async def test_consensus_level_propagated(self):
        agent = ConcreteBoard()
        mock_result = MedicalBoardResult(**make_board_result(consensus_level="full"))
        agent.llm = AsyncMock()
        agent.llm.ainvoke = AsyncMock(return_value=mock_result)

        result = await agent(make_state())
        assert result["consensus_level"] == "full"

    @pytest.mark.asyncio
    async def test_challenges_included_in_context(self):
        agent = ConcreteBoard()
        mock_result = MedicalBoardResult(**make_board_result())
        agent.llm = AsyncMock()
        agent.llm.ainvoke = AsyncMock(return_value=mock_result)

        challenges = [
            {
                "specialist": "medicina_general",
                "challenge": "Por que descarto pancreatitis?",
                "alternative_hypothesis": "Pancreatitis aguda leve",
                "unexamined_assumption": "Asume que no hay irradiacion",
            }
        ]
        await agent(make_state(challenges=challenges))

        call_args = agent.llm.ainvoke.call_args[0][0]
        user_message = call_args[1]["content"]
        assert "Devil" in user_message
