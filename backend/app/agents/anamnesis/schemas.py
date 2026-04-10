from pydantic import BaseModel, Field, field_validator
from typing import Literal


class ClinicalQuestion(BaseModel):
    """Pregunta clínica generada por el agente de anamnesis."""
    question: str = Field(
        description="Texto de la pregunta clínica a formular al paciente"
    )
    area: Literal["datos_basicos", "motivo_consulta", "antecedentes", "contexto"] = Field(
        description="Área clínica que indaga esta pregunta"
    )
    priority: Literal["alta", "media", "baja"] = Field(
        description="Prioridad clínica de esta pregunta"
    )
    rationale: str = Field(
        description="Justificación clínica de por qué se formula esta pregunta"
    )


class ClinicalFact(BaseModel):
    """Hecho clínico extraído de los mensajes del paciente."""
    fact_type: Literal[
        "symptom",
        "antecedent",
        "medication",
        "allergy",
        "vital_sign",
        "lifestyle",
        "context",
        "family_history",
    ] = Field(description="Tipo de hecho clínico")
    value: str = Field(description="Valor o descripción del hecho clínico")
    confidence: float = Field(
        ge=0.0, le=1.0,
        description="Confianza en la extracción de este hecho (0.0 a 1.0)"
    )


class AnamnesisResult(BaseModel):
    """Resultado del agente de anamnesis — preguntas y hechos extraídos."""
    questions: list[ClinicalQuestion] = Field(
        description="Preguntas clínicas formuladas (máximo 4 por turno)"
    )
    extracted_facts: list[ClinicalFact] = Field(
        default_factory=list,
        description="Hechos clínicos extraídos de los mensajes del paciente"
    )
    completeness_score: float = Field(
        ge=0.0, le=1.0,
        description="Qué tan completa está la anamnesis (0.0 = nada, 1.0 = completa)"
    )
    critical_gaps: list[str] = Field(
        default_factory=list,
        description="Información crítica que aún falta para completar la anamnesis"
    )

    @field_validator("questions")
    @classmethod
    def max_four_questions(cls, v: list[ClinicalQuestion]) -> list[ClinicalQuestion]:
        if len(v) > 4:
            raise ValueError("El agente de anamnesis no puede formular más de 4 preguntas por turno")
        return v
