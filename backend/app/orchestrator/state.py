"""
ClinicalCaseState — shared TypedDict for the MedAgent orchestration graph.

Lives in its own module to avoid circular imports:
  agents → orchestrator.state  (OK)
  orchestrator.graph → agents  (OK)
  orchestrator.graph → orchestrator.state  (OK)
"""

from typing import TypedDict, Optional, Literal


class ClinicalCaseState(TypedDict):
    """Estado compartido por todos los agentes del grafo."""

    # Identificación
    case_id: str
    user_id: str

    # Mensajes
    messages: list[dict]  # Historial de conversación
    current_message: str  # Mensaje actual del usuario

    # Triage
    triage_level: Optional[Literal["green", "yellow", "red"]]
    triage_confidence: float
    red_flags: list[str]

    # Anamnesis
    extracted_facts: list[dict]
    pending_questions: list[str]
    completeness_score: float

    # Clasificación
    active_specialties: list[dict]  # [{name, weight, reason}]
    primary_specialty: Optional[str]

    # Especialistas
    specialist_outputs: dict[str, dict]  # {specialty: analysis}

    # Mesa Médica (v2)
    medical_board_result: Optional[dict]
    debate_rounds: int
    consensus_level: Optional[Literal["full", "partial", "disagreement"]]

    # Devil's Advocate (v2)
    challenges: list[dict]
    false_consensus_risk: float

    # Guardrail (v2)
    guardrail_violations: list[dict]
    guardrail_interrupt: bool

    # Síntesis
    synthesized_response: Optional[str]
    attention_level: Optional[str]

    # Control de flujo
    loop_count: int
    max_loops: int
    current_node: str
    force_close: bool

    # Document context (Phase 2.5) — injected before graph runs when message references docs
    # Shape: {"documents": [{doc_type, filename, ocr_preview}], "lab_values": [{test_name, ...}]}
    document_context: dict

    # Level-3 memory (Phase 4) — patient timeline + profile injected pre-graph
    patient_timeline: list[dict]   # ordered events: [{event_type, summary, details, occurred_at}]
    patient_profile: dict          # {allergies, active_medications, chronic_conditions, blood_type, age, sex}

    # Knowledge Base context (Phase 4) — RAG results injected pre-graph
    kb_context: str                # formatted string with [source: title] headers

    # Metadata
    created_at: str
    updated_at: str
