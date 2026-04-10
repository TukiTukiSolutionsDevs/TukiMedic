"""
Medical Board — Output schemas.

MedicalBoardResult captures the consensus evaluation after multi-round debate.
ChallengeResponse captures each specialist's reply to the Devil's Advocate.
"""

from pydantic import BaseModel, Field
from typing import Literal


class ChallengeResponse(BaseModel):
    specialist: str = Field(description="Especialista que responde")
    original_position: str = Field(description="Posición original")
    response_to_challenge: str = Field(description="Respuesta al desafío")
    position_changed: bool = Field(description="¿Cambió su posición?")
    adjusted_analysis: str = Field(
        default="",
        description="Análisis ajustado (si cambió)",
    )


class MedicalBoardResult(BaseModel):
    consensus_level: Literal["full", "partial", "disagreement"] = Field(
        description="Nivel de consenso alcanzado"
    )
    debate_rounds: int = Field(ge=1, description="Rondas de debate ejecutadas")
    key_agreements: list[str] = Field(
        default_factory=list,
        description="Puntos de consenso",
    )
    key_disagreements: list[str] = Field(
        default_factory=list,
        description="Puntos de desacuerdo",
    )
    resolution_path: Literal["synthesis", "extra_round", "clarification"] = Field(
        description="Siguiente paso recomendado"
    )
    moderator_summary: str = Field(description="Resumen del moderador")
    challenges_addressed: list[ChallengeResponse] = Field(
        default_factory=list,
        description="Respuestas a los desafíos del Devil's Advocate",
    )
