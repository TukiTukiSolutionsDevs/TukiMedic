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


class TestPromptHandlesChronicityCorrectly:
    """Chronicity by itself MUST NOT escalate to YELLOW.

    Regression target: green-003 (sueño irregular crónico sin red flags),
    which the previous few-shot version mis-classified to YELLOW because the
    YELLOW pediátrico example used 'fiebre persistente' as anchor — the LLM
    generalized 'persistente / crónico' as a yellow signal.

    Fix: the prompt MUST contain (a) an explicit rule that chronicity alone
    does NOT escalate, and (b) at least one GREEN example of benign
    chronicity to balance the YELLOW anchor.
    """

    def test_chronicity_rule_present(self):
        # The prompt must explicitly state that chronicity by itself is not a
        # yellow trigger; signs of alarm or symptom combinations are.
        prompt_lower = TRIAGE_SYSTEM_PROMPT.lower()
        assert "cronicidad" in prompt_lower or "crónic" in prompt_lower, (
            "Prompt MUST mention cronicidad/cronicas to anchor the rule"
        )
        # Look for a directive phrase like "NO escala automáticamente" /
        # "no escala" / "no es un red flag" near the chronicity term.
        assert any(
            phrase in prompt_lower
            for phrase in (
                "no escala automáticamente",
                "no escala automaticamente",
                "no es un red flag",
                "no escala la categoría",
                "no escala la categoria",
            )
        ), "Prompt MUST state explicitly that chronicity alone does NOT escalate"

    def test_has_green_chronicity_example(self):
        # A GREEN example covering benign chronicity (sleep hygiene,
        # chronic stable mild symptom) must exist.
        prompt_lower = TRIAGE_SYSTEM_PROMPT.lower()
        # Must mention at least one chronic-benign trigger keyword.
        chronicity_green_signals = (
            "sueño irregular",
            "higiene del sueño",
            "patrón crónico estable",
            "patron cronico estable",
            "cronicidad benigna",
            "hábitos del sueño",
            "habitos del sueno",
        )
        assert any(s in prompt_lower for s in chronicity_green_signals), (
            "Prompt MUST include a GREEN example covering benign chronicity"
        )

    def test_yellow_pediatric_example_uses_combination_not_just_persistence(self):
        # The YELLOW pediatric example must clarify it is the COMBINATION of
        # signs that triggers yellow (fever + decay + feeding refusal),
        # not chronicity / persistence alone.
        prompt_lower = TRIAGE_SYSTEM_PROMPT.lower()
        # Combination keywords near the YELLOW example.
        assert "rechazo" in prompt_lower or "no quiere comer" in prompt_lower, (
            "YELLOW pediatric example MUST include feeding-refusal as a co-symptom "
            "to make the combination explicit"
        )
        assert "combinación" in prompt_lower or "combinacion" in prompt_lower, (
            "Prompt MUST emphasize 'combinación' to anchor the rule that YELLOW "
            "requires multiple co-occurring signs, not single-axis persistence"
        )
