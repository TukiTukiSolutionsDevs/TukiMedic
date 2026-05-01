"""
QW3 latency optimization — skip anamnesis on the first turn when the
patient already supplied a rich, clinically-loaded message.

ROI: -3-6s per case (one LLM round-trip eliminated) → drops P95 from ~175s.

Heuristic for "rich enough":
- Message length ≥ 200 chars
- ≥ 2 distinct clinical keywords from a curated set

Safety net:
- A red flag (deterministic or LLM) ALWAYS escalates first — richness
  cannot bypass an emergency.
- Subsequent loops (loop_count > 0) already skip anamnesis — unchanged.
- Short or non-clinical messages on turn 1 still go to anamnesis to
  collect more facts before classification.
"""
from __future__ import annotations

import pytest

from app.agents.triage.agent import triage_router


# ---------------------------------------------------------------------------
# Fixture builder
# ---------------------------------------------------------------------------


def _make_state(**overrides) -> dict:
    base = {
        "current_message": "",
        "case_id": "case-1",
        "user_id": "user-1",
        "messages": [],
        "extracted_facts": [],
        "triage_level": "green",
        "triage_confidence": 0.0,
        "red_flags": [],
        "anamnesis_questions": [],
        "completeness_score": 0.0,
        "active_specialties": [],
        "specialist_outputs": {},
        "medical_board": None,
        "devils_advocate": None,
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


# ---------------------------------------------------------------------------
# Sample messages
# ---------------------------------------------------------------------------

# Rich: > 200 chars, ≥ 2 clinical keywords ("dolor", "presión", "fiebre").
_RICH_MESSAGE = (
    "Tengo desde anoche un dolor opresivo en el pecho que se irradia al "
    "brazo izquierdo. La presión arterial me la tomé hace un rato y "
    "estaba en 150/95. También tuve algo de fiebre baja durante el día "
    "y estoy con bastante dificultad para respirar al subir escaleras. "
    "Soy hipertenso y diabético desde hace 8 años, tomo metformina y enalapril."
)

# Long but devoid of clinical keywords — should still go to anamnesis.
_LONG_NON_CLINICAL = (
    "Hola, perdón por la consulta extensa pero quería darles contexto. "
    "Vivo en una ciudad chica, trabajo como contador desde hace varios "
    "años y suelo viajar al menos una vez por semana en colectivo. "
    "Practico mucho deporte de fin de semana y como bastante sano por "
    "lo general, aunque a veces me salto comidas si estoy ocupado. "
    "Me gustaría saber qué piensan en general sobre mi situación."
)

# Short but clinical — should still trigger anamnesis (not enough info).
_SHORT_CLINICAL = "Tengo dolor y fiebre."

assert len(_RICH_MESSAGE) >= 200
assert len(_LONG_NON_CLINICAL) >= 200
assert len(_SHORT_CLINICAL) < 200


# ---------------------------------------------------------------------------
# Routing tests
# ---------------------------------------------------------------------------


def test_rich_first_turn_skips_anamnesis():
    """Rich first-turn message bypasses anamnesis → classification."""
    state = _make_state(
        triage_level="green",
        loop_count=0,
        completeness_score=0.3,
        current_message=_RICH_MESSAGE,
    )
    assert triage_router(state) == "classification"


def test_long_non_clinical_still_goes_to_anamnesis():
    """Length alone is not enough; clinical keywords gate the skip."""
    state = _make_state(
        triage_level="green",
        loop_count=0,
        completeness_score=0.3,
        current_message=_LONG_NON_CLINICAL,
    )
    assert triage_router(state) == "anamnesis"


def test_short_clinical_first_turn_still_goes_to_anamnesis():
    """Clinical keywords alone are not enough; min length gates the skip."""
    state = _make_state(
        triage_level="green",
        loop_count=0,
        completeness_score=0.3,
        current_message=_SHORT_CLINICAL,
    )
    assert triage_router(state) == "anamnesis"


def test_rich_message_with_red_flag_still_escalates():
    """Emergency path is unaffected by richness — escalation wins."""
    state = _make_state(
        triage_level="red",
        red_flags=["dolor torácico opresivo"],
        loop_count=0,
        completeness_score=0.3,
        current_message=_RICH_MESSAGE,
    )
    assert triage_router(state) == "escalation"


def test_rich_message_high_completeness_unchanged():
    """High completeness already routes to classification — stays the same."""
    state = _make_state(
        triage_level="yellow",
        loop_count=0,
        completeness_score=0.8,
        current_message=_RICH_MESSAGE,
    )
    assert triage_router(state) == "classification"


def test_subsequent_loop_unchanged_with_short_message():
    """loop_count > 0 already skips anamnesis — richness irrelevant."""
    state = _make_state(
        triage_level="green",
        loop_count=1,
        completeness_score=0.3,
        current_message=_SHORT_CLINICAL,
    )
    assert triage_router(state) == "classification"


def test_empty_message_routes_to_anamnesis():
    """Defensive: missing/empty message can never qualify as rich."""
    state = _make_state(
        triage_level="green",
        loop_count=0,
        completeness_score=0.3,
        current_message="",
    )
    assert triage_router(state) == "anamnesis"


def test_missing_current_message_routes_to_anamnesis():
    """Defensive: state without current_message key falls back to anamnesis."""
    state = _make_state(
        triage_level="green",
        loop_count=0,
        completeness_score=0.3,
    )
    state.pop("current_message", None)
    assert triage_router(state) == "anamnesis"


# ---------------------------------------------------------------------------
# Helper purity tests (white-box)
# ---------------------------------------------------------------------------


def test_is_rich_message_helper_truthy_on_rich():
    from app.agents.triage.agent import _is_rich_message

    assert _is_rich_message(_RICH_MESSAGE) is True


def test_is_rich_message_helper_falsy_on_long_non_clinical():
    from app.agents.triage.agent import _is_rich_message

    assert _is_rich_message(_LONG_NON_CLINICAL) is False


def test_is_rich_message_helper_falsy_on_short():
    from app.agents.triage.agent import _is_rich_message

    assert _is_rich_message(_SHORT_CLINICAL) is False


def test_is_rich_message_helper_falsy_on_none():
    from app.agents.triage.agent import _is_rich_message

    assert _is_rich_message(None) is False
    assert _is_rich_message("") is False
