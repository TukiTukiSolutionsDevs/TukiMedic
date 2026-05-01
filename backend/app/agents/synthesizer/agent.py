"""
Synthesizer Agent — Consolidates all agent outputs into one patient-facing response.

Takes triage, specialist analyses, and medical board result and produces a
single clear, empathetic, actionable response for the patient.
"""

import json

from langchain_openai import ChatOpenAI

from app.agents._llm_safe import safe_ainvoke
from app.orchestrator.state import ClinicalCaseState
from app.agents.synthesizer.schemas import SynthesizedResponse
from app.agents.synthesizer.prompts import SYNTHESIZER_SYSTEM_PROMPT
from app.core.prompt_guard import wrap_user_input
from app.core.sanitize import sanitize_patient_markdown


# Fail-safe message: tell the user we couldn't process the case and to seek
# in-person attention. NEVER produce a clinical recommendation in fallback.
_SYNTHESIZER_FALLBACK = SynthesizedResponse(
    patient_response=(
        "Lo siento, en este momento no puedo procesar tu consulta clínica. "
        "Por favor reintentá en unos minutos. Si tu situación es urgente, "
        "consultá presencialmente con un profesional o llamá a emergencias."
    ),
    clinical_summary="LLM unavailable; returned safe-fallback patient response.",
    specialties_involved=[],
    attention_level="24-48h",
    follow_up_questions=[],
    alarm_signs=[],
)


# Base disclaimer always concatenated to the patient-facing response.
# Even when the LLM omits or returns an empty disclaimer, this MUST appear.
BASE_DISCLAIMER = (
    "MedAgent es una herramienta de orientación; "
    "no reemplaza la consulta médica profesional."
)
DISCLAIMER_SEPARATOR = "\n\n---\n\n"

# Shown to free users when specialist analysis was skipped at the orchestrator
# level (see `_should_gate_specialists` in app.orchestrator.graph). Stable
# constant so the frontend can detect / restyle it if needed.
TIER_UPGRADE_HINT = (
    "Análisis con especialistas (8 agentes) disponible en el plan Premium. "
    "Esta respuesta se basa en el triaje básico."
)


def _compose_patient_text(
    patient_response: str,
    disclaimer: str | None,
    *,
    upgrade_hint: str | None = None,
) -> str:
    """Append disclaimer (and optional upgrade hint) to the patient response.

    The patient_response is sanitized via `sanitize_patient_markdown` before
    being concatenated — this removes HTML tags, dangerous URL schemes,
    Markdown image references, and zero-width Unicode characters. The
    disclaimer and the optional upgrade_hint are left intact (we control
    both sources).

    Layout (when both present):
        body
        ---
        upgrade_hint
        ---
        disclaimer

    Falls back to BASE_DISCLAIMER if the LLM returned an empty or missing one.
    """
    body = sanitize_patient_markdown(patient_response).strip()
    extra = (disclaimer or "").strip()
    if not extra:
        extra = BASE_DISCLAIMER
    hint = (upgrade_hint or "").strip()

    parts: list[str] = []
    if body:
        parts.append(body)
    if hint:
        parts.append(hint)
    parts.append(extra)
    return DISCLAIMER_SEPARATOR.join(parts)


# Ranking of attention levels — higher == more urgent.
_ATTENTION_RANK: dict[str, int] = {
    "rutina": 0,
    "24-48h": 1,
    "hoy": 2,
    "urgencia": 3,
}

# Per-triage attention ceiling. Keeps the synthesizer LLM from escalating
# beyond what triage classified, while preserving downward flexibility (the
# LLM can pick any level <= ceiling). Red has no ceiling — urgencia is fine.
_TRIAGE_ATTENTION_CEILING: dict[str, str] = {
    "green": "24-48h",
    "yellow": "hoy",
}


def _clamp_attention(triage_level: str | None, attention_level: str) -> str:
    """Clamp a synthesizer-chosen attention level by the triage ceiling.

    The synthesizer prompt biases the LLM toward "more conservative" attention
    levels when specialists disagree. Combined with multi-specialist outputs
    on yellow/green cases, this systematically over-escalates to ``urgencia``.
    The clamp guarantees attention_level <= ceiling derived from triage_level.

    No upward clamp: if the LLM picks something LESS urgent than the ceiling,
    that's preserved (it could be a legitimate clinical judgment that the
    case is benign even though triage flagged it yellow).

    For unknown triage_level (None or missing key), the clamp is skipped —
    we cannot derive a safe ceiling, so we trust the LLM.
    """
    ceiling = _TRIAGE_ATTENTION_CEILING.get(triage_level or "")
    if ceiling is None:
        return attention_level
    if _ATTENTION_RANK[attention_level] > _ATTENTION_RANK[ceiling]:
        return ceiling
    return attention_level


