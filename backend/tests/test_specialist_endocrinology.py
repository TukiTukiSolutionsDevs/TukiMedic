"""
Tests for EndocrinologyAgent — TDD RED first.

Coverage:
1. Class metadata: specialty_name, prompt non-empty, prompt mentions endo core.
2. Behavior: __call__ returns SpecialistAnalysis under "endocrinologia" key in
   specialist_outputs and emits the right current_node string.
3. Integration with the registry + dispatcher routing path:
   - Registered under the canonical key "endocrinologia".
   - The classifier-style accented variant "Endocrinología" resolves through
     `_normalize_specialty` to the same agent.
   - Short alias "endocrino" resolves via ALIASES to "endocrinologia".
   - get_specialist returns an instance type-correct with the agent class.
4. Red flag detection in clinical scenarios:
   - DKA (poliuria + Kussmaul + glucemia >250).
   - Crisis tirotóxica (taquicardia + hipertermia + delirium).
   - Crisis adrenal (Addison + stress + hipotensión).
5. Routine consult: HbA1c review in stable DBT → moderate confidence, no flags.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.agents.specialists.schemas import SpecialistAnalysis


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_state(**overrides) -> dict:
    base = {
        "case_id": "test-endo-001",
        "user_id": "user-001",
        "messages": [],
        "current_message": "Consulta sobre control de diabetes",
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
        "patient_profile": {},
        "kb_context": "",
        "created_at": "2026-05-01T00:00:00",
        "updated_at": "2026-05-01T00:00:00",
    }
    base.update(overrides)
    return base


def _make_analysis(
    specialty_name: str = "endocrinologia",
    *,
    clinical_impression: str | None = None,
    differential: list[dict] | None = None,
    alarm_signs: list[str] | None = None,
    confidence: float = 0.7,
    needs_referral: bool = False,
    referral_to: list[str] | None = None,
) -> dict:
    return {
        "specialty_name": specialty_name,
        "clinical_impression": clinical_impression
        or "Cuadro endocrinológico que requiere evaluación complementaria.",
        "differential_diagnosis": differential
        or [
            {
                "condition": "Diabetes mellitus tipo 2 en seguimiento",
                "probability": "media",
                "supporting_evidence": ["HbA1c 7.2%"],
                "against_evidence": [],
            }
        ],
        "suggested_studies": ["HbA1c", "Glucemia en ayunas", "Perfil lipídico"],
        "risk_factors": ["obesidad", "sedentarismo"],
        "recommendations": [
            "Continuar control endocrinológico ambulatorio"
        ],
        "alarm_signs": alarm_signs or [],
        "confidence": confidence,
        "needs_referral": needs_referral,
        "referral_to": referral_to or [],
    }


def _make_agent_no_llm(agent_class):
    """Bypass __init__ so tests don't need API keys / network."""
    agent = object.__new__(agent_class)
    agent.llm = MagicMock()
    return agent


# ---------------------------------------------------------------------------
# Class metadata
# ---------------------------------------------------------------------------

class TestEndocrinologyAgentMetadata:
    def test_specialty_name_is_canonical_snake_case(self):
        from app.agents.specialists.endocrinology import EndocrinologyAgent
        assert EndocrinologyAgent.specialty_name == "endocrinologia"

    def test_system_prompt_non_empty(self):
        from app.agents.specialists.endocrinology import EndocrinologyAgent
        agent = _make_agent_no_llm(EndocrinologyAgent)
        assert len(agent.system_prompt) > 200

    def test_system_prompt_mentions_core_endo_concepts(self):
        from app.agents.specialists.endocrinology import EndocrinologyAgent
        agent = _make_agent_no_llm(EndocrinologyAgent)
        prompt_lower = agent.system_prompt.lower()
        # Diabetes anchors
        assert "diabetes" in prompt_lower
        assert "hba1c" in prompt_lower
        # Acute decompensations
        assert "cetoacidosis" in prompt_lower or "dka" in prompt_lower
        assert "hipoglucemia" in prompt_lower
        # Thyroid
        assert "tsh" in prompt_lower
        assert any(t in prompt_lower for t in ("hipotiroidismo", "hipertiroidismo"))
        # Adrenal
        assert "addison" in prompt_lower or "adrenal" in prompt_lower

    def test_system_prompt_mentions_red_flags_and_emergencies(self):
        """The prompt MUST surface red flags so the agent escalates correctly."""
        from app.agents.specialists.endocrinology import EndocrinologyAgent
        agent = _make_agent_no_llm(EndocrinologyAgent)
        prompt_lower = agent.system_prompt.lower()
        assert "guardia" in prompt_lower or "emergencia" in prompt_lower
        assert "kussmaul" in prompt_lower
        assert "tirotóxica" in prompt_lower or "tirotoxica" in prompt_lower or "tormenta tiroidea" in prompt_lower
        assert "crisis adrenal" in prompt_lower


