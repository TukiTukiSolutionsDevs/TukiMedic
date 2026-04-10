"""
Triage Agent — Entry point del grafo de orquestación MedAgent.

Clasifica la urgencia de una consulta médica en GREEN/YELLOW/RED.
Usa GPT-4o-mini por velocidad y costo. Temperature 0.0 para consistencia.
"""

from langchain_openai import ChatOpenAI

from app.orchestrator.state import ClinicalCaseState
from app.agents.triage.schemas import TriageResult
from app.agents.triage.prompts import TRIAGE_SYSTEM_PROMPT
from app.agents.triage.tools import red_flag_checker


class TriageAgent:
    """Agente de triage clínico — nodo de LangGraph."""

    def __init__(self, api_key: str, model: str = "gpt-4o-mini"):
        self.llm = ChatOpenAI(
            model=model,
            temperature=0.0,
            api_key=api_key,
        ).with_structured_output(TriageResult)

    async def __call__(self, state: ClinicalCaseState) -> dict:
        """Execute triage and return partial state update."""
        message = state["current_message"]

        # Step 1: Pre-LLM red flag check (no tokens spent)
        red_flag_matches = red_flag_checker(message)

        if red_flag_matches:
            # Automatic RED — bypass LLM for speed
            return {
                "triage_level": "red",
                "triage_confidence": 1.0,
                "red_flags": [m.details for m in red_flag_matches],
                "current_node": "triage",
            }

        # Step 2: LLM-based triage
        messages = [
            {"role": "system", "content": TRIAGE_SYSTEM_PROMPT},
            {"role": "user", "content": message},
        ]

        # Add context from previous messages if available
        if state.get("extracted_facts"):
            facts_str = "\n".join(
                f"- {f.get('value', '')}" for f in state["extracted_facts"]
            )
            messages.insert(1, {
                "role": "system",
                "content": f"Contexto clínico previo del paciente:\n{facts_str}",
            })

        result: TriageResult = await self.llm.ainvoke(messages)

        return {
            "triage_level": result.level,
            "triage_confidence": result.confidence,
            "red_flags": result.red_flags_detected,
            "current_node": "triage",
        }


def triage_router(state: ClinicalCaseState) -> str:
    """Route after triage — decides next node in the graph."""
    if state["triage_level"] == "red" and state["red_flags"]:
        return "escalation"
    if state["loop_count"] == 0 and state["completeness_score"] < 0.5:
        return "anamnesis"
    return "classification"
