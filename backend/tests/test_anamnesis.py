"""Tests for the Anamnesis Agent — schemas, validation, and agent node."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from pydantic import ValidationError

from app.agents.anamnesis.schemas import (
    AnamnesisResult,
    ClinicalQuestion,
    ClinicalFact,
)


# ========== ClinicalQuestion Schema Tests ==========

class TestClinicalQuestion:
    def test_valid_question(self):
        q = ClinicalQuestion(
            question="¿Desde cuándo tiene el dolor?",
            area="motivo_consulta",
            priority="alta",
            rationale="La duración del síntoma es clave para el diagnóstico diferencial",
        )
        assert q.question == "¿Desde cuándo tiene el dolor?"
        assert q.area == "motivo_consulta"
        assert q.priority == "alta"

    def test_all_valid_areas(self):
        areas = ["datos_basicos", "motivo_consulta", "antecedentes", "contexto"]
        for area in areas:
            q = ClinicalQuestion(
                question="Pregunta de prueba",
                area=area,
                priority="media",
                rationale="Test",
            )
            assert q.area == area

    def test_all_valid_priorities(self):
        for priority in ["alta", "media", "baja"]:
            q = ClinicalQuestion(
                question="Pregunta",
                area="antecedentes",
                priority=priority,
                rationale="Test",
            )
            assert q.priority == priority

    def test_invalid_area_raises(self):
        with pytest.raises(ValidationError):
            ClinicalQuestion(
                question="Pregunta",
                area="diagnostico",  # invalid
                priority="alta",
                rationale="Test",
            )

    def test_invalid_priority_raises(self):
        with pytest.raises(ValidationError):
            ClinicalQuestion(
                question="Pregunta",
                area="contexto",
                priority="urgente",  # invalid
                rationale="Test",
            )


# ========== ClinicalFact Schema Tests ==========

class TestClinicalFact:
    def test_valid_fact(self):
        fact = ClinicalFact(
            fact_type="symptom",
            value="dolor abdominal en fosa ilíaca derecha",
            confidence=0.9,
        )
        assert fact.fact_type == "symptom"
        assert fact.confidence == 0.9

    def test_all_valid_fact_types(self):
        types = [
            "symptom", "antecedent", "medication", "allergy",
            "vital_sign", "lifestyle", "context", "family_history",
        ]
        for ft in types:
            fact = ClinicalFact(fact_type=ft, value="test", confidence=0.5)
            assert fact.fact_type == ft

    def test_confidence_must_be_between_0_and_1(self):
        with pytest.raises(ValidationError):
            ClinicalFact(fact_type="symptom", value="dolor", confidence=1.5)

        with pytest.raises(ValidationError):
            ClinicalFact(fact_type="symptom", value="dolor", confidence=-0.1)

    def test_confidence_boundary_values(self):
        fact_min = ClinicalFact(fact_type="symptom", value="test", confidence=0.0)
        fact_max = ClinicalFact(fact_type="symptom", value="test", confidence=1.0)
        assert fact_min.confidence == 0.0
        assert fact_max.confidence == 1.0

    def test_invalid_fact_type_raises(self):
        with pytest.raises(ValidationError):
            ClinicalFact(fact_type="diagnosis", value="apendicitis", confidence=0.8)


# ========== AnamnesisResult Schema Tests ==========

class TestAnamnesisResult:
    def _make_question(self, text: str = "¿Desde cuándo?") -> ClinicalQuestion:
        return ClinicalQuestion(
            question=text,
            area="motivo_consulta",
            priority="alta",
            rationale="Duración es dato clave",
        )

    def _make_fact(self) -> ClinicalFact:
        return ClinicalFact(fact_type="symptom", value="cefalea", confidence=0.85)

    def test_valid_result(self):
        result = AnamnesisResult(
            questions=[self._make_question()],
            extracted_facts=[self._make_fact()],
            completeness_score=0.3,
            critical_gaps=["Duración del dolor", "Medicación actual"],
        )
        assert len(result.questions) == 1
        assert result.completeness_score == 0.3

    def test_max_four_questions_passes(self):
        questions = [self._make_question(f"Pregunta {i}") for i in range(4)]
        result = AnamnesisResult(
            questions=questions,
            completeness_score=0.2,
        )
        assert len(result.questions) == 4

    def test_five_questions_raises(self):
        questions = [self._make_question(f"Pregunta {i}") for i in range(5)]
        with pytest.raises(ValidationError) as exc_info:
            AnamnesisResult(questions=questions, completeness_score=0.2)
        assert "4" in str(exc_info.value) or "preguntas" in str(exc_info.value).lower()

    def test_completeness_score_range(self):
        # Valid boundary values
        r_min = AnamnesisResult(questions=[], completeness_score=0.0)
        r_max = AnamnesisResult(questions=[], completeness_score=1.0)
        assert r_min.completeness_score == 0.0
        assert r_max.completeness_score == 1.0

    def test_completeness_score_above_1_raises(self):
        with pytest.raises(ValidationError):
            AnamnesisResult(questions=[], completeness_score=1.1)

    def test_completeness_score_below_0_raises(self):
        with pytest.raises(ValidationError):
            AnamnesisResult(questions=[], completeness_score=-0.1)

    def test_defaults_are_empty_lists(self):
        result = AnamnesisResult(questions=[], completeness_score=0.0)
        assert result.extracted_facts == []
        assert result.critical_gaps == []

    def test_zero_questions_is_valid(self):
        result = AnamnesisResult(questions=[], completeness_score=0.9)
        assert len(result.questions) == 0


# ========== AnamnesisAgent Node Tests ==========

class TestAnamnesisAgentNode:
    def _make_state(self, **overrides) -> dict:
        base = {
            "case_id": "test-001",
            "user_id": "user-001",
            "messages": [],
            "current_message": "Me duele mucho la cabeza desde ayer",
            "triage_level": "yellow",
            "triage_confidence": 0.8,
            "red_flags": [],
            "extracted_facts": [],
            "pending_questions": [],
            "completeness_score": 0.0,
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
            "current_node": "triage",
            "force_close": False,
            "created_at": "2026-04-09T00:00:00",
            "updated_at": "2026-04-09T00:00:00",
        }
        base.update(overrides)
        return base

    def _make_mock_result(self) -> AnamnesisResult:
        return AnamnesisResult(
            questions=[
                ClinicalQuestion(
                    question="¿Puede describir el tipo de dolor? (pulsátil, opresivo, punzante)",
                    area="motivo_consulta",
                    priority="alta",
                    rationale="El carácter del dolor orienta el diagnóstico diferencial",
                ),
                ClinicalQuestion(
                    question="¿El dolor se irradia a alguna otra parte?",
                    area="motivo_consulta",
                    priority="alta",
                    rationale="La irradiación descarta o confirma causas secundarias",
                ),
                ClinicalQuestion(
                    question="¿Está tomando alguna medicación actualmente?",
                    area="antecedentes",
                    priority="media",
                    rationale="La medicación puede ser causa o modulador del síntoma",
                ),
            ],
            extracted_facts=[
                ClinicalFact(fact_type="symptom", value="cefalea desde ayer", confidence=0.95),
            ],
            completeness_score=0.2,
            critical_gaps=["Duración exacta", "Carácter del dolor", "Medicación actual"],
        )

    @pytest.mark.asyncio
    async def test_agent_returns_correct_keys(self):
        from app.agents.anamnesis.agent import AnamnesisAgent

        with patch("app.agents.anamnesis.agent.ChatOpenAI") as mock_openai:
            mock_llm = MagicMock()
            mock_llm.ainvoke = AsyncMock(return_value=self._make_mock_result())
            mock_openai.return_value.with_structured_output.return_value = mock_llm

            agent = AnamnesisAgent(api_key="sk-test")
            state = self._make_state()
            result = await agent(state)

        assert "extracted_facts" in result
        assert "pending_questions" in result
        assert "completeness_score" in result
        assert "current_node" in result
        assert result["current_node"] == "anamnesis"

    @pytest.mark.asyncio
    async def test_agent_merges_new_facts_with_existing(self):
        from app.agents.anamnesis.agent import AnamnesisAgent

        existing = [{"fact_type": "symptom", "value": "náuseas", "confidence": 0.8}]

        with patch("app.agents.anamnesis.agent.ChatOpenAI") as mock_openai:
            mock_llm = MagicMock()
            mock_llm.ainvoke = AsyncMock(return_value=self._make_mock_result())
            mock_openai.return_value.with_structured_output.return_value = mock_llm

            agent = AnamnesisAgent(api_key="sk-test")
            state = self._make_state(extracted_facts=existing)
            result = await agent(state)

        # Existing fact preserved
        values = [f["value"].lower() for f in result["extracted_facts"]]
        assert "náuseas" in values
        # New fact added
        assert any("cefalea" in v for v in values)

    @pytest.mark.asyncio
    async def test_agent_does_not_duplicate_existing_facts(self):
        from app.agents.anamnesis.agent import AnamnesisAgent

        # Same fact already exists
        existing = [{"fact_type": "symptom", "value": "cefalea desde ayer", "confidence": 0.95}]

        with patch("app.agents.anamnesis.agent.ChatOpenAI") as mock_openai:
            mock_llm = MagicMock()
            mock_llm.ainvoke = AsyncMock(return_value=self._make_mock_result())
            mock_openai.return_value.with_structured_output.return_value = mock_llm

            agent = AnamnesisAgent(api_key="sk-test")
            state = self._make_state(extracted_facts=existing)
            result = await agent(state)

        # Should not have duplicated the same fact
        values = [f["value"].lower() for f in result["extracted_facts"]]
        assert values.count("cefalea desde ayer") == 1

    @pytest.mark.asyncio
    async def test_agent_appends_new_pending_questions(self):
        from app.agents.anamnesis.agent import AnamnesisAgent

        prior_questions = ["¿Tiene fiebre?"]

        with patch("app.agents.anamnesis.agent.ChatOpenAI") as mock_openai:
            mock_llm = MagicMock()
            mock_llm.ainvoke = AsyncMock(return_value=self._make_mock_result())
            mock_openai.return_value.with_structured_output.return_value = mock_llm

            agent = AnamnesisAgent(api_key="sk-test")
            state = self._make_state(pending_questions=prior_questions)
            result = await agent(state)

        # Prior question preserved
        assert "¿Tiene fiebre?" in result["pending_questions"]
        # New questions added
        assert len(result["pending_questions"]) > 1

    @pytest.mark.asyncio
    async def test_completeness_score_is_float_in_range(self):
        from app.agents.anamnesis.agent import AnamnesisAgent

        with patch("app.agents.anamnesis.agent.ChatOpenAI") as mock_openai:
            mock_llm = MagicMock()
            mock_llm.ainvoke = AsyncMock(return_value=self._make_mock_result())
            mock_openai.return_value.with_structured_output.return_value = mock_llm

            agent = AnamnesisAgent(api_key="sk-test")
            state = self._make_state()
            result = await agent(state)

        score = result["completeness_score"]
        assert isinstance(score, float)
        assert 0.0 <= score <= 1.0
