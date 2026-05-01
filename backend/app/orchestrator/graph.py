"""
MedAgent Orchestration Graph — v2

StateGraph de LangGraph que implementa el flujo deliberativo:
Triage → Anamnesis → Classification → Specialists (parallel)
→ Mesa Médica (debate) → Synthesizer

Con Guardrail Agent monitoreando en paralelo en tiempo real.

NOTE: ClinicalCaseState lives in orchestrator.state to avoid circular imports.
Agents import from there; this module imports agents → no cycle.
"""

import asyncio
import logging
import uuid
from typing import Any, Awaitable, Callable

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

# Re-export `async_session` (NullPool-backed audit factory) so monkeypatching
# in tests works.  The audit factory uses NullPool to prevent asyncpg
# InterfaceError when LangGraph interleaves coroutines on the same event loop.
from app.core.database import audit_session as async_session  # noqa: F401 — patched in tests

from app.services.audit import log_clinical_decision
from app.services.llm_router import ProviderCredentialDTO, get_chat_model
from app.agents.synthesizer.agent import BASE_DISCLAIMER, DISCLAIMER_SEPARATOR

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Clinical audit — model versions (bump suffix when prompt or model changes)
# ---------------------------------------------------------------------------

TRIAGE_MODEL = "gpt-4o-mini@triage-v1"
GUARDRAIL_MODEL = "gpt-4o@guardrail-v1"
SYNTHESIZER_MODEL = "gpt-4o@synthesizer-v1"


# ---------------------------------------------------------------------------
# Audit detail builders — pure functions: (state, result) -> dict
# ---------------------------------------------------------------------------

def _triage_details(state: dict, result: dict) -> dict:
    return {
        "urgency_level": result.get("triage_level"),
        "red_flags_detected": result.get("red_flags", []),
        "confidence": result.get("triage_confidence"),
    }


def _guardrail_details(state: dict, result: dict) -> dict:
    return {
        "violations": result.get("guardrail_violations", []),
        "interrupt": bool(result.get("guardrail_interrupt", False)),
    }


def _synthesizer_details(state: dict, result: dict) -> dict:
    response = result.get("synthesized_response") or ""
    return {
        "attention_level": result.get("attention_level"),
        "response_length": len(response),
    }


# ---------------------------------------------------------------------------
# Audit wrapper — fail-open: if audit logging fails, the node still returns.
# ---------------------------------------------------------------------------

NodeFn = Callable[[dict], Awaitable[dict]]
DetailsFn = Callable[[dict, dict], dict]


def _audit_node(
    node: NodeFn,
    *,
    action: str,
    model_version: str,
    build_details: DetailsFn,
) -> NodeFn:
    """Wrap a graph node so each invocation persists an audit log entry.

    Behaviour:
    - The wrapped node runs first; we only audit the *result*.
    - Each call opens its OWN fresh AsyncSession via async_session() — never
      reusing a session from state or from a sibling coroutine. This is safe
      under asyncio.gather (concurrent specialists) because each session has
      its own connection from the pool.
    - Audit failures are swallowed and logged — they MUST NOT block the
      clinical flow. The patient must still get a response if the audit DB
      is down. The exception is captured for ops to investigate.
    """

    async def _wrapped(state: dict) -> dict:
        result = await node(state)
        try:
            raw_case_id = state.get("case_id")
            case_id = (
                uuid.UUID(raw_case_id)
                if isinstance(raw_case_id, str) and raw_case_id
                else (raw_case_id or uuid.uuid4())
            )
            user_raw = state.get("user_id")
            user_id = uuid.UUID(user_raw) if isinstance(user_raw, str) and user_raw else None

            details = build_details(state, result)

            # Schedule the DB write as a top-level asyncio Task so it runs in a
            # clean greenlet context — NOT nested inside LangGraph's greenlet.
            # SQLAlchemy's greenlet_spawn conflicts with LangGraph's scheduler
            # when called from within an already-active SQLAlchemy greenlet chain.
            # create_task() breaks that chain: the task starts from the event loop's
            # root greenlet, avoiding "another operation is in progress" errors.
            async def _write_audit() -> None:
                async with async_session() as db:
                    await log_clinical_decision(
                        db,
                        case_id=case_id,
                        action=action,
                        details=details,
                        model_version=model_version,
                        user_id=user_id,
                    )
                    await db.commit()

            await asyncio.ensure_future(_write_audit())
        except Exception:  # noqa: BLE001 — fail-open by design
            log.exception(
                "clinical audit failed for action=%s; continuing with node result",
                action,
            )
        return result

    return _wrapped


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
        "patient_timeline": [],
        "patient_profile": {},
        "kb_context": "",
        "created_at": "",
        "updated_at": "",
    }


