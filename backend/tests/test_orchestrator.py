"""
Tests for the MedAgent orchestration graph.

All tests run WITHOUT live LLM calls — ChatOpenAI is mocked at every
agent module that imports it. Fast and hermetic.
"""

import asyncio
from contextlib import ExitStack
from unittest.mock import MagicMock, patch

import pytest
from langgraph.graph import END

from app.orchestrator.graph import (
    LOOP_CONFIG,
    _escalation_node,
    _guardrail_router,
    build_graph,
    create_initial_state,
)
from app.orchestrator.state import ClinicalCaseState


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_CHATLLM_TARGETS = [
    "app.agents.triage.agent.ChatOpenAI",
    "app.agents.anamnesis.agent.ChatOpenAI",
    "app.agents.classifier.agent.ChatOpenAI",
    "app.agents.specialists.base.ChatOpenAI",
    "app.agents.medical_board.agent.ChatOpenAI",
    "app.agents.devils_advocate.agent.ChatOpenAI",
    "app.agents.guardrail.agent.ChatOpenAI",
    "app.agents.synthesizer.agent.ChatOpenAI",
]


@pytest.fixture()
def mock_llm():
    """Patch ChatOpenAI across all agent modules — zero real API calls."""
    mock_inst = MagicMock()
    mock_inst.with_structured_output.return_value = mock_inst
    with ExitStack() as stack:
        for target in _CHATLLM_TARGETS:
            m = stack.enter_context(patch(target))
            m.return_value = mock_inst
        yield mock_inst


def _make_state(**overrides) -> ClinicalCaseState:
    base = create_initial_state("case-1", "user-1", "Me duele la cabeza")
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# LOOP_CONFIG
# ---------------------------------------------------------------------------

class TestLoopConfig:
    def test_has_all_expected_keys(self):
        expected = {
            "max_loops", "max_specialists_per_loop", "max_questions_per_turn",
            "min_completeness_for_synthesis", "force_synthesis_after_loops",
            "specialty_activation_threshold", "max_medical_board_extra_rounds",
        }
        assert expected.issubset(set(LOOP_CONFIG.keys()))

    def test_max_loops_is_3(self):
        assert LOOP_CONFIG["max_loops"] == 3

    def test_max_specialists_per_loop_is_4(self):
        assert LOOP_CONFIG["max_specialists_per_loop"] == 4

    def test_max_questions_per_turn_is_4(self):
        assert LOOP_CONFIG["max_questions_per_turn"] == 4

    def test_min_completeness_is_0_6(self):
        assert LOOP_CONFIG["min_completeness_for_synthesis"] == 0.6

    def test_force_synthesis_after_loops_is_true(self):
        assert LOOP_CONFIG["force_synthesis_after_loops"] is True

    def test_specialty_threshold_is_0_4(self):
        assert LOOP_CONFIG["specialty_activation_threshold"] == 0.4

    def test_max_medical_board_extra_rounds_is_2(self):
        assert LOOP_CONFIG["max_medical_board_extra_rounds"] == 2


# ---------------------------------------------------------------------------
# create_initial_state
# ---------------------------------------------------------------------------

