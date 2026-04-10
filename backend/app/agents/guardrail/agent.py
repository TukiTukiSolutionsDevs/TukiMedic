"""
Guardrail Agent — Real-time safety monitor for MedAgent.

Inspired by Google g-AMIE (2026). Monitors every node output for safety
violations and can observe, flag, modify, or interrupt the clinical flow.
"""

from langchain_openai import ChatOpenAI

from app.orchestrator.state import ClinicalCaseState
from app.agents.guardrail.schemas import GuardrailCheck, InterruptionLevel
from app.agents.guardrail.prompts import GUARDRAIL_SYSTEM_PROMPT


class GuardrailAgent:
    """Monitor de seguridad en tiempo real — inspirado en g-AMIE."""

    def __init__(self, api_key: str, model: str = "gpt-4o"):
        self.llm = ChatOpenAI(
            model=model,
            temperature=0.0,
            api_key=api_key,
        ).with_structured_output(GuardrailCheck)

    async def __call__(self, state: ClinicalCaseState) -> dict:
        """Check current state content for safety violations."""
        violations = []
        interrupt = False

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

        return {
            "guardrail_violations": violations,
            "guardrail_interrupt": interrupt,
            "current_node": "guardrail",
        }

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
        return await self.llm.ainvoke(messages)
