"""Tests for pediatric green-clamp via few-shot calibration in TRIAGE_SYSTEM_PROMPT.

Root cause of green-002 fail (eval s3 18:56Z, expected=green, actual=yellow):
LLM-bias defensivo pediátrico — the declarative prompt is correct, but the LLM
ignores "dudas sobre dosis → GREEN" when it sees "nena 4 años + fiebre 37.8"
and applies conservative pediatric bias despite the explicit rule
"No hay 'ante la duda más alto'".

Fix strategy (Option A, validated in `tuki-medic/green-002-investigation`):
add few-shot examples to TRIAGE_SYSTEM_PROMPT covering:
- GREEN admin pediátrico (dosing question with mild fever)
- GREEN preventivo / orientativo
- YELLOW pediátrico real (anti-overcorrection anchor)

These tests are STRUCTURAL — they validate the prompt contains the
calibration shape that the LLM needs to overcome the bias. End-to-end
behavior is validated via the clinical eval suite.
"""

import re

from app.agents.triage.prompts import TRIAGE_SYSTEM_PROMPT


class TestPromptHasFewShotSection:
    """The prompt MUST include an explicit few-shot calibration section."""

    def test_has_few_shot_or_examples_header(self):
        # Accept "EJEMPLOS", "FEW-SHOT", or "CALIBRACIÓN" as valid section markers.
        prompt_upper = TRIAGE_SYSTEM_PROMPT.upper()
        assert any(
            marker in prompt_upper
            for marker in ("EJEMPLOS", "FEW-SHOT", "CALIBRACIÓN", "CALIBRACION")
        ), "Prompt MUST contain a few-shot calibration section"

    def test_has_at_least_three_green_examples(self):
        # Count occurrences of "→ GREEN" or "-> GREEN" or similar example markers.
        pattern = re.compile(
            r"(?:→|->|=>|:)\s*GREEN\b", re.IGNORECASE
        )
        matches = pattern.findall(TRIAGE_SYSTEM_PROMPT)
        assert len(matches) >= 3, (
            f"Prompt MUST include ≥3 GREEN few-shot examples (found {len(matches)})"
        )

    def test_has_at_least_one_yellow_example(self):
        # Anti-overcorrection anchor: a pediatric YELLOW must exist so the
        # LLM does not flip everything pediatric to green.
        pattern = re.compile(
            r"(?:→|->|=>|:)\s*YELLOW\b", re.IGNORECASE
        )
        matches = pattern.findall(TRIAGE_SYSTEM_PROMPT)
        assert len(matches) >= 1, (
            f"Prompt MUST include ≥1 YELLOW few-shot example as anti-overcorrection anchor (found {len(matches)})"
        )


class TestPromptCoversGreen002Pattern:
    """The few-shot section MUST cover the green-002 pattern explicitly."""

    def test_covers_pediatric_dosing_question(self):
        # green-002 input: "mi nena tiene 4 años... ¿cuánto paracetamol le doy?"
        # Prompt must contain at least one example matching this shape:
        # pediatric population + dosing question + mild/no severe symptoms → GREEN.
        prompt_lower = TRIAGE_SYSTEM_PROMPT.lower()
        assert "dosis" in prompt_lower or "dosificación" in prompt_lower or "cuánto" in prompt_lower, (
            "Prompt few-shot section MUST mention a dosing question pattern"
        )
        # And must mention pediatric context in conjunction with green outcome.
        assert any(
            kw in prompt_lower
            for kw in ("pediátric", "nene", "nena", "niño", "niña", "lactante", "bebé")
        ), "Prompt MUST mention a pediatric context in few-shot examples"

    def test_pediatric_yellow_anchor_present(self):
        # A pediatric YELLOW example must exist so over-correction (flipping
        # all pediatric to green) is prevented.
        prompt_lower = TRIAGE_SYSTEM_PROMPT.lower()
        # Look for pediatric YELLOW signals: persistent fever, decay, dehydration, etc.
        assert (
            "fiebre" in prompt_lower
            and ("persistente" in prompt_lower or ">72h" in prompt_lower or "más de 72" in prompt_lower or "decaído" in prompt_lower or "decaida" in prompt_lower)
        ), "Prompt MUST include a pediatric YELLOW anchor (e.g. persistent fever, decay)"


class TestPromptInvariantsPreserved:
    """Existing rules must remain — few-shot must NOT loosen RED criteria."""

    def test_red_reservation_clause_preserved(self):
        # Original rule: RED reservada exclusivamente a la lista de red flags.
        assert "RESERVAD" in TRIAGE_SYSTEM_PROMPT.upper(), (
            "RED reservation clause MUST remain after adding few-shots"
        )

    def test_no_ante_la_duda_clause_preserved(self):
        # Original rule: "No hay 'ante la duda más alto'".
        assert "ante la duda" in TRIAGE_SYSTEM_PROMPT.lower(), (
            "Anti-conservative-bias clause MUST remain"
        )

    def test_red_flags_list_preserved(self):
        # The deterministic RED FLAGS list must remain.
        assert "RED FLAGS" in TRIAGE_SYSTEM_PROMPT, "RED FLAGS list MUST remain"
        # Sanity check on a couple of canonical entries.
        assert "torácico" in TRIAGE_SYSTEM_PROMPT or "toracico" in TRIAGE_SYSTEM_PROMPT
        assert "ideación suicida" in TRIAGE_SYSTEM_PROMPT.lower() or "ideacion suicida" in TRIAGE_SYSTEM_PROMPT.lower()
