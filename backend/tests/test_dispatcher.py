"""
Tests for Specialist Dispatcher — dispatcher.py

Tests TDD (RED first):
1. test_dispatch_no_active_fallback
2. test_dispatch_single_specialist
3. test_dispatch_parallel_multiple
4. test_dispatch_unknown_specialty_fallback
5. test_dispatch_merges_outputs
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_state(**overrides) -> dict:
    base = {
        "case_id": "test-001",
        "user_id": "user-001",
        "messages": [],
        "current_message": "Tengo dolor abdominal",
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


def make_specialist_result(specialty_name: str) -> dict:
    return {
        "specialist_outputs": {
            specialty_name: {"clinical_impression": f"Analysis by {specialty_name}"}
        },
        "current_node": f"specialist_{specialty_name}",
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestDispatcher:
    async def test_dispatch_no_active_fallback(self):
        """Empty active_specialties → falls back to general medicine."""
        from app.agents.specialists.dispatcher import dispatch_specialists

        state = make_state(active_specialties=[])
        mock_result = make_specialist_result("medicina_general")

        mock_instance = AsyncMock(return_value=mock_result)

        with patch("app.agents.specialists.dispatcher.GeneralMedicineAgent") as MockGM:
            MockGM.return_value = mock_instance
            result = await dispatch_specialists(state, api_key="test-key")

        MockGM.assert_called_once_with(api_key="test-key", base_url=None)
        assert "specialist_outputs" in result
        assert "medicina_general" in result["specialist_outputs"]

    async def test_dispatch_single_specialist(self):
        """One active specialty → that specialist runs."""
        from app.agents.specialists.dispatcher import dispatch_specialists

        state = make_state(
            active_specialties=[{"name": "medicina_interna", "weight": 0.8, "reason": "fatiga crónica"}]
        )
        mock_result = make_specialist_result("medicina_interna")
        mock_agent = AsyncMock(return_value=mock_result)

        with patch("app.agents.specialists.dispatcher.get_specialist", return_value=mock_agent) as mock_get:
            result = await dispatch_specialists(state, api_key="test-key")

        mock_get.assert_called_once_with("medicina_interna", "test-key", base_url=None, chat_model=None)
        assert "specialist_outputs" in result
        assert "medicina_interna" in result["specialist_outputs"]

    async def test_dispatch_parallel_multiple(self):
        """Two active specialties → both run and results are merged."""
        from app.agents.specialists.dispatcher import dispatch_specialists

        state = make_state(
            active_specialties=[
                {"name": "medicina_interna", "weight": 0.8, "reason": "test"},
                {"name": "pediatria", "weight": 0.6, "reason": "test"},
            ]
        )

        result_a = make_specialist_result("medicina_interna")
        result_b = make_specialist_result("pediatria")

        mock_agent_a = AsyncMock(return_value=result_a)
        mock_agent_b = AsyncMock(return_value=result_b)

        def get_spec(name, key, base_url=None, chat_model=None):
            if name == "medicina_interna":
                return mock_agent_a
            if name == "pediatria":
                return mock_agent_b
            return None

        with patch("app.agents.specialists.dispatcher.get_specialist", side_effect=get_spec):
            result = await dispatch_specialists(state, api_key="test-key")

        outputs = result["specialist_outputs"]
        assert "medicina_interna" in outputs
        assert "pediatria" in outputs
        # Both agents must have been called
        mock_agent_a.assert_called_once()
        mock_agent_b.assert_called_once()

    async def test_dispatch_unknown_specialty_fallback(self):
        """Unknown specialty name (get_specialist returns None) → fallback to general medicine."""
        from app.agents.specialists.dispatcher import dispatch_specialists

        state = make_state(
            active_specialties=[{"name": "especialidad_rara", "weight": 0.9, "reason": "test"}]
        )
        mock_result = make_specialist_result("medicina_general")
        mock_instance = AsyncMock(return_value=mock_result)

        with patch("app.agents.specialists.dispatcher.get_specialist", return_value=None), \
             patch("app.agents.specialists.dispatcher.GeneralMedicineAgent") as MockGM:
            MockGM.return_value = mock_instance
            result = await dispatch_specialists(state, api_key="test-key")

        MockGM.assert_called_once_with(api_key="test-key", base_url=None)
        assert "medicina_general" in result["specialist_outputs"]

    async def test_dispatch_merges_outputs(self):
        """Multiple specialist results are merged into a single specialist_outputs dict."""
        from app.agents.specialists.dispatcher import dispatch_specialists

        state = make_state(
            active_specialties=[
                {"name": "medicina_interna", "weight": 0.8, "reason": "test"},
                {"name": "ginecologia", "weight": 0.7, "reason": "test"},
            ]
        )

        result_a = {
            "specialist_outputs": {"medicina_interna": {"clinical_impression": "Internal A"}},
            "current_node": "specialist_medicina_interna",
        }
        result_b = {
            "specialist_outputs": {"ginecologia": {"clinical_impression": "Gynecology B"}},
            "current_node": "specialist_ginecologia",
        }

        mock_agent_a = AsyncMock(return_value=result_a)
        mock_agent_b = AsyncMock(return_value=result_b)

        def get_spec(name, key, base_url=None, chat_model=None):
            if name == "medicina_interna":
                return mock_agent_a
            if name == "ginecologia":
                return mock_agent_b
            return None

        with patch("app.agents.specialists.dispatcher.get_specialist", side_effect=get_spec):
            result = await dispatch_specialists(state, api_key="test-key")

        outputs = result["specialist_outputs"]
        assert outputs["medicina_interna"]["clinical_impression"] == "Internal A"
        assert outputs["ginecologia"]["clinical_impression"] == "Gynecology B"
