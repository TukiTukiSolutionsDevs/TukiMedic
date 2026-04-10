"""
MedAgent Orchestration Graph — v2

StateGraph de LangGraph que implementa el flujo deliberativo:
Triage → Anamnesis → Classification → Specialists (parallel)
→ Mesa Médica (debate) → Synthesizer

Con Guardrail Agent monitoreando en paralelo en tiempo real.

NOTE: ClinicalCaseState lives in orchestrator.state to avoid circular imports.
Agents import from there; this module imports agents → no cycle.
"""

from langgraph.graph import StateGraph, END

# State lives in its own module — agents import from there, avoiding cycles
from app.orchestrator.state import ClinicalCaseState  # noqa: F401 (re-exported)

from app.agents.triage import TriageAgent, triage_router
from app.agents.anamnesis import AnamnesisAgent
from app.agents.classifier import ClassifierAgent, classification_router
import app.agents.specialists  # noqa: F401 — triggers @register decorators
from app.agents.specialists.dispatcher import dispatch_specialists
from app.agents.medical_board import MedicalBoardAgent, medical_board_router
from app.agents.devils_advocate import DevilsAdvocateAgent
from app.agents.guardrail import GuardrailAgent
from app.agents.synthesizer import SynthesizerAgent


# ---------------------------------------------------------------------------
# Loop control configuration
# ---------------------------------------------------------------------------

LOOP_CONFIG = {
    "max_loops": 3,
    "max_specialists_per_loop": 4,
    "max_questions_per_turn": 4,
    "min_completeness_for_synthesis": 0.6,
    "force_synthesis_after_loops": True,
    "specialty_activation_threshold": 0.4,
    "max_medical_board_extra_rounds": 2,
}


# ---------------------------------------------------------------------------
# State factory
# ---------------------------------------------------------------------------

def create_initial_state(case_id: str, user_id: str, message: str) -> ClinicalCaseState:
    """Create a fresh ClinicalCaseState for a new conversation turn."""
    return {
        "case_id": case_id,
        "user_id": user_id,
        "messages": [],
        "current_message": message,
        "triage_level": None,
        "triage_confidence": 0.0,
        "red_flags": [],
        "extracted_facts": [],
        "pending_questions": [],
        "completeness_score": 0.0,
        "active_specialties": [],
        "primary_specialty": None,
        "specialist_outputs": {},
        "medical_board_result": None,
        "debate_rounds": 0,
        "consensus_level": None,
        "challenges": [],
        "false_consensus_risk": 0.0,
        "guardrail_violations": [],
        "guardrail_interrupt": False,
        "synthesized_response": None,
        "attention_level": None,
        "loop_count": 0,
        "max_loops": LOOP_CONFIG["max_loops"],
        "current_node": "",
        "force_close": False,
        "document_context": {},
        "created_at": "",
        "updated_at": "",
    }


# ---------------------------------------------------------------------------
# Internal nodes
# ---------------------------------------------------------------------------

async def _escalation_node(state: ClinicalCaseState) -> dict:
    """Handle escalation — generate urgent response without full analysis."""
    red_flags_str = ", ".join(state.get("red_flags", []))
    return {
        "synthesized_response": (
            f"⚠️ ATENCIÓN: Se detectaron señales que requieren atención médica inmediata.\n\n"
            f"Señales detectadas: {red_flags_str}\n\n"
            f"Por favor, acude a urgencias o llama a servicios de emergencia lo antes posible.\n\n"
            f"Este sistema no puede atender emergencias médicas. "
            f"Si estás en peligro inmediato, llama al número de emergencias de tu país."
        ),
        "attention_level": "urgencia",
        "current_node": "escalation",
    }


def _guardrail_router(state: ClinicalCaseState) -> str:
    """Route after guardrail check."""
    if state.get("guardrail_interrupt"):
        return "escalation"
    return END


# ---------------------------------------------------------------------------
# Graph builder
# ---------------------------------------------------------------------------

def build_graph(api_key: str) -> StateGraph:
    """Build the complete MedAgent orchestration graph.

    Args:
        api_key: User's API key (BYOK model). Injected into all agents.

    Returns:
        Compiled LangGraph StateGraph ready for execution.
    """
    # Instantiate agents with user's API key
    triage = TriageAgent(api_key=api_key)
    anamnesis = AnamnesisAgent(api_key=api_key)
    classifier = ClassifierAgent(api_key=api_key)
    medical_board = MedicalBoardAgent(api_key=api_key)
    devils_advocate = DevilsAdvocateAgent(api_key=api_key)
    guardrail = GuardrailAgent(api_key=api_key)
    synthesizer = SynthesizerAgent(api_key=api_key)

    # Build graph
    workflow = StateGraph(ClinicalCaseState)

    # Add nodes
    workflow.add_node("triage", triage)
    workflow.add_node("anamnesis", anamnesis)
    workflow.add_node("classification", classifier)
    async def specialist_node(state: ClinicalCaseState) -> dict:
        return await dispatch_specialists(state, api_key=api_key)

    workflow.add_node("specialists", specialist_node)
    workflow.add_node("medical_board", medical_board)
    workflow.add_node("devils_advocate", devils_advocate)
    workflow.add_node("guardrail", guardrail)
    workflow.add_node("synthesizer", synthesizer)
    workflow.add_node("escalation", _escalation_node)

    # Entry point
    workflow.set_entry_point("triage")

    # --- Edges ---

    # triage → escalation | anamnesis | classification
    workflow.add_conditional_edges("triage", triage_router)

    # anamnesis → classification (always)
    workflow.add_edge("anamnesis", "classification")

    # classification → specialists (always)
    workflow.add_conditional_edges("classification", classification_router)

    # specialists → medical_board (always)
    workflow.add_edge("specialists", "medical_board")

    # medical_board → synthesizer | anamnesis (clarification loop) | devils_advocate
    # NOTE: medical_board_router returns "synthesis" not "synthesizer" — remap here.
    # "clarification" loops back to anamnesis so the patient can answer missing info.
    workflow.add_conditional_edges(
        "medical_board",
        medical_board_router,
        {
            "synthesis": "synthesizer",
            "clarification": "anamnesis",
            "devils_advocate": "devils_advocate",
        },
    )

    # devils_advocate → medical_board (loop back for re-evaluation)
    workflow.add_edge("devils_advocate", "medical_board")

    # synthesizer → guardrail (sequential safety check on final output)
    workflow.add_edge("synthesizer", "guardrail")

    # guardrail → END | escalation
    workflow.add_conditional_edges(
        "guardrail",
        _guardrail_router,
        {
            "escalation": "escalation",
            END: END,
        },
    )

    # escalation → END
    workflow.add_edge("escalation", END)

    return workflow.compile()