# ---------------------------------------------------------------------------
# Behavior — __call__
# ---------------------------------------------------------------------------

class TestEndocrinologyAgentBehavior:
    @pytest.mark.asyncio
    async def test_endocrinology_analyze_returns_specialist_analysis(self):
        from app.agents.specialists.endocrinology import EndocrinologyAgent

        agent = _make_agent_no_llm(EndocrinologyAgent)
        mock_result = SpecialistAnalysis(**_make_analysis("endocrinologia"))
        agent.llm = AsyncMock()
        agent.llm.ainvoke = AsyncMock(return_value=mock_result)

        result = await agent(_make_state())

        assert "specialist_outputs" in result
        assert "current_node" in result
        assert "endocrinologia" in result["specialist_outputs"]
        assert result["current_node"] == "specialist_endocrinologia"

    @pytest.mark.asyncio
    async def test_call_does_not_overwrite_other_specialists(self):
        from app.agents.specialists.endocrinology import EndocrinologyAgent

        agent = _make_agent_no_llm(EndocrinologyAgent)
        mock_result = SpecialistAnalysis(**_make_analysis("endocrinologia"))
        agent.llm = AsyncMock()
        agent.llm.ainvoke = AsyncMock(return_value=mock_result)

        existing = {
            "medicina_general": {"clinical_impression": "general view"},
        }
        result = await agent(_make_state(specialist_outputs=existing))

        outputs = result["specialist_outputs"]
        assert "medicina_general" in outputs
        assert "endocrinologia" in outputs

    @pytest.mark.asyncio
    async def test_call_uses_safe_ainvoke_fail_open_on_llm_failure(self):
        """If the LLM raises, the agent must still return a usable dict."""
        from app.agents.specialists.endocrinology import EndocrinologyAgent

        agent = _make_agent_no_llm(EndocrinologyAgent)
        agent.llm = AsyncMock()
        agent.llm.ainvoke = AsyncMock(side_effect=RuntimeError("upstream gone"))

        result = await agent(_make_state())

        assert "specialist_outputs" in result
        out = result["specialist_outputs"]["endocrinologia"]
        assert out["specialty_name"] == "endocrinologia"
        assert out["confidence"] == 0.0
        assert out["needs_referral"] is True


# ---------------------------------------------------------------------------
# Red-flag clinical scenarios — wiring tests (the LLM is mocked; we validate
# that the agent surfaces the red-flag analysis we hand it back, plus that
# the alarm_signs / needs_referral fields propagate cleanly through __call__).
# ---------------------------------------------------------------------------

