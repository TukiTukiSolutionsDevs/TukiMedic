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
        """Check current state content for safety violations."""
        violations = []
        interrupt = False
        # Default: keep the original patient-facing response untouched.
        final_response = state.get("synthesized_response")

        # 1. Check synthesized_response if present (final output — highest priority)
        if state.get("synthesized_response"):
            check = await self.check_content(
                state["synthesized_response"],
                node_name="synthesizer",
            )
            if not check.approved:
                for v in check.violations:
                    v.node_source = "synthesizer"
                violations.extend([v.model_dump() for v in check.violations])
                if check.interruption_level == InterruptionLevel.INTERRUPT:
                    interrupt = True
                # Apply MODIFY: rewrite the patient-facing text with the
                # guardrail's suggestion. Falls back to the original if the
                # suggestion is empty so we never blank out the response.
                if check.interruption_level == InterruptionLevel.MODIFY:
                    suggested = "\n\n".join(
                        s.strip() for s in check.modifications_suggested if s and s.strip()
                    )
                    if suggested:
                        final_response = suggested

        # 2. Check specialist outputs for unsafe content
        for specialty, output in (state.get("specialist_outputs") or {}).items():
            content = ""
            if isinstance(output, dict):
                content = output.get("clinical_impression", "") + " " + " ".join(
                    output.get("recommendations", [])
                )
            elif isinstance(output, str):
                content = output

            if content.strip():
                check = await self.check_content(content, node_name=f"specialist_{specialty}")
                if not check.approved:
                    for v in check.violations:
                        v.node_source = f"specialist_{specialty}"
                    violations.extend([v.model_dump() for v in check.violations])
                    if check.interruption_level == InterruptionLevel.INTERRUPT:
                        interrupt = True

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
