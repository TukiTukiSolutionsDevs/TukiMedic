"""
Guardrail Agent — Real-time safety monitor for MedAgent.

Inspired by Google g-AMIE (2026). Monitors every node output for safety
violations and can observe, flag, modify, or interrupt the clinical flow.
"""

from langchain_openai import ChatOpenAI

from app.agents._llm_safe import safe_ainvoke
from app.orchestrator.state import ClinicalCaseState
from app.agents.guardrail.schemas import GuardrailCheck, InterruptionLevel
from app.agents.guardrail.prompts import GUARDRAIL_SYSTEM_PROMPT
from app.agents.synthesizer.agent import BASE_DISCLAIMER, DISCLAIMER_SEPARATOR


# Fail-safe: when the safety LLM is down we cannot prove the content is safe,
# but interrupting every turn would brick the product. Approve as "observe"
# only, with an explicit escalation note so ops sees it in logs/audit.
_GUARDRAIL_FALLBACK = GuardrailCheck(
    approved=True,
    violations=[],
    interruption_level=InterruptionLevel.OBSERVE,
    modifications_suggested=[],
    escalation_required=True,
    escalation_reason="Guardrail LLM unavailable — degraded mode (no safety check ran).",
)


# Violation types whose critical-severity manifestations actually warrant
# interrupting the patient flow. Other violation_types (e.g. missing_disclaimer)
# are recoverable in-band — we record them in `violations` but do NOT interrupt.
_INTERRUPT_WORTHY_VIOLATIONS = frozenset({
    "ignored_red_flag",
    "prescription_with_dose",
    "symptom_minimization",
    "prompt_injection",
    "definitive_diagnosis_unsafe",
})


def _clamp_interrupt(check: GuardrailCheck) -> bool:
    """Defensive clamp on the guardrail INTERRUPT signal.

    The LLM's `interruption_level` is not anchored to severity in the prompt,
    so `INTERRUPT` was being emitted on benign clinical text (e.g. green/yellow
    cases routed to escalation_node despite no real emergency). This produced
    false-positive interrupts that degraded UX and added latency without
    preventing harm.

    Rule: only return True if ALL of the following hold:
      - check.interruption_level == INTERRUPT
      - at least one violation has severity == "critical"
      - at least one violation has a clinically-dangerous violation_type
        (see _INTERRUPT_WORTHY_VIOLATIONS)

    Mirrors `_clamp_triage` (triage/agent.py) and `_clamp_attention`
    (synthesizer/agent.py): LLM categorical contracts are validated against
    structured evidence before they alter the flow.
    """
    if check.interruption_level != InterruptionLevel.INTERRUPT:
        return False
    has_critical = any(v.severity == "critical" for v in check.violations)
    has_worthy = any(
        v.violation_type in _INTERRUPT_WORTHY_VIOLATIONS for v in check.violations
    )
    return has_critical and has_worthy


class GuardrailAgent:
    """Monitor de seguridad en tiempo real — inspirado en g-AMIE."""

    def __init__(
        self,
        chat_model=None,
        *,
        api_key: str | None = None,
        model: str = "gpt-4o",
        base_url: str | None = None,
    ):
        if chat_model is not None:
            self.llm = chat_model.with_structured_output(GuardrailCheck)
        else:
            self.llm = ChatOpenAI(
                model=model,
                temperature=0.0,
                api_key=api_key,
                base_url=base_url,
            ).with_structured_output(GuardrailCheck)

    async def __call__(self, state: ClinicalCaseState) -> dict:
        """Check the synthesized patient-facing response for safety violations.

        Only `synthesized_response` is reviewed here. Specialist outputs are
        intermediate clinical artefacts authored by domain LLMs — they use
        clinical language (drug names, doses, definitive-sounding phrasing)
        that the patient-facing GUARDRAIL_SYSTEM_PROMPT mis-flags. The
        synthesizer is the boundary that turns those internals into
        patient text; that's the artifact we monitor.

        The interruption signal goes through `_clamp_interrupt`, which
        requires both critical severity AND a clinically-dangerous
        violation_type before flipping the flow to escalation.
        """
        violations: list[dict] = []
        interrupt = False
        # Default: keep the original patient-facing response untouched.
        final_response = state.get("synthesized_response")

        if state.get("synthesized_response"):
            check = await self.check_content(
                state["synthesized_response"],
                node_name="synthesizer",
            )
            if not check.approved:
                for v in check.violations:
                    v.node_source = "synthesizer"
                violations.extend([v.model_dump() for v in check.violations])
                if _clamp_interrupt(check):
                    interrupt = True
                # Apply MODIFY: rewrite the patient-facing text with the
                # guardrail's suggestion. Falls back to the original if the
                # suggestion is empty so we never blank out the response.
                if check.interruption_level == InterruptionLevel.MODIFY:
                    suggested = "\n\n".join(
                        s.strip() for s in check.modifications_suggested if s and s.strip()
                    )
                    if suggested:
                        final_response = suggested + DISCLAIMER_SEPARATOR + BASE_DISCLAIMER

        result = {
            "guardrail_violations": violations,
            "guardrail_interrupt": interrupt,
            "current_node": "guardrail",
        }
        # Only propagate the response key when we actually had one to evaluate.
        if state.get("synthesized_response") is not None:
            result["synthesized_response"] = final_response
        return result

    async def check_content(self, content: str, node_name: str) -> GuardrailCheck:
        """Check a specific piece of content for safety violations.

        Can be called independently by the orchestrator for real-time
        monitoring of any node's output before it propagates.
        """
        messages = [
            {"role": "system", "content": GUARDRAIL_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    f"Revisá el siguiente contenido generado por el nodo '{node_name}':\n\n"
                    f"{content}"
                ),
            },
        ]
        return await safe_ainvoke(
            self.llm,
            messages,
            fallback=_GUARDRAIL_FALLBACK,
            agent_name="guardrail",
        )
