"""
Tests for DermatologyAgent — TDD RED first.

Coverage:
1. Class metadata: specialty_name, prompt non-empty, prompt mentions
   derm core concepts (rashes, urticaria, dermatitis, ABCDE) and red flags
   (melanoma, anafilaxia, Stevens-Johnson, fascitis necrotizante).
2. Behavior: __call__ returns SpecialistAnalysis under "dermatologia" key in
   specialist_outputs and emits the right `current_node` string. Falls open
   under LLM failure.
3. Registry integration:
   - Registered under the canonical key "dermatologia".
   - get_specialist resolves "Dermatología", "dermatología", "derma" and
     "DERMATOLOGÍA" to a DermatologyAgent instance.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agents.specialists.schemas import SpecialistAnalysis


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_state(**overrides) -> dict:
    base = {
        "case_id": "test-derma-001",
        "user_id": "user-001",
        "messages": [],
        "current_message": (
            "Tengo un rash que apareció hace 3 días en el tronco, levemente "
            "pruriginoso, sin fiebre ni otros síntomas."
        ),
        "triage_level": "green",
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
    specialty_name: str = "dermatologia",
    *,
    confidence: float = 0.7,
    alarm_signs: list[str] | None = None,
    needs_referral: bool = False,
    differentials: list[dict] | None = None,
    clinical_impression: str | None = None,
) -> dict:
    return {
        "specialty_name": specialty_name,
        "clinical_impression": clinical_impression
        or (
            "Erupción maculopapular de evolución reciente, sin signos de "
            "alarma sistémicos en este momento."
        ),
        "differential_diagnosis": differentials
        or [
            {
                "condition": "Exantema viral inespecífico",
                "probability": "media",
                "supporting_evidence": ["rash reciente", "ausencia de fiebre"],
                "against_evidence": [],
            }
        ],
        "suggested_studies": ["Fotos de buena calidad", "Seguimiento clínico en 48–72h"],
        "risk_factors": [],
        "recommendations": [
            "Hidratación de piel, evitar irritantes",
            "Reconsultar si aparece fiebre o compromiso de mucosas",
        ],
        "alarm_signs": alarm_signs if alarm_signs is not None else [],
        "confidence": confidence,
        "needs_referral": needs_referral,
        "referral_to": ["Dermatología ambulatoria"] if needs_referral else [],
    }


def _make_agent_no_llm(agent_class):
    """Bypass __init__ so tests don't need API keys / network."""
    agent = object.__new__(agent_class)
    agent.llm = MagicMock()
    return agent


# ---------------------------------------------------------------------------
# Class metadata
# ---------------------------------------------------------------------------

class TestDermatologyAgentMetadata:
    def test_specialty_name_is_canonical_snake_case(self):
        from app.agents.specialists.dermatology import DermatologyAgent
        assert DermatologyAgent.specialty_name == "dermatologia"

    def test_system_prompt_non_empty(self):
        from app.agents.specialists.dermatology import DermatologyAgent
        agent = _make_agent_no_llm(DermatologyAgent)
        assert len(agent.system_prompt) > 200

    def test_system_prompt_mentions_core_dermatology_concepts(self):
        from app.agents.specialists.dermatology import DermatologyAgent
        agent = _make_agent_no_llm(DermatologyAgent)
        prompt_lower = agent.system_prompt.lower()
        # Core derm semiology + the three families the user enumerated.
        assert "rash" in prompt_lower or "exantema" in prompt_lower
        assert "urticaria" in prompt_lower
        assert "dermatitis" in prompt_lower
        assert "atópica" in prompt_lower or "atopica" in prompt_lower

    def test_system_prompt_mentions_red_flags(self):
        """Prompt MUST surface the dermatologic red flags so the agent escalates."""
        from app.agents.specialists.dermatology import DermatologyAgent
        agent = _make_agent_no_llm(DermatologyAgent)
        prompt_lower = agent.system_prompt.lower()
        # Melanoma + ABCDE rule.
        assert "melanoma" in prompt_lower
        assert "abcde" in prompt_lower
        # Other catastrophic emergencies the prompt must cover.
        assert "stevens" in prompt_lower  # Stevens-Johnson
        assert "fascitis" in prompt_lower  # Fascitis necrotizante
        assert "anafilaxia" in prompt_lower or "adrenalina" in prompt_lower


# ---------------------------------------------------------------------------
# Registry integration
# ---------------------------------------------------------------------------