class TestEndocrinologyRedFlags:
    @pytest.mark.asyncio
    async def test_endocrinology_detects_dka_red_flag(self):
        """Poliuria + Kussmaul + glucemia >250 → DKA red flag."""
        from app.agents.specialists.endocrinology import EndocrinologyAgent

        agent = _make_agent_no_llm(EndocrinologyAgent)
        mock_result = SpecialistAnalysis(
            **_make_analysis(
                clinical_impression=(
                    "Cuadro compatible con cetoacidosis diabética: poliuria, "
                    "respiración de Kussmaul, glucemia 320 mg/dl, aliento cetónico."
                ),
                differential=[
                    {
                        "condition": "Cetoacidosis diabética (DKA)",
                        "probability": "alta",
                        "supporting_evidence": [
                            "poliuria",
                            "respiración de Kussmaul",
                            "glucemia 320 mg/dl",
                            "aliento cetónico",
                        ],
                        "against_evidence": [],
                    }
                ],
                alarm_signs=[
                    "Cetoacidosis diabética: requiere derivación INMEDIATA a guardia"
                ],
                confidence=0.9,
                needs_referral=True,
                referral_to=["Guardia / emergencias"],
            )
        )
        agent.llm = AsyncMock()
        agent.llm.ainvoke = AsyncMock(return_value=mock_result)

        state = _make_state(
            current_message=(
                "Paciente con DBT1 con poliuria intensa hace 24h, respiración "
                "rápida y profunda, aliento dulzón, glucemia capilar 320 mg/dl."
            ),
            extracted_facts=[
                {"value": "poliuria 24h"},
                {"value": "respiración Kussmaul"},
                {"value": "glucemia 320 mg/dl"},
            ],
        )
        result = await agent(state)

        out = result["specialist_outputs"]["endocrinologia"]
        assert out["needs_referral"] is True
        assert any("cetoacidosis" in s.lower() or "dka" in s.lower() for s in out["alarm_signs"])
        assert any(
            "cetoacidosis" in d["condition"].lower() or "dka" in d["condition"].lower()
            for d in out["differential_diagnosis"]
        )

    @pytest.mark.asyncio
    async def test_endocrinology_detects_thyroid_storm_red_flag(self):
        """Taquicardia + hipertermia + delirium en hipertiroideo → crisis tirotóxica."""
        from app.agents.specialists.endocrinology import EndocrinologyAgent

        agent = _make_agent_no_llm(EndocrinologyAgent)
        mock_result = SpecialistAnalysis(
            **_make_analysis(
                clinical_impression=(
                    "Cuadro compatible con crisis tirotóxica (tormenta tiroidea) "
                    "en paciente con Graves conocida, tras infección urinaria."
                ),
                differential=[
                    {
                        "condition": "Crisis tirotóxica (tormenta tiroidea)",
                        "probability": "alta",
                        "supporting_evidence": [
                            "taquicardia 160 lpm",
                            "hipertermia 39.5°C",
                            "delirium",
                            "hipertiroidismo previo (Graves)",
                            "factor desencadenante: ITU",
                        ],
                        "against_evidence": [],
                    }
                ],
                alarm_signs=[
                    "Crisis tirotóxica: emergencia con mortalidad alta, "
                    "derivar a guardia inmediatamente"
                ],
                confidence=0.9,
                needs_referral=True,
                referral_to=["Guardia / UCI"],
            )
        )
        agent.llm = AsyncMock()
        agent.llm.ainvoke = AsyncMock(return_value=mock_result)

        state = _make_state(
            current_message=(
                "Mujer con Graves conocida, suspendió metimazol hace 1 semana, "
                "ahora con FC 160 lpm, T° 39.5°C, agitada y desorientada."
            ),
            extracted_facts=[
                {"value": "FC 160 lpm"},
                {"value": "T° 39.5°C"},
                {"value": "delirium / agitación"},
                {"value": "Graves conocida, suspendió metimazol"},
            ],
        )
        result = await agent(state)

        out = result["specialist_outputs"]["endocrinologia"]
        assert out["needs_referral"] is True
        assert any(
            "tirotóxica" in s.lower() or "tirotoxica" in s.lower() or "tormenta" in s.lower()
            for s in out["alarm_signs"]
        )

    @pytest.mark.asyncio
    async def test_endocrinology_detects_addisonian_crisis_red_flag(self):
        """Addison + stress + hipotensión → crisis adrenal."""
        from app.agents.specialists.endocrinology import EndocrinologyAgent

        agent = _make_agent_no_llm(EndocrinologyAgent)
        mock_result = SpecialistAnalysis(
            **_make_analysis(
                clinical_impression=(
                    "Cuadro compatible con crisis adrenal (insuficiencia adrenal "
                    "aguda) en paciente con Addison conocido, en contexto de "
                    "infección respiratoria."
                ),
                differential=[
                    {
                        "condition": "Crisis adrenal (insuficiencia adrenal aguda)",
                        "probability": "alta",
                        "supporting_evidence": [
                            "hipotensión 80/50 mmHg",
                            "náuseas y vómitos",
                            "dolor abdominal",
                            "fiebre",
                            "Addison conocido",
                            "stress (infección)",
                        ],
                        "against_evidence": [],
                    }
                ],
                alarm_signs=[
                    "Crisis adrenal: requiere hidrocortisona endovenosa "
                    "inmediata, derivar a guardia"
                ],
                confidence=0.9,
                needs_referral=True,
                referral_to=["Guardia / emergencias"],
            )
        )
        agent.llm = AsyncMock()
        agent.llm.ainvoke = AsyncMock(return_value=mock_result)

        state = _make_state(
            current_message=(
                "Paciente con enfermedad de Addison, en curso de bronquitis "
                "aguda, ahora con TA 80/50, náuseas, vómitos y dolor abdominal."
            ),
            extracted_facts=[
                {"value": "Addison conocido"},
                {"value": "TA 80/50 mmHg"},
                {"value": "náuseas / vómitos"},
                {"value": "stress: infección respiratoria"},
            ],
        )
        result = await agent(state)

        out = result["specialist_outputs"]["endocrinologia"]
        assert out["needs_referral"] is True
        assert any(
            "adrenal" in s.lower() or "addison" in s.lower()
            for s in out["alarm_signs"]
        )

    @pytest.mark.asyncio
    async def test_endocrinology_handles_routine_hba1c_consult(self):
        """Consulta sobre HbA1c en DBT estable → confidence moderado, sin red flags."""
        from app.agents.specialists.endocrinology import EndocrinologyAgent

        agent = _make_agent_no_llm(EndocrinologyAgent)
        mock_result = SpecialistAnalysis(
            **_make_analysis(
                clinical_impression=(
                    "DBT2 con buen control metabólico (HbA1c 6.8%), continuar "
                    "tratamiento actual y reforzar medidas higiénico-dietéticas."
                ),
                differential=[
                    {
                        "condition": "Diabetes mellitus tipo 2 controlada",
                        "probability": "alta",
                        "supporting_evidence": ["HbA1c 6.8%", "glucemias estables"],
                        "against_evidence": [],
                    }
                ],
                alarm_signs=[],
                confidence=0.65,
                needs_referral=False,
                referral_to=[],
            )
        )
        agent.llm = AsyncMock()
        agent.llm.ainvoke = AsyncMock(return_value=mock_result)

        state = _make_state(
            current_message=(
                "Tengo DBT2 hace 5 años, HbA1c 6.8%, vine a control rutinario."
            ),
            triage_level="green",
            extracted_facts=[
                {"value": "DBT2 5 años"},
                {"value": "HbA1c 6.8%"},
            ],
        )
        result = await agent(state)

        out = result["specialist_outputs"]["endocrinologia"]
        assert out["needs_referral"] is False
        assert out["alarm_signs"] == []
        assert 0.4 <= out["confidence"] <= 0.85