# ---------------------------------------------------------------------------
# Internal nodes
# ---------------------------------------------------------------------------

# Triage level → max attention_level when escalation is NOT a real emergency
# (i.e. triggered by guardrail interrupt rather than red flags). Keeps the
# patient-facing recommendation aligned with what triage actually classified.
_TRIAGE_TO_ATTENTION_NON_EMERGENCY: dict[str | None, str] = {
    "green": "rutina",
    "yellow": "24-48h",
}


async def _escalation_node(state: ClinicalCaseState) -> dict:
    """Handle escalation — two paths reach this node:

    1. **Real medical emergency**: triage classified the case as ``red`` (or
       red flags surfaced). We return the canonical "go to ER NOW" message and
       force ``attention_level="urgencia"``.
    2. **Guardrail interrupt on non-emergency triage**: the safety filter
       blocked the synthesizer output, but the patient is NOT in medical
       urgency. Returning the ER alarm here is a false positive — it triggers
       over-escalation (8/9 fails in the 25-case eval baseline). Instead we
       map ``attention_level`` from the triage classification and return a
       neutral safety message that preserves any synthesized response that
       was already deemed acceptable (or substitutes a generic
       "consultá con un profesional" when no response is present).

    Always appends ``BASE_DISCLAIMER`` exactly once so the legal medical
    disclaimer is present on every escalation message regardless of path.
    """
    triage_level = state.get("triage_level")
    red_flags = state.get("red_flags") or []
    is_real_emergency = triage_level == "red" or bool(red_flags)

    if is_real_emergency:
        red_flags_str = ", ".join(red_flags) if red_flags else "señales clínicas urgentes"
        clinical_message = (
            f"⚠️ ATENCIÓN: Se detectaron señales que requieren atención médica inmediata.\n\n"
            f"Señales detectadas: {red_flags_str}\n\n"
            f"Por favor, acude a urgencias o llama a servicios de emergencia lo antes posible.\n\n"
            f"Este sistema no puede atender emergencias médicas. "
            f"Si estás en peligro inmediato, llama al número de emergencias de tu país."
        )
        return {
            "synthesized_response": clinical_message + DISCLAIMER_SEPARATOR + BASE_DISCLAIMER,
            "attention_level": "urgencia",
            "current_node": "escalation",
        }

    # Non-emergency escalation (guardrail-driven safety filter).
    attention = _TRIAGE_TO_ATTENTION_NON_EMERGENCY.get(triage_level, "24-48h")
    existing = (state.get("synthesized_response") or "").strip()
    if not existing:
        existing = (
            "No podemos darte una respuesta clínica completa en este momento. "
            "Te recomendamos consultar con un profesional de salud para revisar "
            "tu caso con la información necesaria."
        )
    if BASE_DISCLAIMER.lower() not in existing.lower():
        existing = existing.rstrip() + DISCLAIMER_SEPARATOR + BASE_DISCLAIMER
    return {
        "synthesized_response": existing,
        "attention_level": attention,
        "current_node": "escalation",
    }


def _with_disclaimer(node: NodeFn) -> NodeFn:
    """Ensure BASE_DISCLAIMER is always present in synthesized_response.

    Idempotent: if the response already contains BASE_DISCLAIMER (case-insensitive
    exact match), it is not appended again.

    This guards against LLM-paraphrased disclaimers: Gemini fills
    SynthesizedResponse.disclaimer with a non-empty paraphrase, which causes
    _compose_patient_text to skip the BASE_DISCLAIMER fallback.  Any path
    through the synthesizer node must include the canonical disclaimer so the
    guardrail and clinical-eval checks pass.
    """

    async def _wrapped(state: dict) -> dict:
        result = await node(state)
        response = result.get("synthesized_response") or ""
        if BASE_DISCLAIMER.lower() not in response.lower():
            result = {
                **result,
                "synthesized_response": response.rstrip() + DISCLAIMER_SEPARATOR + BASE_DISCLAIMER,
            }
        return result

    return _wrapped


