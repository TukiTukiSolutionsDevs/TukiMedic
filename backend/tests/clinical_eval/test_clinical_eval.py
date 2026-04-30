"""
Clinical Evaluation Suite — parametrized end-to-end tests.

Each test loads one YAML case, runs it through the full MedAgent graph
(real Gemini LLM), and asserts clinical-quality metrics.

Run:
    RUN_CLINICAL_EVAL=1 cd backend && poetry run pytest -m clinical_eval -v
    RUN_CLINICAL_EVAL=1 cd backend && poetry run pytest -m clinical_eval -k cardio-001 -v
"""
from __future__ import annotations

import time
import uuid
from pathlib import Path

import pytest
import yaml

# ---------------------------------------------------------------------------
# Disclaimer detection — check against both the hardcoded fallback and the
# LLM-generated disclaimer variants from the synthesizer prompt.
# ---------------------------------------------------------------------------
from app.agents.synthesizer.agent import BASE_DISCLAIMER

_DISCLAIMER_PHRASES = [
    BASE_DISCLAIMER.lower(),
    "no reemplaza la consulta médica",
    "consultá con un profesional de salud",
    "consultar con un profesional de salud",
    "orientación no reemplaza",
]


def _has_disclaimer(response: str) -> bool:
    r = response.lower()
    return any(phrase in r for phrase in _DISCLAIMER_PHRASES)


# ---------------------------------------------------------------------------
# Case loader
# ---------------------------------------------------------------------------

_CASES_DIR = Path(__file__).parent / "cases"


def _load_cases() -> list[dict]:
    cases = []
    for path in sorted(_CASES_DIR.glob("*.yaml")):
        with path.open(encoding="utf-8") as f:
            cases.append(yaml.safe_load(f))
    return cases


_ALL_CASES = _load_cases()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _red_flag_recall(state: dict, expected_flags: list[str]) -> float:
    """Fraction of expected red-flag terms found in detected flags OR response."""
    if not expected_flags:
        return 1.0
    detected_text = " ".join(state.get("red_flags", [])).lower()
    response_text = (state.get("synthesized_response") or "").lower()
    combined = detected_text + " " + response_text
    hits = sum(1 for ef in expected_flags if ef.lower() in combined)
    return hits / len(expected_flags)


def _build_result(case: dict, state: dict, latency: float, metrics: dict) -> dict:
    return {
        "id": case["id"],
        "title": case.get("title", ""),
        "category": case.get("category", "unknown"),
        "triage_level_expected": case["expected"]["triage_level"],
        "triage_level_actual": state.get("triage_level"),
        "triage_match": metrics["triage_match"],
        "red_flag_recall": metrics["red_flag_recall"],
        "expected_flag_count": len(case["expected"].get("must_contain_red_flags", [])),
        "escalation_match": metrics["escalation_match"],
        "attention_level_actual": state.get("attention_level"),
        "forbidden_diagnosis_avoided": metrics["forbidden_ok"],
        "disclaimer_present": metrics["disclaimer_ok"],
        "latency_seconds": round(latency, 2),
        "active_specialties": [
            s.get("name", s) if isinstance(s, dict) else s
            for s in state.get("active_specialties", [])
        ],
        "specialist_outputs_keys": list(state.get("specialist_outputs", {}).keys()),
        "red_flags_detected": state.get("red_flags", []),
        "current_node": state.get("current_node"),
    }


# ---------------------------------------------------------------------------
# Parametrized test — one test per YAML case
# ---------------------------------------------------------------------------


@pytest.mark.clinical_eval
@pytest.mark.parametrize("case", _ALL_CASES, ids=[c["id"] for c in _ALL_CASES])
async def test_clinical_case(
    case: dict,
    clinical_graph,
    eval_results: list[dict],
) -> None:
    """Run a single patient scenario through the full graph and assert metrics."""
    from app.orchestrator.graph import create_initial_state

    expected = case["expected"]
    patient = case.get("patient", {})

    # --- Build initial state ---
    state = create_initial_state(
        case_id=str(uuid.uuid4()),
        user_id=str(uuid.uuid4()),
        message=case["input_message"],
    )
    state["patient_profile"] = {
        "age": patient.get("age"),
        "biological_sex": patient.get("sex"),
        "chronic_conditions": patient.get("history", []),
    }

    # --- Run graph ---
    t0 = time.monotonic()
    final_state = await clinical_graph.ainvoke(state)
    latency = time.monotonic() - t0

    response = (final_state.get("synthesized_response") or "").lower()

    # --- Compute metrics ---
    triage_match = final_state.get("triage_level") == expected["triage_level"]

    expected_flags = expected.get("must_contain_red_flags", [])
    rf_recall = _red_flag_recall(final_state, expected_flags)

    actual_escalated = final_state.get("attention_level") == "urgencia"
    escalation_match = actual_escalated == expected["must_escalate"]

    must_not = [d.lower() for d in expected.get("must_not_diagnose", [])]
    forbidden_ok = all(d not in response for d in must_not)

    disclaimer_ok = _has_disclaimer(response)

    metrics = {
        "triage_match": triage_match,
        "red_flag_recall": rf_recall,
        "escalation_match": escalation_match,
        "forbidden_ok": forbidden_ok,
        "disclaimer_ok": disclaimer_ok,
    }

    # --- Collect result ---
    eval_results.append(_build_result(case, final_state, latency, metrics))

    # --- Assertions ---
    assert triage_match, (
        f"[{case['id']}] Triage mismatch: "
        f"got={final_state.get('triage_level')!r}, "
        f"expected={expected['triage_level']!r}"
    )

    if expected_flags:
        assert rf_recall == 1.0, (
            f"[{case['id']}] Red flag recall {rf_recall:.2f} < 1.0 — "
            f"expected terms {expected_flags!r} not fully detected in "
            f"flags={final_state.get('red_flags', [])!r}"
        )

    assert escalation_match, (
        f"[{case['id']}] Escalation mismatch: "
        f"attention_level={final_state.get('attention_level')!r}, "
        f"must_escalate={expected['must_escalate']}"
    )

    assert forbidden_ok, (
        f"[{case['id']}] Forbidden over-diagnosis term found in response: "
        f"{[d for d in must_not if d in response]}"
    )

    assert disclaimer_ok, (
        f"[{case['id']}] Disclaimer MISSING from response — "
        f"this is a clinical safety issue. "
        f"Response preview: {response[:300]!r}"
    )