class TestCreateInitialState:
    def test_returns_dict(self):
        assert isinstance(create_initial_state("c1", "u1", "msg"), dict)

    def test_identifiers_set_correctly(self):
        s = create_initial_state("case-42", "user-99", "hola")
        assert s["case_id"] == "case-42"
        assert s["user_id"] == "user-99"
        assert s["current_message"] == "hola"

    def test_max_loops_from_loop_config(self):
        assert create_initial_state("c1", "u1", "msg")["max_loops"] == LOOP_CONFIG["max_loops"]

    def test_loop_count_starts_at_zero(self):
        assert create_initial_state("c1", "u1", "msg")["loop_count"] == 0

    def test_triage_level_none(self):
        assert create_initial_state("c1", "u1", "msg")["triage_level"] is None

    def test_triage_confidence_zero(self):
        assert create_initial_state("c1", "u1", "msg")["triage_confidence"] == 0.0

    def test_red_flags_empty(self):
        assert create_initial_state("c1", "u1", "msg")["red_flags"] == []

    def test_messages_empty(self):
        assert create_initial_state("c1", "u1", "msg")["messages"] == []

    def test_extracted_facts_empty(self):
        assert create_initial_state("c1", "u1", "msg")["extracted_facts"] == []

    def test_pending_questions_empty(self):
        assert create_initial_state("c1", "u1", "msg")["pending_questions"] == []

    def test_completeness_score_zero(self):
        assert create_initial_state("c1", "u1", "msg")["completeness_score"] == 0.0

    def test_active_specialties_empty(self):
        assert create_initial_state("c1", "u1", "msg")["active_specialties"] == []

    def test_primary_specialty_none(self):
        assert create_initial_state("c1", "u1", "msg")["primary_specialty"] is None

    def test_specialist_outputs_empty_dict(self):
        assert create_initial_state("c1", "u1", "msg")["specialist_outputs"] == {}

    def test_medical_board_result_none(self):
        assert create_initial_state("c1", "u1", "msg")["medical_board_result"] is None

    def test_debate_rounds_zero(self):
        assert create_initial_state("c1", "u1", "msg")["debate_rounds"] == 0

    def test_consensus_level_none(self):
        assert create_initial_state("c1", "u1", "msg")["consensus_level"] is None

    def test_challenges_empty(self):
        assert create_initial_state("c1", "u1", "msg")["challenges"] == []

    def test_false_consensus_risk_zero(self):
        assert create_initial_state("c1", "u1", "msg")["false_consensus_risk"] == 0.0

    def test_guardrail_violations_empty(self):
        assert create_initial_state("c1", "u1", "msg")["guardrail_violations"] == []

    def test_guardrail_interrupt_false(self):
        assert create_initial_state("c1", "u1", "msg")["guardrail_interrupt"] is False

    def test_synthesized_response_none(self):
        assert create_initial_state("c1", "u1", "msg")["synthesized_response"] is None

    def test_attention_level_none(self):
        assert create_initial_state("c1", "u1", "msg")["attention_level"] is None

    def test_force_close_false(self):
        assert create_initial_state("c1", "u1", "msg")["force_close"] is False

    def test_current_node_empty_string(self):
        assert create_initial_state("c1", "u1", "msg")["current_node"] == ""

    def test_all_required_keys_present(self):
        s = create_initial_state("c1", "u1", "msg")
        required = {
            "case_id", "user_id", "messages", "current_message",
            "triage_level", "triage_confidence", "red_flags",
            "extracted_facts", "pending_questions", "completeness_score",
            "active_specialties", "primary_specialty", "specialist_outputs",
            "medical_board_result", "debate_rounds", "consensus_level",
            "challenges", "false_consensus_risk",
            "guardrail_violations", "guardrail_interrupt",
            "synthesized_response", "attention_level",
            "loop_count", "max_loops", "current_node", "force_close",
            "created_at", "updated_at",
        }
        assert required.issubset(set(s.keys()))


# ---------------------------------------------------------------------------
# _escalation_node
# ---------------------------------------------------------------------------

class TestEscalationNode:
    def test_returns_synthesized_response(self):
        result = asyncio.run(_escalation_node(_make_state(red_flags=[])))
        assert isinstance(result["synthesized_response"], str)
        assert len(result["synthesized_response"]) > 0

    def test_includes_red_flags_in_response(self):
        flags = ["dolor en el pecho", "dificultad para respirar"]
        result = asyncio.run(_escalation_node(_make_state(red_flags=flags)))
        for flag in flags:
            assert flag in result["synthesized_response"]

    def test_attention_level_is_urgencia(self):
        result = asyncio.run(_escalation_node(_make_state(red_flags=[])))
        assert result["attention_level"] == "urgencia"

    def test_current_node_is_escalation(self):
        result = asyncio.run(_escalation_node(_make_state(red_flags=[])))
        assert result["current_node"] == "escalation"

    def test_response_mentions_emergency(self):
        result = asyncio.run(_escalation_node(_make_state(red_flags=[])))
        text = result["synthesized_response"].lower()
        assert any(w in text for w in ["urgencia", "emergencia", "inmediata"])

    def test_empty_red_flags_no_crash(self):
        result = asyncio.run(_escalation_node(_make_state(red_flags=[])))
        assert result["synthesized_response"] is not None

    def test_multiple_flags_all_appear(self):
        flags = ["fiebre alta", "convulsiones", "pérdida de conciencia"]
        result = asyncio.run(_escalation_node(_make_state(red_flags=flags)))
        for flag in flags:
            assert flag in result["synthesized_response"]


# ---------------------------------------------------------------------------
# _guardrail_router
# ---------------------------------------------------------------------------

class TestGuardrailRouter:
    def test_interrupt_true_routes_to_escalation(self):
        assert _guardrail_router(_make_state(guardrail_interrupt=True)) == "escalation"

    def test_interrupt_false_routes_to_end(self):
        assert _guardrail_router(_make_state(guardrail_interrupt=False)) == END

    def test_default_state_routes_to_end(self):
        assert _guardrail_router(_make_state()) == END

    def test_end_matches_langgraph_sentinel(self):
        result = _guardrail_router(_make_state(guardrail_interrupt=False))
        assert result is END or result == END


# ---------------------------------------------------------------------------
# build_graph
# ---------------------------------------------------------------------------

class TestBuildGraph:
    def test_compiles_without_error(self, mock_llm):
        graph = build_graph(api_key="sk-test-00000000000000000000000000000000")
        assert graph is not None

    def test_returns_invocable(self, mock_llm):
        graph = build_graph(api_key="sk-test-00000000000000000000000000000000")
        assert hasattr(graph, "invoke") or hasattr(graph, "ainvoke")

    def test_agents_constructed_with_key(self, mock_llm):
        build_graph(api_key="sk-my-test-key")
        assert mock_llm.with_structured_output.called
