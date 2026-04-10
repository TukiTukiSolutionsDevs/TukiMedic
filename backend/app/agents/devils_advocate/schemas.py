"""
Devil's Advocate — Output schemas.

ChallengeResult contains all challenges issued against specialist conclusions.
Challenge represents a single targeted challenge to one specialist.
"""

from pydantic import BaseModel, Field


class Challenge(BaseModel):
    specialist: str = Field(description="Especialista desafiado")
    challenge: str = Field(description="El desafío clínico")
    alternative_hypothesis: str = Field(description="Hipótesis alternativa propuesta")
    unexamined_assumption: str = Field(
        default="",
        description="Suposición no examinada",
    )


class ChallengeResult(BaseModel):
    challenges_per_specialist: list[Challenge] = Field(
        description="Desafíos por especialista"
    )
    alternative_hypotheses: list[str] = Field(
        default_factory=list,
        description="Hipótesis alternativas globales",
    )
    unexamined_assumptions: list[str] = Field(
        default_factory=list,
        description="Suposiciones no examinadas",
    )
    false_consensus_risk: float = Field(
        ge=0.0,
        le=1.0,
        description="Riesgo de falso consenso (0.0 a 1.0)",
    )
    critical_questions: list[str] = Field(
        default_factory=list,
        description="Preguntas críticas no hechas",
    )
