"""
Tests — BUG 1: agents must accept chat_model; build_graph must use tier routing.

RED phase: agents currently don't accept chat_model param; build_graph still
constructs ChatOpenAI directly inside each agent constructor.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.services.llm_router import ProviderCredentialDTO


def _mock_model() -> MagicMock:
    m = MagicMock()
    m.with_structured_output.return_value = m
    return m


def _gemini_cred() -> ProviderCredentialDTO:
    return ProviderCredentialDTO(
        provider="gemini",
        api_key="sk-test",
        base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
    )


# ---------------------------------------------------------------------------
# Each agent accepts chat_model as primary constructor arg
# ---------------------------------------------------------------------------


class TestAgentsAcceptChatModel:
    """chat_model=<pre-built ChatOpenAI> replaces api_key/model/base_url in __init__."""

    def test_triage_agent_accepts_chat_model(self):
        from app.agents.triage.agent import TriageAgent
        model = _mock_model()
        TriageAgent(chat_model=model)
        model.with_structured_output.assert_called_once()

    def test_anamnesis_agent_accepts_chat_model(self):
        from app.agents.anamnesis.agent import AnamnesisAgent
        model = _mock_model()
        AnamnesisAgent(chat_model=model)
        model.with_structured_output.assert_called_once()

    def test_classifier_agent_accepts_chat_model(self):
        from app.agents.classifier.agent import ClassifierAgent
        model = _mock_model()
        ClassifierAgent(chat_model=model)
        model.with_structured_output.assert_called_once()

    def test_medical_board_agent_accepts_chat_model(self):
        from app.agents.medical_board.agent import MedicalBoardAgent
        model = _mock_model()
        MedicalBoardAgent(chat_model=model)
        model.with_structured_output.assert_called_once()

    def test_synthesizer_agent_accepts_chat_model(self):
        from app.agents.synthesizer.agent import SynthesizerAgent
        model = _mock_model()
        SynthesizerAgent(chat_model=model)
        model.with_structured_output.assert_called_once()

    def test_guardrail_agent_accepts_chat_model(self):
        from app.agents.guardrail.agent import GuardrailAgent
        model = _mock_model()
        GuardrailAgent(chat_model=model)
        model.with_structured_output.assert_called_once()

    def test_devils_advocate_accepts_chat_model(self):
        from app.agents.devils_advocate.agent import DevilsAdvocateAgent
        model = _mock_model()
        DevilsAdvocateAgent(chat_model=model)
        model.with_structured_output.assert_called_once()

    def test_base_specialist_accepts_chat_model(self):
        from app.agents.specialists.general_medicine import GeneralMedicineAgent
        model = _mock_model()
        GeneralMedicineAgent(chat_model=model)
        model.with_structured_output.assert_called_once()

    def test_pharmacology_agent_accepts_chat_model(self):
        """PharmacologyAgent stores raw model; with_structured_output called in __call__."""
        from app.agents.specialists.pharmacology import PharmacologyAgent
        model = _mock_model()
        agent = PharmacologyAgent(chat_model=model)
        # stored raw — __call__ calls with_structured_output internally
        assert agent.llm is model


# ---------------------------------------------------------------------------
# build_graph uses get_chat_model (not hardcoded ChatOpenAI)
# ---------------------------------------------------------------------------


class TestBuildGraphTierRouting:
    def test_build_graph_calls_get_chat_model(self):
        """build_graph must route through get_chat_model, not hardcode ChatOpenAI per agent."""
        from app.orchestrator.graph import build_graph
        mock_model = _mock_model()

        with patch("app.orchestrator.graph.get_chat_model", return_value=mock_model) as mock_gcm:
            build_graph(_gemini_cred())

        assert mock_gcm.called, "build_graph did not call get_chat_model"

    def test_build_graph_passes_cred_to_get_chat_model(self):
        """Credential is forwarded so provider resolution works correctly."""
        from app.orchestrator.graph import build_graph
        cred = _gemini_cred()
        mock_model = _mock_model()
        captured_creds = []

        def _capture(tier, passed_cred, **kwargs):
            captured_creds.append(passed_cred)
            return mock_model

        with patch("app.orchestrator.graph.get_chat_model", side_effect=_capture):
            build_graph(cred)

        assert captured_creds, "get_chat_model was never called"
        assert all(c is cred for c in captured_creds), (
            "Not all get_chat_model calls received the correct cred"
        )

    def test_build_graph_uses_valid_tiers_only(self):
        """Every get_chat_model call must use 'fast' or 'smart', never None or custom."""
        from app.orchestrator.graph import build_graph
        mock_model = _mock_model()
        tiers_used = []

        def _capture(tier, cred, **kwargs):
            tiers_used.append(tier)
            return mock_model

        with patch("app.orchestrator.graph.get_chat_model", side_effect=_capture):
            build_graph(_gemini_cred())

        assert tiers_used, "get_chat_model was never called"
        for tier in tiers_used:
            assert tier in ("fast", "smart"), f"Invalid tier passed to get_chat_model: {tier!r}"