class TestDermatologyRegistryWiring:
    def test_dermatology_agent_registered(self):
        """The agent must be discoverable via the canonical registry key."""
        # Importing the package triggers @register on import.
        from app.agents import specialists  # noqa: F401
        from app.agents.specialists.registry import REGISTRY
        from app.agents.specialists.dermatology import DermatologyAgent

        assert "dermatologia" in REGISTRY
        assert REGISTRY["dermatologia"] is DermatologyAgent

    def test_dermatology_normalizes_aliases(self):
        """Accented / capitalized / shorthand variants must resolve to the canonical key.

        Variants required by spec:
          - "Dermatología"  (classifier-style, accented + capitalized)
          - "dermatología"  (accented lowercase)
          - "DERMATOLOGÍA"  (all caps + accent)
          - "derma"         (shorthand, must hit ALIASES)
        """
        from app.agents import specialists  # noqa: F401 — populates ALIASES
        from app.agents.specialists.registry import (
            ALIASES,
            REGISTRY,
            _normalize_specialty,
        )

        # Direct normalization for the accented variants.
        assert _normalize_specialty("Dermatología") == "dermatologia"
        assert _normalize_specialty("dermatología") == "dermatologia"
        assert _normalize_specialty("DERMATOLOGÍA") == "dermatologia"
        assert _normalize_specialty(" dermatología ") == "dermatologia"

        # Shorthand needs an explicit alias entry → canonical key.
        assert _normalize_specialty("derma") == "derma"
        assert ALIASES.get("derma") == "dermatologia"
        assert ALIASES["derma"] in REGISTRY

    def test_get_specialist_returns_dermatology_instance(self):
        """get_specialist must build a DermatologyAgent for accented + alias names."""
        from app.agents.specialists.dermatology import DermatologyAgent
        from app.agents.specialists.registry import get_specialist

        with patch("app.agents.specialists.base.ChatOpenAI") as mock_chat:
            mock_chat.return_value.with_structured_output.return_value = MagicMock()

            for name in ("Dermatología", "dermatología", "derma", "DERMATOLOGÍA"):
                instance = get_specialist(name, api_key="x")
                assert isinstance(instance, DermatologyAgent), (
                    f"get_specialist({name!r}) did not resolve to DermatologyAgent"
                )


# ---------------------------------------------------------------------------
# Behavior — __call__
# ---------------------------------------------------------------------------

