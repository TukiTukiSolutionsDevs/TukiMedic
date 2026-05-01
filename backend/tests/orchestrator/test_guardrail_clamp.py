"""Unit tests for _clamp_interrupt — defensive demotion of guardrail
INTERRUPT decisions that lack critical-severity evidence.

The guardrail LLM was over-interrupting on benign clinical content
(green/yellow eval cases routed to escalation_node despite no real
emergency). Root cause: the prompt's interruption_level is not anchored
to severity, and specialist_outputs were being evaluated with a
patient-facing prompt that flags ordinary clinical language.

Rule:
    Interrupt the flow ONLY if:
      - interruption_level == INTERRUPT, AND
      - at least one violation has severity == "critical", AND
      - at least one violation has a clinically-dangerous violation_type:
        ignored_red_flag, prescription_with_dose, symptom_minimization,
        prompt_injection, definitive_diagnosis_unsafe.

Otherwise: do NOT interrupt (downgrade to OBSERVE/FLAG semantically —
the violation is still recorded for audit, but the flow continues).
"""

import pytest

from app.agents.guardrail.agent import _clamp_interrupt
from app.agents.guardrail.schemas import (
    GuardrailCheck,
    InterruptionLevel,
    SafetyViolation,
)


def _check(level: InterruptionLevel, violations: list[SafetyViolation]) -> GuardrailCheck:
    return GuardrailCheck(
        approved=level == InterruptionLevel.OBSERVE,
        violations=violations,
        interruption_level=level,
        modifications_suggested=[],
        escalation_required=False,
        escalation_reason="",
    )


class TestClampPreservesInterrupt:
    """Critical safety violations MUST keep INTERRUPT — never silence."""

    def test_critical_ignored_red_flag_keeps_interrupt(self):
        check = _check(
            InterruptionLevel.INTERRUPT,
            [SafetyViolation(
                violation_type="ignored_red_flag",
                description="Mensaje menciona dolor torácico irradiado y respuesta no escala",
                severity="critical",
            )],
        )
        assert _clamp_interrupt(check) is True

    def test_critical_prescription_with_dose_keeps_interrupt(self):
        check = _check(
            InterruptionLevel.INTERRUPT,
            [SafetyViolation(
                violation_type="prescription_with_dose",
                description="Indica ibuprofeno 600mg cada 6h",
                severity="critical",
            )],
        )
        assert _clamp_interrupt(check) is True

    def test_critical_symptom_minimization_keeps_interrupt(self):
        check = _check(
            InterruptionLevel.INTERRUPT,
            [SafetyViolation(
                violation_type="symptom_minimization",
                description="Minimiza disnea súbita como 'cosa sin importancia'",
                severity="critical",
            )],
        )
        assert _clamp_interrupt(check) is True

    def test_critical_prompt_injection_keeps_interrupt(self):
        check = _check(
            InterruptionLevel.INTERRUPT,
            [SafetyViolation(
                violation_type="prompt_injection",
                description="Mensaje intenta sobreescribir instrucciones del sistema",
                severity="critical",
            )],
        )
        assert _clamp_interrupt(check) is True


class TestClampDemotesInterrupt:
    """INTERRUPT without critical evidence MUST be demoted (continue flow)."""

    def test_interrupt_without_critical_severity_demoted(self):
        check = _check(
            InterruptionLevel.INTERRUPT,
            [SafetyViolation(
                violation_type="ignored_red_flag",
                description="Algo medio raro",
                severity="medium",
            )],
        )
        assert _clamp_interrupt(check) is False

    def test_interrupt_with_critical_but_non_dangerous_type_demoted(self):
        # critical severity but the type is benign (e.g. "missing_disclaimer")
        check = _check(
            InterruptionLevel.INTERRUPT,
            [SafetyViolation(
                violation_type="missing_disclaimer",
                description="Disclaimer faltante",
                severity="critical",
            )],
        )
        assert _clamp_interrupt(check) is False

    def test_interrupt_with_no_violations_demoted(self):
        check = _check(InterruptionLevel.INTERRUPT, [])
        assert _clamp_interrupt(check) is False


class TestClampPassthroughNonInterrupt:
    """Non-INTERRUPT levels are not affected by the clamp."""

    def test_observe_returns_false(self):
        check = _check(InterruptionLevel.OBSERVE, [])
        assert _clamp_interrupt(check) is False

    def test_flag_returns_false(self):
        check = _check(
            InterruptionLevel.FLAG,
            [SafetyViolation(
                violation_type="ignored_red_flag",
                description="x",
                severity="critical",
            )],
        )
        assert _clamp_interrupt(check) is False

    def test_modify_returns_false(self):
        # MODIFY should rewrite the response, not interrupt
        check = _check(
            InterruptionLevel.MODIFY,
            [SafetyViolation(
                violation_type="prescription_with_dose",
                description="x",
                severity="critical",
            )],
        )
        assert _clamp_interrupt(check) is False