# ---------------------------------------------------------------------------
# Registry integration
# ---------------------------------------------------------------------------

class TestEndocrinologyRegistryWiring:
    def test_endocrinology_agent_registered(self):
        # Importing the package triggers @register on import.
        from app.agents import specialists  # noqa: F401
        from app.agents.specialists.registry import REGISTRY
        from app.agents.specialists.endocrinology import EndocrinologyAgent

        assert "endocrinologia" in REGISTRY
        assert REGISTRY["endocrinologia"] is EndocrinologyAgent

    def test_endocrinology_normalizes_aliases(self):
        """All variants must resolve to canonical 'endocrinologia'."""
        from app.agents import specialists  # noqa: F401  (load aliases)
        from app.agents.specialists.registry import (
            ALIASES,
            _normalize_specialty,
            get_specialist,
        )
        from unittest.mock import patch

        # Direct normalization via the normalizer (no alias needed).
        assert _normalize_specialty("Endocrinología") == "endocrinologia"
        assert _normalize_specialty("endocrinología") == "endocrinologia"
        assert _normalize_specialty("ENDOCRINOLOGÍA") == "endocrinologia"
        assert _normalize_specialty(" endocrinologia ") == "endocrinologia"

        # Short alias must be wired through ALIASES.
        assert ALIASES.get("endocrino") == "endocrinologia"

        # End-to-end: every variant must resolve through get_specialist.
        from app.agents.specialists.endocrinology import EndocrinologyAgent

        variants = [
            "Endocrinología",
            "endocrinologia",
            "endocrinología",
            "endocrino",
        ]
        with patch("app.agents.specialists.base.ChatOpenAI") as mock_chat:
            mock_chat.return_value.with_structured_output.return_value = MagicMock()
            for variant in variants:
                instance = get_specialist(variant, api_key="x")
                assert isinstance(instance, EndocrinologyAgent), (
                    f"variant {variant!r} did not resolve to EndocrinologyAgent"
                )

    def test_get_specialist_returns_endocrinology_instance(self):
        """get_specialist with an accented name must build an EndocrinologyAgent."""
        from unittest.mock import patch
        from app.agents.specialists.endocrinology import EndocrinologyAgent
        from app.agents.specialists.registry import get_specialist

        with patch("app.agents.specialists.base.ChatOpenAI") as mock_chat:
            mock_chat.return_value.with_structured_output.return_value = MagicMock()
            instance = get_specialist("Endocrinología", api_key="x")

        assert isinstance(instance, EndocrinologyAgent)
