"""
DevilsAdvocateAgent — Abogado del Diablo.

Explicitly challenges every specialist's conclusions to prevent false consensus.
Runs between Medical Board rounds when disagreement persists.
"""

from langchain_openai import ChatOpenAI

from app.agents._llm_safe import safe_ainvoke
from app.orchestrator.state import ClinicalCaseState
from app.agents.devils_advocate.schemas import ChallengeResult
from app.agents.devils_advocate.prompts import DEVILS_ADVOCATE_PROMPT


# Fail-safe: no challenges, conservative consensus risk. The graph will skip
# the contrarian round, which is acceptable when the LLM is unavailable.
_DEVILS_ADVOCATE_FALLBACK = ChallengeResult(
    challenges_per_specialist=[],
    alternative_hypotheses=[],
    unexamined_assumptions=[],
    false_consensus_risk=0.0,
    critical_questions=[],
)


class DevilsAdvocateAgent:
    """Devil's Advocate — challenges specialist conclusions to prevent groupthink."""

    def __init__(self, api_key: str, model: str = "gpt-4o", base_url: str | None = None):
        self.llm = ChatOpenAI(
            model=model,
            temperature=0.5,
            api_key=api_key,
            base_url=base_url,
        ).with_structured_output(ChallengeResult)

    def _format_specialist_analyses(self, specialist_outputs: dict) -> str:
        """Render specialist analyses as input for the Devil's Advocate."""
        if not specialist_outputs:
            return "No hay análisis de especialistas disponibles."

        lines = []
        for specialty, analysis in specialist_outputs.items():
            lines.append(f"\n### Especialista: {specialty}")
            lines.append(f"Impresión clínica: {analysis.get('clinical_impression', '')}")

            diffs = analysis.get("differential_diagnosis", [])
            if diffs:
                lines.append("Diagnósticos diferenciales:")
                for d in diffs:
                    evidence = ", ".join(d.get("supporting_evidence", []))
                    against = ", ".join(d.get("against_evidence", []))
                    line = f"  - {d.get('condition')} [{d.get('probability')}]"
                    if evidence:
                        line += f" — a favor: {evidence}"
                    if against:
                        line += f" — en contra: {against}"
                    lines.append(line)

            recommendations = analysis.get("recommendations", [])
            if recommendations:
                lines.append(f"Recomendaciones: {', '.join(recommendations)}")

            alarm = analysis.get("alarm_signs", [])
            if alarm:
                lines.append(f"Signos de alarma: {', '.join(alarm)}")

            confidence = analysis.get("confidence")
            if confidence is not None:
                lines.append(f"Confianza declarada: {confidence:.0%}")

        return "\n".join(lines)

    async def __call__(self, state: ClinicalCaseState) -> dict:
        specialist_outputs = state.get("specialist_outputs", {})

        analyses_text = self._format_specialist_analyses(specialist_outputs)

        messages = [
            {"role": "system", "content": DEVILS_ADVOCATE_PROMPT},
            {
                "role": "user",
                "content": (
                    "A continuación están los análisis de los especialistas. "
                    "Desafía cada uno:\n\n"
                    f"{analyses_text}"
                ),
            },
        ]

        result: ChallengeResult = await safe_ainvoke(
            self.llm,
            messages,
            fallback=_DEVILS_ADVOCATE_FALLBACK,
            agent_name="devils_advocate",
        )

        # Flatten challenges to list[dict] for state storage
        challenges_dicts = [c.model_dump() for c in result.challenges_per_specialist]

        return {
            "challenges": challenges_dicts,
            "false_consensus_risk": result.false_consensus_risk,
            "current_node": "devils_advocate",
        }