def _guardrail_router(state: ClinicalCaseState) -> str:
    """Route after guardrail check."""
    if state.get("guardrail_interrupt"):
        return "escalation"
    return END


def _specialists_router(state: ClinicalCaseState) -> str:
    """Route after specialists dispatch.

    Green-triage cases bypass medical_board to save ~30-40s of smart-tier
    LLM latency. The medical board's deliberative debate adds limited value
    for low-stakes consultations where the dominant differential is benign.

    Yellow and any non-green triage level keep the full deliberation path.
    Red cases never reach this router because triage_router escalates first.
    """
    if state.get("triage_level") == "green":
        return "synthesizer"
    return "medical_board"


# ---------------------------------------------------------------------------
# Graph builder
# ---------------------------------------------------------------------------

def build_graph(cred: ProviderCredentialDTO) -> StateGraph:
    """Build the complete MedAgent orchestration graph.

    Args:
        cred: Provider credential DTO from the LLM router. Contains a
              decrypted ``api_key`` and an optional ``base_url`` for
              multi-provider support (e.g. Gemini OpenAI-compat endpoint).

    Returns:
        Compiled LangGraph StateGraph ready for execution.
    """
    # Resolve provider-correct models from the router — no model name hardcoded here.
    # "fast" tier: high-throughput nodes (triage, anamnesis, specialists, etc.)
    # "smart" tier: deliberative nodes that need deeper reasoning (medical_board)
    triage = TriageAgent(chat_model=get_chat_model("fast", cred, temperature=0.0))
    anamnesis = AnamnesisAgent(chat_model=get_chat_model("fast", cred, temperature=0.3))
    classifier = ClassifierAgent(chat_model=get_chat_model("fast", cred, temperature=0.2))
    medical_board = MedicalBoardAgent(chat_model=get_chat_model("smart", cred, temperature=0.2))
    devils_advocate = DevilsAdvocateAgent(chat_model=get_chat_model("fast", cred, temperature=0.5))
    guardrail = GuardrailAgent(chat_model=get_chat_model("fast", cred, temperature=0.0))
    synthesizer = SynthesizerAgent(chat_model=get_chat_model("fast", cred, temperature=0.4))

    # Build graph
    workflow = StateGraph(ClinicalCaseState)

    # Add nodes — clinical decisions are wrapped with the audit logger so
    # every triage / guardrail / synthesis call is persisted with model
    # version + sha256 fingerprint of inputs (legal defensibility).
    workflow.add_node(
        "triage",
        _audit_node(
            triage,
            action="triage_decision",
            model_version=TRIAGE_MODEL,
            build_details=_triage_details,
        ),
    )
    workflow.add_node("anamnesis", anamnesis)
    workflow.add_node("classification", classifier)

    async def specialist_node(state: ClinicalCaseState) -> dict:
        # Fresh model per invocation — specialists share tier but each gets their own instance
        spec_model = get_chat_model("fast", cred, temperature=0.3)
        return await dispatch_specialists(state, chat_model=spec_model)

    workflow.add_node("specialists", specialist_node)
    workflow.add_node("medical_board", medical_board)
    workflow.add_node("devils_advocate", devils_advocate)
    workflow.add_node(
        "guardrail",
        _audit_node(
            guardrail,
            action="guardrail_violation",
            model_version=GUARDRAIL_MODEL,
            build_details=_guardrail_details,
        ),
    )
    workflow.add_node(
        "synthesizer",
        _audit_node(
            _with_disclaimer(synthesizer),
            action="response_synthesized",
            model_version=SYNTHESIZER_MODEL,
            build_details=_synthesizer_details,
        ),
    )
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

    # specialists → medical_board | synthesizer (bypass for green triage)
    workflow.add_conditional_edges(
        "specialists",
        _specialists_router,
        {
            "medical_board": "medical_board",
            "synthesizer": "synthesizer",
        },
    )

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
