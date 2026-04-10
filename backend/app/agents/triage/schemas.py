from pydantic import BaseModel, Field
from typing import Literal


class TriageResult(BaseModel):
    """Resultado del triage clínico."""
    level: Literal["green", "yellow", "red"] = Field(
        description="Nivel de urgencia: green (rutina), yellow (atención próxima), red (urgencia)"
    )
    confidence: float = Field(
        ge=0.0, le=1.0,
        description="Confianza en la clasificación (0.0 a 1.0)"
    )
    red_flags_detected: list[str] = Field(
        default_factory=list,
        description="Red flags clínicos detectados"
    )
    reasoning: str = Field(
        description="Explicación clínica de la clasificación"
    )
    recommended_urgency: Literal["rutina", "24-48h", "hoy", "inmediato"] = Field(
        description="Tiempo recomendado para buscar atención"
    )
