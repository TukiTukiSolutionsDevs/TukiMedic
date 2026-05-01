"""
Triage Agent — Entry point del grafo de orquestación MedAgent.

Clasifica la urgencia de una consulta médica en GREEN/YELLOW/RED.
Usa GPT-4o-mini por velocidad y costo. Temperature 0.0 para consistencia.
"""

from langchain_openai import ChatOpenAI

from app.agents._llm_safe import safe_ainvoke
from app.orchestrator.state import ClinicalCaseState
from app.agents.triage.schemas import TriageResult
from app.agents.triage.prompts import TRIAGE_SYSTEM_PROMPT
from app.agents.triage.tools import red_flag_checker


# Fail-safe default: yellow + low confidence so the user is steered to seek
# attention if the LLM is unavailable. NEVER default to green.
_TRIAGE_FALLBACK = TriageResult(
    level="yellow",
    confidence=0.3,
    red_flags_detected=[],
    reasoning="LLM no disponible; defaulting to yellow por precaución clínica.",
    recommended_urgency="24-48h",
)


def _clamp_triage(
    *,
    level: str,
    red_flags_detected: list[str],
    deterministic_matches: list,
) -> str:
    """Defensive clamp: demote RED to YELLOW when the LLM lacks evidence.

    The pre-LLM red_flag_checker already escalates deterministically to RED
    when YAML triggers match the message. If execution reaches the LLM and
    it still returns RED *without* populating `red_flags_detected` AND with
    no deterministic upstream match, that's an over-triage caused by LLM
    bias toward conservatism — demote to YELLOW so the patient still gets
    attention but the system doesn't trip the urgencia ER alarm.

    Mirrors `_clamp_attention` in synthesizer/agent.py: LLM categorical
    contracts are not trusted in isolation; we anchor to evidence.
    """
    if level != "red":
        return level
    has_llm_evidence = any((flag or "").strip() for flag in red_flags_detected)
    has_deterministic_evidence = bool(deterministic_matches)
    if has_llm_evidence or has_deterministic_evidence:
        return "red"
    return "yellow"


class TriageAgent:
    """Agente de triage clínico — nodo de LangGraph."""

    def __init__(
        self,
        chat_model=None,
        *,
        api_key: str | None = None,
        model: str = "gpt-4o-mini",
        base_url: str | None = None,
    ):
        if chat_model is not None:
            self.llm = chat_model.with_structured_output(TriageResult)
        else:
            self.llm = ChatOpenAI(
                model=model,
                temperature=0.0,
                api_key=api_key,
                base_url=base_url,
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

        result: TriageResult = await safe_ainvoke(
            self.llm,
            messages,
            fallback=_TRIAGE_FALLBACK,
            agent_name="triage",
        )

        # Defensive clamp: reaching this branch implies red_flag_matches was
        # empty (otherwise we'd have returned RED in step 1). If the LLM still
        # claims RED without populating red_flags_detected, demote to YELLOW.
        clamped_level = _clamp_triage(
            level=result.level,
            red_flags_detected=result.red_flags_detected,
            deterministic_matches=[],
        )

        return {
            "triage_level": clamped_level,
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