class SynthesizerAgent:
    """Agente sintetizador — nodo final del grafo de orquestación."""

    def __init__(
        self,
        chat_model=None,
        *,
        api_key: str | None = None,
        model: str = "gpt-4o",
        base_url: str | None = None,
    ):
        if chat_model is not None:
            self.llm = chat_model.with_structured_output(SynthesizedResponse)
        else:
            self.llm = ChatOpenAI(
                model=model,
                temperature=0.4,
                api_key=api_key,
                base_url=base_url,
            ).with_structured_output(SynthesizedResponse)

    async def __call__(self, state: ClinicalCaseState) -> dict:
        """Synthesize all agent outputs into a single patient-facing response."""

        # 1. Build context from all upstream outputs
        context_parts = []

        # Triage
        triage_level = state.get("triage_level", "unknown")
        red_flags = state.get("red_flags", [])
        context_parts.append(
            f"## Triage\nNivel: {triage_level}\n"
            f"Red flags: {', '.join(red_flags) if red_flags else 'ninguno'}"
        )

        # Original message — wrapped in explicit delimiters so the LLM
        # treats it as DATA, not as instructions. This is the key
        # containment for prompt injection that slips past the triage
        # pre-filter (e.g. obfuscated patterns, novel jailbreaks).
        if state.get("current_message"):
            context_parts.append(
                f"## Consulta del paciente\n{wrap_user_input(state['current_message'])}"
            )

        # Extracted facts from anamnesis
        if state.get("extracted_facts"):
            facts = [
                f"- {f.get('key', '')}: {f.get('value', '')}"
                for f in state["extracted_facts"]
                if isinstance(f, dict)
            ]
            if facts:
                context_parts.append(
                    "## Datos clínicos recopilados\n" + "\n".join(facts)
                )

        # Specialist analyses
        specialist_outputs = state.get("specialist_outputs") or {}
        specialties_involved = []

        if specialist_outputs:
            context_parts.append("## Análisis de especialistas")
            for specialty, output in specialist_outputs.items():
                specialties_involved.append(specialty)
                if isinstance(output, dict):
                    impression = output.get("clinical_impression", "")
                    recommendations = output.get("recommendations", [])
                    alarm_signs = output.get("alarm_signs", [])
                    differential = output.get("differential_diagnosis", [])

                    specialist_text = f"### {specialty}\n"
                    if impression:
                        specialist_text += f"Impresión: {impression}\n"
                    if differential:
                        specialist_text += "Diferenciales: " + ", ".join(
                            d.get("condition", "") if isinstance(d, dict) else str(d)
                            for d in differential[:3]
                        ) + "\n"
                    if recommendations:
                        specialist_text += "Recomendaciones: " + "; ".join(recommendations[:3]) + "\n"
                    if alarm_signs:
                        specialist_text += "Alarmas: " + "; ".join(alarm_signs) + "\n"
                    context_parts.append(specialist_text)
                else:
                    context_parts.append(f"### {specialty}\n{output}")

        # Medical board result
        medical_board = state.get("medical_board_result")
        if medical_board:
            if isinstance(medical_board, dict):
                board_text = (
                    f"## Panel Médico\n"
                    f"Consenso: {medical_board.get('consensus_level', 'unknown')}\n"
                    f"Resumen: {medical_board.get('moderator_summary', '')}\n"
                )
                if medical_board.get("key_agreements"):
                    board_text += "Acuerdos: " + "; ".join(medical_board["key_agreements"]) + "\n"
                if medical_board.get("key_disagreements"):
                    board_text += "Desacuerdos: " + "; ".join(medical_board["key_disagreements"]) + "\n"
                context_parts.append(board_text)

        # 2. Build messages
        full_context = "\n\n".join(context_parts)
        messages = [
            {"role": "system", "content": SYNTHESIZER_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    "Sintetizá toda la información clínica disponible en una respuesta "
                    "clara y accionable para el paciente:\n\n"
                    f"{full_context}"
                ),
            },
        ]

        # 3. Generate synthesized response
        result: SynthesizedResponse = await safe_ainvoke(
            self.llm,
            messages,
            fallback=_SYNTHESIZER_FALLBACK,
            agent_name="synthesizer",
        )

        # Merge specialties from state if not populated by LLM
        if not result.specialties_involved and specialties_involved:
            result.specialties_involved = specialties_involved

        # Clamp attention_level by triage ceiling — defends against the LLM
        # over-escalating yellow/green cases due to the "más conservador"
        # rule in the synthesizer prompt. Surfaced by clinical eval (commit
        # 5f2a716): cardio-002 + gyneco-001 yellow→urgencia via guardrail.
        clamped_attention = _clamp_attention(triage_level, result.attention_level)

        # Free users with gated specialist analysis get an upgrade hint
        # appended between the body and the disclaimer.
        upgrade_hint = (
            TIER_UPGRADE_HINT if state.get("tier_gated_specialists") else None
        )

        return {
            "synthesized_response": _compose_patient_text(
                result.patient_response,
                result.disclaimer,
                upgrade_hint=upgrade_hint,
            ),
            "attention_level": clamped_attention,
            "current_node": "synthesizer",
        }