class TestDermatologyAgentBehavior:
    @pytest.mark.asyncio
    async def test_dermatology_analyze_returns_specialist_analysis(self):
        """Mock LLM → __call__ returns a well-shaped SpecialistAnalysis dump."""
        from app.agents.specialists.dermatology import DermatologyAgent

        agent = _make_agent_no_llm(DermatologyAgent)
        mock_result = SpecialistAnalysis(**_make_analysis("dermatologia"))
        agent.llm = AsyncMock()
        agent.llm.ainvoke = AsyncMock(return_value=mock_result)

        result = await agent(_make_state())

        assert "specialist_outputs" in result
        assert "current_node" in result
        assert "dermatologia" in result["specialist_outputs"]
        assert result["current_node"] == "specialist_dermatologia"

        out = result["specialist_outputs"]["dermatologia"]
        # Required SpecialistAnalysis fields.
        for field in (
            "specialty_name",
            "clinical_impression",
            "differential_diagnosis",
            "alarm_signs",
            "confidence",
            "needs_referral",
        ):
            assert field in out, f"missing {field} in specialist output"
        assert out["specialty_name"] == "dermatologia"
        assert isinstance(out["differential_diagnosis"], list)
        assert isinstance(out["alarm_signs"], list)
        assert isinstance(out["confidence"], float)

    @pytest.mark.asyncio
    async def test_dermatology_does_not_overwrite_other_specialists(self):
        """Merging into specialist_outputs must preserve sibling agents' results."""
        from app.agents.specialists.dermatology import DermatologyAgent

        agent = _make_agent_no_llm(DermatologyAgent)
        mock_result = SpecialistAnalysis(**_make_analysis("dermatologia"))
        agent.llm = AsyncMock()
        agent.llm.ainvoke = AsyncMock(return_value=mock_result)

        existing = {"medicina_general": {"clinical_impression": "general view"}}
        result = await agent(_make_state(specialist_outputs=existing))

        outputs = result["specialist_outputs"]
        assert "medicina_general" in outputs
        assert "dermatologia" in outputs

    @pytest.mark.asyncio
    async def test_dermatology_call_uses_safe_ainvoke_fail_open_on_llm_failure(self):
        """If the LLM raises, the agent must still return a usable fallback dict."""
        from app.agents.specialists.dermatology import DermatologyAgent

        agent = _make_agent_no_llm(DermatologyAgent)
        agent.llm = AsyncMock()
        agent.llm.ainvoke = AsyncMock(side_effect=RuntimeError("upstream gone"))

        result = await agent(_make_state())

        assert "specialist_outputs" in result
        out = result["specialist_outputs"]["dermatologia"]
        assert out["specialty_name"] == "dermatologia"
        assert out["confidence"] == 0.0
        assert out["needs_referral"] is True

    @pytest.mark.asyncio
    async def test_dermatology_detects_melanoma_red_flag(self):
        """ABCDE-style description must surface a melanoma alarm sign."""
        from app.agents.specialists.dermatology import DermatologyAgent

        agent = _make_agent_no_llm(DermatologyAgent)
        mock_result = SpecialistAnalysis(
            **_make_analysis(
                "dermatologia",
                confidence=0.8,
                needs_referral=True,
                clinical_impression=(
                    "Lesión pigmentada con criterios ABCDE positivos: asimétrica, "
                    "bordes irregulares, color heterogéneo, > 8 mm, evolución reciente. "
                    "Alta sospecha de melanoma."
                ),
                differentials=[
                    {
                        "condition": "Melanoma cutáneo (sospecha)",
                        "probability": "alta",
                        "supporting_evidence": [
                            "asimetría", "bordes irregulares", "color heterogéneo",
                            "diámetro > 6 mm", "evolución reciente",
                        ],
                        "against_evidence": [],
                    }
                ],
                alarm_signs=[
                    "Criterios ABCDE positivos — sospecha de melanoma",
                    "Cambio reciente en lesión pigmentada",
                ],
            )
        )
        agent.llm = AsyncMock()
        agent.llm.ainvoke = AsyncMock(return_value=mock_result)

        state = _make_state(
            current_message=(
                "Tengo un lunar en la espalda que cambió de tamaño y color en los "
                "últimos meses. Mide más de 8 mm, los bordes son irregulares y "
                "tiene zonas marrones y negras."
            ),
        )
        result = await agent(state)

        out = result["specialist_outputs"]["dermatologia"]
        joined_alarms = " ".join(out["alarm_signs"]).lower()
        assert "melanoma" in joined_alarms or "abcde" in joined_alarms
        assert out["needs_referral"] is True

    @pytest.mark.asyncio
    async def test_dermatology_detects_anaphylaxis_red_flag(self):
        """Rash + airway edema → anaphylaxis alarm sign + referral."""
        from app.agents.specialists.dermatology import DermatologyAgent

        agent = _make_agent_no_llm(DermatologyAgent)
        mock_result = SpecialistAnalysis(
            **_make_analysis(
                "dermatologia",
                confidence=0.9,
                needs_referral=True,
                clinical_impression=(
                    "Urticaria generalizada con edema labial / lingual y disnea. "
                    "Cuadro compatible con anafilaxia — emergencia."
                ),
                differentials=[
                    {
                        "condition": "Anafilaxia (urticaria + compromiso de vía aérea)",
                        "probability": "alta",
                        "supporting_evidence": [
                            "habones generalizados",
                            "edema labial y lingual",
                            "disnea",
                        ],
                        "against_evidence": [],
                    },
                    {
                        "condition": "Urticaria aguda aislada",
                        "probability": "baja",
                        "supporting_evidence": [],
                        "against_evidence": ["edema vía aérea", "disnea"],
                    },
                ],
                alarm_signs=[
                    "Anafilaxia con compromiso de vía aérea — adrenalina IM y guardia INMEDIATA",
                    "Edema labial y lingual",
                ],
            )
        )
        agent.llm = AsyncMock()
        agent.llm.ainvoke = AsyncMock(return_value=mock_result)

        state = _make_state(
            current_message=(
                "Me salieron habones por todo el cuerpo después de comer mariscos y "
                "ahora tengo los labios y la lengua hinchados, me cuesta respirar."
            ),
            triage_level="red",
            red_flags=["edema vía aérea", "disnea"],
        )
        result = await agent(state)

        out = result["specialist_outputs"]["dermatologia"]
        joined_alarms = " ".join(out["alarm_signs"]).lower()
        assert "anafilaxia" in joined_alarms or "vía aérea" in joined_alarms or "via aerea" in joined_alarms
        assert out["needs_referral"] is True

    @pytest.mark.asyncio
    async def test_dermatology_handles_benign_rash(self):
        """Benign-looking rash → moderate confidence, no alarm signs, no referral."""
        from app.agents.specialists.dermatology import DermatologyAgent

        agent = _make_agent_no_llm(DermatologyAgent)
        mock_result = SpecialistAnalysis(
            **_make_analysis(
                "dermatologia",
                confidence=0.65,
                needs_referral=False,
                alarm_signs=[],
                clinical_impression=(
                    "Erupción maculopapular leve, sin compromiso mucoso ni "
                    "signos sistémicos. Cuadro clínicamente benigno."
                ),
            )
        )
        agent.llm = AsyncMock()
        agent.llm.ainvoke = AsyncMock(return_value=mock_result)

        result = await agent(_make_state())

        out = result["specialist_outputs"]["dermatologia"]
        # Moderate confidence — clearly above zero (not the fallback) but not
        # high-certainty either.
        assert 0.3 <= out["confidence"] <= 0.85
        assert out["alarm_signs"] == []
        assert out["needs_referral"] is False
