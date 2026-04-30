"""
Synthesizer Agent — Consolidates all agent outputs into one patient-facing response.

Takes triage, specialist analyses, and medical board result and produces a
single clear, empathetic, actionable response for the patient.
"""

import json

from langchain_openai import ChatOpenAI

from app.orchestrator.state import ClinicalCaseState
from app.agents.synthesizer.schemas import SynthesizedResponse
from app.agents.synthesizer.prompts import SYNTHESIZER_SYSTEM_PROMPT


# Base disclaimer always concatenated to the patient-facing response.
# Even when the LLM omits or returns an empty disclaimer, this MUST appear.
BASE_DISCLAIMER = (
    "MedAgent es una herramienta de orientación; "
    "no reemplaza la consulta médica profesional."
)
DISCLAIMER_SEPARATOR = "\n\n---\n\n"


def _compose_patient_text(patient_response: str, disclaimer: str | None) -> str:
    """Append disclaimer to the patient response with a visible separator.

    Falls back to BASE_DISCLAIMER if the LLM returned an empty or missing one.
    """
    body = (patient_response or "").strip()
    extra = (disclaimer or "").strip()
    if not extra:
        extra = BASE_DISCLAIMER
    if not body:
        return extra
    return f"{body}{DISCLAIMER_SEPARATOR}{extra}"


class SynthesizerAgent:
    """Agente sintetizador — nodo final del grafo de orquestación."""

    def __init__(self, api_key: str, model: str = "gpt-4o"):
        self.llm = ChatOpenAI(
            model=model,
            temperature=0.4,
            api_key=api_key,
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

        # Original message
        if state.get("current_message"):
            context_parts.append(
                f"## Consulta del paciente\n{state['current_message']}"
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
        result: SynthesizedResponse = await self.llm.ainvoke(messages)

        # Merge specialties from state if not populated by LLM
        if not result.specialties_involved and specialties_involved:
            result.specialties_involved = specialties_involved

        return {
            "synthesized_response": _compose_patient_text(
                result.patient_response, result.disclaimer
            ),
            "attention_level": result.attention_level,
            "current_node": "synthesizer",
        }
