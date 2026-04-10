"""
MedicalBoardAgent — Mesa Médica.

Coordinates multi-round debate between specialists, evaluates consensus,
and decides the resolution path (synthesis / extra_round / clarification).
"""

import json

from langchain_openai import ChatOpenAI

from app.orchestrator.graph import ClinicalCaseState
from app.agents.medical_board.schemas import MedicalBoardResult
from app.agents.medical_board.prompts import MEDICAL_BOARD_PROMPT

# Maximum extra rounds the board can request before forcing synthesis
MAX_EXTRA_ROUNDS = 2


def medical_board_router(state: ClinicalCaseState) -> str:
    """
    Conditional edge for the Medical Board node.

    Returns:
        "synthesis"       — consensus reached (full/partial) or max rounds exceeded
        "clarification"   — missing clinical info needed to resolve debate
        "devils_advocate" — disagreement and extra rounds still available
    """
    result = state.get("medical_board_result") or {}
    consensus_level = state.get("consensus_level") or result.get("consensus_level")
    resolution_path = result.get("resolution_path", "synthesis")
    debate_rounds = state.get("debate_rounds", 1)

    # Force close if we exceeded the extra-round budget
    if debate_rounds > MAX_EXTRA_ROUNDS + 1:  # +1 for the initial round
        return "synthesis"

    if resolution_path == "clarification":
        return "clarification"

    if resolution_path == "extra_round" and consensus_level == "disagreement":
        return "devils_advocate"

    return "synthesis"


class MedicalBoardAgent:
    """Mesa Médica — evaluates specialist consensus after multi-round debate."""

    def __init__(self, api_key: str, model: str = "gpt-4o"):
        self.llm = ChatOpenAI(
            model=model,
            temperature=0.2,
            api_key=api_key,
        ).with_structured_output(MedicalBoardResult)

    def _format_specialist_analyses(self, specialist_outputs: dict) -> str:
        """Render all specialist analyses as structured text for the moderator."""
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
                    lines.append(
                        f"  - {d.get('condition')} [{d.get('probability')}]"
                    )

            studies = analysis.get("suggested_studies", [])
            if studies:
                lines.append(f"Estudios sugeridos: {', '.join(studies)}")

            alarm = analysis.get("alarm_signs", [])
            if alarm:
                lines.append(f"Signos de alarma: {', '.join(alarm)}")

            needs_ref = analysis.get("needs_referral", False)
            referrals = analysis.get("referral_to", [])
            if needs_ref and referrals:
                lines.append(f"Derivación sugerida a: {', '.join(referrals)}")

            confidence = analysis.get("confidence")
            if confidence is not None:
                lines.append(f"Confianza: {confidence:.0%}")

        return "\n".join(lines)

    def _format_challenges(self, challenges: list[dict]) -> str:
        """Render Devil's Advocate challenges for the moderator."""
        if not challenges:
            return ""

        lines = ["\n## Desafíos del Devil's Advocate"]
        for ch in challenges:
            lines.append(f"\n### Especialista desafiado: {ch.get('specialist', '')}")
            lines.append(f"Desafío: {ch.get('challenge', '')}")
            lines.append(
                f"Hipótesis alternativa: {ch.get('alternative_hypothesis', '')}"
            )
            assumption = ch.get("unexamined_assumption", "")
            if assumption:
                lines.append(f"Suposición no examinada: {assumption}")

        return "\n".join(lines)

    async def __call__(self, state: ClinicalCaseState) -> dict:
        specialist_outputs = state.get("specialist_outputs", {})
        challenges = state.get("challenges", [])
        current_rounds = state.get("debate_rounds", 0)

        analyses_text = self._format_specialist_analyses(specialist_outputs)
        challenges_text = self._format_challenges(challenges)

        user_content = f"## Análisis de especialistas\n{analyses_text}"
        if challenges_text:
            user_content += f"\n\n{challenges_text}"

        messages = [
            {"role": "system", "content": MEDICAL_BOARD_PROMPT},
            {"role": "user", "content": user_content},
        ]

        result: MedicalBoardResult = await self.llm.ainvoke(messages)

        # debate_rounds counts actual board evaluations (starts at 0 in state)
        new_rounds = current_rounds + 1

        return {
            "medical_board_result": result.model_dump(),
            "consensus_level": result.consensus_level,
            "debate_rounds": new_rounds,
            "current_node": "medical_board",
        }
