"""
Classifier Agent — Schemas de salida estructurada.

Define SpecialtyScore y ClassificationResult para que el LLM
devuelva un conjunto ponderado de especialidades médicas.
"""

from pydantic import BaseModel, Field
from typing import Literal


class SpecialtyScore(BaseModel):
    name: str = Field(description="Nombre de la especialidad médica")
    weight: float = Field(ge=0.0, le=1.0, description="Peso/relevancia (0.0 a 1.0)")
    reason: str = Field(description="Por qué esta especialidad es relevante para el caso")


class ClassificationResult(BaseModel):
    specialties: list[SpecialtyScore] = Field(
        description="Especialidades médicas ponderadas, ordenadas por peso descendente"
    )
    primary_specialty: str = Field(
        description="Especialidad principal (la de mayor peso)"
    )
    reasoning: str = Field(
        description="Razonamiento clínico de la clasificación"
    )
    differential_considerations: list[str] = Field(
        default_factory=list,
        description="Diagnósticos diferenciales iniciales a considerar"
    )
