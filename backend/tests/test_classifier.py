"""Tests for the Classifier Agent — schemas, tools, and agent node."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from pydantic import ValidationError

from app.agents.classifier.schemas import SpecialtyScore, ClassificationResult
from app.agents.classifier.tools import get_base_specialties, format_specialty_hints


# ========== SpecialtyScore Schema Tests ==========

class TestSpecialtyScore:
    def test_valid_score(self):
        s = SpecialtyScore(name="cardiologia", weight=0.9, reason="Dolor torácico agudo")
        assert s.name == "cardiologia"
        assert s.weight == 0.9
        assert s.reason == "Dolor torácico agudo"

    def test_weight_boundary_zero(self):
        s = SpecialtyScore(name="medicina_general", weight=0.0, reason="Baseline")
        assert s.weight == 0.0

    def test_weight_boundary_one(self):
        s = SpecialtyScore(name="neurologia", weight=1.0, reason="Convulsión activa")
        assert s.weight == 1.0

    def test_weight_above_one_raises(self):
        with pytest.raises(ValidationError):
            SpecialtyScore(name="cardiologia", weight=1.1, reason="Test")

    def test_weight_below_zero_raises(self):
        with pytest.raises(ValidationError):
            SpecialtyScore(name="cardiologia", weight=-0.1, reason="Test")


# ========== ClassificationResult Schema Tests ==========

class TestClassificationResult:
    def _make_specialty(self, name: str, weight: float) -> SpecialtyScore:
        return SpecialtyScore(name=name, weight=weight, reason=f"Relevante para {name}")

    def test_valid_result(self):
        result = ClassificationResult(
            specialties=[
                self._make_specialty("cardiologia", 0.9),
                self._make_specialty("medicina_interna", 0.5),
            ],
            primary_specialty="cardiologia",
            reasoning="Dolor torácico con irradiación al brazo izquierdo",
            differential_considerations=["IAM", "angina inestable", "disección aórtica"],
        )
        assert len(result.specialties) == 2
        assert result.primary_specialty == "cardiologia"
        assert len(result.differential_considerations) == 3

    def test_differential_considerations_defaults_to_empty(self):
        result = ClassificationResult(
            specialties=[self._make_specialty("neurologia", 0.7)],
            primary_specialty="neurologia",
            reasoning="Cefalea intensa de inicio súbito",
        )
        assert result.differential_considerations == []

    def test_empty_specialties_is_valid(self):
        result = ClassificationResult(
            specialties=[],
            primary_specialty="medicina_general",
            reasoning="Síntomas inespecíficos",
        )
        assert result.specialties == []


# ========== specialty_map.yaml Tests ==========

class TestSpecialtyMapYaml:
    def test_yaml_loads_correctly(self):
        from app.agents.classifier.tools import _load_specialty_map
        specialty_map = _load_specialty_map()
        assert isinstance(specialty_map, dict)
        assert len(specialty_map) > 0

    def test_yaml_has_expected_symptom_keys(self):
        from app.agents.classifier.tools import _load_specialty_map
        specialty_map = _load_specialty_map()
        expected_keys = [
            "dolor_abdominal", "fatiga_cronica", "cefalea",
            "dolor_toracico", "problemas_piel", "dolor_articular",
        ]
        for key in expected_keys:
            assert key in specialty_map, f"Missing symptom key: {key}"

    def test_yaml_weights_are_floats_between_0_and_1(self):
        from app.agents.classifier.tools import _load_specialty_map
        specialty_map = _load_specialty_map()
        for symptom, specialties in specialty_map.items():
            for specialty, weight in specialties.items():
                assert 0.0 <= weight <= 1.0, (
                    f"{symptom}/{specialty} has invalid weight: {weight}"
                )

    def test_dolor_toracico_has_cardiologia_with_high_weight(self):
        from app.agents.classifier.tools import _load_specialty_map
        specialty_map = _load_specialty_map()
        assert "cardiologia" in specialty_map["dolor_toracico"]
        assert specialty_map["dolor_toracico"]["cardiologia"] >= 0.8


# ========== get_base_specialties Tests ==========

class TestGetBaseSpecialties:
    def test_known_symptom_returns_expected_specialties(self):
        result = get_base_specialties(["cefalea"])
        assert "neurologia" in result
        assert "medicina_general" in result

    def test_unknown_symptom_returns_empty(self):
        result = get_base_specialties(["dolor_de_codo_misterioso"])
        assert result == {}

    def test_empty_list_returns_empty(self):
        result = get_base_specialties([])
        assert result == {}

    def test_multiple_symptoms_merged_taking_max_weight(self):
        # Both cefalea and dolor_toracico have medicina_interna or similar
        # dolor_toracico → medicina_interna: 0.5; dolor_abdominal → medicina_interna: 0.6
        result = get_base_specialties(["dolor_abdominal", "dolor_toracico"])
        assert "cardiologia" in result      # from dolor_toracico
        assert "gastroenterologia" in result  # from dolor_abdominal
        # medicina_interna appears in both — should take max
        assert "medicina_interna" in result
        assert result["medicina_interna"] == max(0.6, 0.5)

    def test_dolor_toracico_cardiologia_weight(self):
        result = get_base_specialties(["dolor_toracico"])
        assert result["cardiologia"] == 0.9

    def test_returns_dict_of_str_float(self):
        result = get_base_specialties(["cefalea"])
        assert isinstance(result, dict)
        for k, v in result.items():
            assert isinstance(k, str)
            assert isinstance(v, float)


# ========== format_specialty_hints Tests ==========

class TestFormatSpecialtyHints:
    def test_returns_string(self):
        result = format_specialty_hints(["cefalea"])
        assert isinstance(result, str)

    def test_unknown_symptoms_returns_fallback_message(self):
        result = format_specialty_hints(["sintoma_inexistente"])
        assert "No se encontraron" in result

    def test_empty_returns_fallback_message(self):
        result = format_specialty_hints([])
        assert "No se encontraron" in result

    def test_valid_symptom_includes_specialty_name(self):
        result = format_specialty_hints(["dolor_toracico"])
        assert "cardiologia" in result


# ========== ClassifierAgent Node Tests ==========

class TestClassifierAgentNode:
    def _make_state(self, **overrides) -> dict:
        base = {
            "case_id": "test-001",
            "user_id": "user-001",
            "messages": [],
            "current_message": "Tengo un dolor en el pecho que se irradia al brazo izquierdo",
            "triage_level": "red",
            "triage_confidence": 0.95,
            "red_flags": ["dolor torácico con irradiación"],
            "extracted_facts": [
                {"fact_type": "symptom", "value": "dolor toracico", "confidence": 0.95},
                {"fact_type": "symptom", "value": "irradiacion al brazo izquierdo", "confidence": 0.9},
            ],
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
            "current_node": "anamnesis",
            "force_close": False,
            "created_at": "2026-04-09T00:00:00",
            "updated_at": "2026-04-09T00:00:00",
        }
        base.update(overrides)
        return base

    def _make_mock_result(self) -> ClassificationResult:
        return ClassificationResult(
            specialties=[
                SpecialtyScore(name="cardiologia", weight=0.9, reason="Dolor torácico con irradiación"),
                SpecialtyScore(name="medicina_interna", weight=0.5, reason="Evaluación sistémica"),
                SpecialtyScore(name="medicina_general", weight=0.35, reason="Baseline"),  # below threshold
            ],
            primary_specialty="cardiologia",
            reasoning="Dolor torácico irradiado al brazo izquierdo — alta sospecha cardiovascular",
            differential_considerations=["IAM", "angina inestable", "disección aórtica"],
        )

    @pytest.mark.asyncio
    async def test_agent_returns_correct_keys(self):
        from app.agents.classifier.agent import ClassifierAgent

        with patch("app.agents.classifier.agent.ChatOpenAI") as mock_openai:
            mock_llm = MagicMock()
            mock_llm.ainvoke = AsyncMock(return_value=self._make_mock_result())
            mock_openai.return_value.with_structured_output.return_value = mock_llm

            agent = ClassifierAgent(api_key="sk-test")
            result = await agent(self._make_state())

        assert "active_specialties" in result
        assert "primary_specialty" in result
        assert "current_node" in result
        assert result["current_node"] == "classifier"

    @pytest.mark.asyncio
    async def test_agent_filters_below_threshold(self):
        from app.agents.classifier.agent import ClassifierAgent

        with patch("app.agents.classifier.agent.ChatOpenAI") as mock_openai:
            mock_llm = MagicMock()
            mock_llm.ainvoke = AsyncMock(return_value=self._make_mock_result())
            mock_openai.return_value.with_structured_output.return_value = mock_llm

            agent = ClassifierAgent(api_key="sk-test")
            result = await agent(self._make_state())

        # medicina_general weight=0.35 is below threshold 0.4 — should be filtered out
        names = [s["name"] for s in result["active_specialties"]]
        assert "medicina_general" not in names
        assert "cardiologia" in names
        assert "medicina_interna" in names

    @pytest.mark.asyncio
    async def test_active_specialties_sorted_by_weight_desc(self):
        from app.agents.classifier.agent import ClassifierAgent

        with patch("app.agents.classifier.agent.ChatOpenAI") as mock_openai:
            mock_llm = MagicMock()
            mock_llm.ainvoke = AsyncMock(return_value=self._make_mock_result())
            mock_openai.return_value.with_structured_output.return_value = mock_llm

            agent = ClassifierAgent(api_key="sk-test")
            result = await agent(self._make_state())

        weights = [s["weight"] for s in result["active_specialties"]]
        assert weights == sorted(weights, reverse=True)

    @pytest.mark.asyncio
    async def test_primary_specialty_is_set(self):
        from app.agents.classifier.agent import ClassifierAgent

        with patch("app.agents.classifier.agent.ChatOpenAI") as mock_openai:
            mock_llm = MagicMock()
            mock_llm.ainvoke = AsyncMock(return_value=self._make_mock_result())
            mock_openai.return_value.with_structured_output.return_value = mock_llm

            agent = ClassifierAgent(api_key="sk-test")
            result = await agent(self._make_state())

        assert result["primary_specialty"] == "cardiologia"

    @pytest.mark.asyncio
    async def test_active_specialties_are_dicts_with_expected_keys(self):
        from app.agents.classifier.agent import ClassifierAgent

        with patch("app.agents.classifier.agent.ChatOpenAI") as mock_openai:
            mock_llm = MagicMock()
            mock_llm.ainvoke = AsyncMock(return_value=self._make_mock_result())
            mock_openai.return_value.with_structured_output.return_value = mock_llm

            agent = ClassifierAgent(api_key="sk-test")
            result = await agent(self._make_state())

        for specialty in result["active_specialties"]:
            assert "name" in specialty
            assert "weight" in specialty
            assert "reason" in specialty
            assert specialty["weight"] >= 0.4


# ========== classification_router Tests ==========

class TestClassificationRouter:
    def _make_state(self, **overrides) -> dict:
        base = {
            "active_specialties": [{"name": "cardiologia", "weight": 0.9, "reason": "test"}],
            "primary_specialty": "cardiologia",
            "current_node": "classifier",
        }
        base.update(overrides)
        return base

    def test_router_always_returns_specialists(self):
        from app.agents.classifier.agent import classification_router
        result = classification_router(self._make_state())
        assert result == "specialists"

    def test_router_returns_specialists_with_empty_specialties(self):
        from app.agents.classifier.agent import classification_router
        result = classification_router(self._make_state(active_specialties=[]))
        assert result == "specialists"

    def test_router_returns_string(self):
        from app.agents.classifier.agent import classification_router
        result = classification_router(self._make_state())
        assert isinstance(result, str)
