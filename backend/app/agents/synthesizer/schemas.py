"""
Synthesizer Agent — Output schemas.

SynthesizedResponse is the final consolidated patient-facing response.
"""

from pydantic import BaseModel, Field
from typing import Literal


class SynthesizedResponse(BaseModel):
    patient_response: str = Field(description="Texto para el paciente en lenguaje claro")
    clinical_summary: str = Field(description="Resumen técnico para logs/audit")
    specialties_involved: list[str] = Field(default_factory=list)
    attention_level: Literal["rutina", "24-48h", "hoy", "urgencia"] = Field(
        description="Nivel de atención recomendado"
    )
    follow_up_questions: list[str] = Field(
        default_factory=list, description="Preguntas de seguimiento opcionales"
    )
    alarm_signs: list[str] = Field(
        default_factory=list, description="Signos de alarma a vigilar"
    )
    disclaimer: str = Field(
        default="Esta orientación no reemplaza la consulta médica presencial.",
        description="Disclaimer obligatorio",
    )
