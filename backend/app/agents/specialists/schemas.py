"""
Specialist Agents — Shared output schemas.

SpecialistAnalysis is used by ALL specialist agents.
DiagnosisHypothesis represents a single differential diagnosis entry.
"""

from pydantic import BaseModel, Field
from typing import Literal


class DiagnosisHypothesis(BaseModel):
    condition: str = Field(description="Condición o diagnóstico diferencial")
    probability: Literal["alta", "media", "baja"] = Field(description="Probabilidad estimada")
    supporting_evidence: list[str] = Field(default_factory=list, description="Evidencia que soporta esta hipótesis")
    against_evidence: list[str] = Field(default_factory=list, description="Evidencia en contra")


class SpecialistAnalysis(BaseModel):
    """Output compartido por todos los agentes especialistas."""

    specialty_name: str = Field(description="Nombre de la especialidad")
    clinical_impression: str = Field(description="Impresión clínica desde esta especialidad")
    differential_diagnosis: list[DiagnosisHypothesis] = Field(
        description="Diagnósticos diferenciales ordenados por probabilidad"
    )
    suggested_studies: list[str] = Field(
        default_factory=list,
        description="Estudios o exámenes sugeridos",
    )
    risk_factors: list[str] = Field(
        default_factory=list,
        description="Factores de riesgo identificados",
    )
    recommendations: list[str] = Field(
        default_factory=list,
        description="Recomendaciones generales",
    )
    alarm_signs: list[str] = Field(
        default_factory=list,
        description="Signos de alarma a vigilar",
    )
    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="Confianza en el análisis (0.0 a 1.0)",
    )
    needs_referral: bool = Field(
        default=False,
        description="¿Requiere derivación a otra especialidad?",
    )
    referral_to: list[str] = Field(
        default_factory=list,
        description="Especialidades a las que derivar",
    )
