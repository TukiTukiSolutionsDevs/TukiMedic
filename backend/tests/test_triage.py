"""Tests for the Triage Agent — tools, router, and agent node."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from app.agents.triage.tools import red_flag_checker, symptom_scorer, age_risk_evaluator
from app.agents.triage.agent import triage_router
from app.agents.triage.schemas import TriageResult


# ========== Red Flag Checker Tests ==========

class TestRedFlagChecker:
    def test_detects_cardiovascular_red_flag(self):
        matches = red_flag_checker("tengo dolor torácico agudo y no puedo respirar")
        assert len(matches) > 0
        categories = [m.category for m in matches]
        assert "cardiovascular" in categories

    def test_detects_neurological_red_flag(self):
        matches = red_flag_checker("no puedo mover un lado del cuerpo")
        assert len(matches) > 0
        categories = [m.category for m in matches]
        assert "neurologico" in categories

    def test_detects_psychiatric_red_flag(self):
        matches = red_flag_checker("quiero matarme, no aguanto más")
        assert len(matches) > 0
        categories = [m.category for m in matches]
        assert "psiquiatrico" in categories

    def test_no_red_flags_for_mild_symptoms(self):
        matches = red_flag_checker("me duele un poco la garganta")
        assert len(matches) == 0

    def test_detects_obstetric_red_flag(self):
        matches = red_flag_checker("tengo sangrado en embarazo")
        assert len(matches) > 0
        categories = [m.category for m in matches]
        assert "obstetrico" in categories

    def test_case_insensitive(self):
        matches = red_flag_checker("DOLOR TORÁCICO AGUDO")
        assert len(matches) > 0

    # ---- Fix A.3 — robust matching: negations and accent normalization ----

    def test_red_flag_negation_not_matched(self):
        """A negated symptom must NOT trigger a red flag."""
        matches = red_flag_checker("no tengo dolor en el pecho")
        cardio = [m for m in matches if m.category == "cardiovascular"]
        assert cardio == []

    def test_red_flag_negation_sin_not_matched(self):
        """The negator 'sin' must also block the match."""
        matches = red_flag_checker("vengo sin dolor en el pecho ni nada")
        cardio = [m for m in matches if m.category == "cardiovascular"]
        assert cardio == []

    def test_red_flag_with_accent_normalized(self):
        """Accent-stripped match still triggers — matches against bare ASCII."""
        # Trigger in YAML is "dolor torácico agudo"; user message lacks accent.
        matches = red_flag_checker("tengo dolor toracico agudo desde anoche")
        assert any(m.category == "cardiovascular" for m in matches)

    def test_red_flag_with_irradiation_matches(self):
        """Positive case: chest pain with arm radiation must match."""
        matches = red_flag_checker(
            "tengo dolor en el pecho que se irradia al brazo izquierdo"
        )
        assert any(m.category == "cardiovascular" for m in matches)

    def test_red_flag_word_boundary_avoids_substring_false_positive(self):
        """Substring inside a longer word must not trigger (e.g. 'pecho' inside 'despechos')."""
        # Using a synthetic example that would match naively but should not via word-boundaries.
        matches = red_flag_checker("nada de despechospasados que me molesten")
        cardio = [m for m in matches if m.category == "cardiovascular"]
        assert cardio == []


# ========== Symptom Scorer Tests ==========

class TestSymptomScorer:
    def test_no_symptoms_returns_zero(self):
        assert symptom_scorer([]) == 0.0

    def test_severe_keyword_scores_high(self):
        score = symptom_scorer(["dolor severo de cabeza"])
        assert score >= 0.8

    def test_mild_keyword_scores_low(self):
        score = symptom_scorer(["molestia leve en el brazo"])
        assert score <= 0.3

    def test_multiple_symptoms_takes_max(self):
        score = symptom_scorer(["dolor leve", "dolor insoportable"])
        assert score >= 0.9


# ========== Age Risk Evaluator Tests ==========

class TestAgeRiskEvaluator:
    def test_neonate_high_risk(self):
        assert age_risk_evaluator(0, []) == 1.5

    def test_elderly_high_risk(self):
        assert age_risk_evaluator(75, []) == 1.3

    def test_adult_normal_risk(self):
        assert age_risk_evaluator(35, []) == 1.0

    def test_none_age_returns_default(self):
        assert age_risk_evaluator(None, []) == 1.0


# ========== Triage Router Tests ==========

class TestTriageRouter:
    def _make_state(self, **overrides):
        base = {
            "case_id": "test",
            "user_id": "test",
            "messages": [],
            "current_message": "",
            "triage_level": "green",
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
            "created_at": "",
            "updated_at": "",
        }
        base.update(overrides)
        return base

    def test_red_with_flags_goes_to_escalation(self):
        state = self._make_state(triage_level="red", red_flags=["dolor torácico"])
        assert triage_router(state) == "escalation"

    def test_first_visit_low_completeness_goes_to_anamnesis(self):
        state = self._make_state(triage_level="green", loop_count=0, completeness_score=0.3)
        assert triage_router(state) == "anamnesis"

    def test_high_completeness_goes_to_classification(self):
        state = self._make_state(triage_level="yellow", loop_count=0, completeness_score=0.7)
        assert triage_router(state) == "classification"

    def test_subsequent_loop_goes_to_classification(self):
        state = self._make_state(triage_level="green", loop_count=1, completeness_score=0.3)
        assert triage_router(state) == "classification"
