"""
Guardrail Agent — Safety check schemas.

GuardrailCheck captures the result of a real-time safety review.
SafetyViolation represents a single detected safety issue.
"""

from pydantic import BaseModel, Field
from typing import Literal
from enum import Enum


class InterruptionLevel(str, Enum):
    OBSERVE = "observe"
    FLAG = "flag"
    MODIFY = "modify"
    INTERRUPT = "interrupt"


class SafetyViolation(BaseModel):
    violation_type: str = Field(description="Tipo de violación de seguridad")
    description: str = Field(description="Descripción de la violación")
    severity: Literal["low", "medium", "high", "critical"] = Field(description="Severidad")
    node_source: str = Field(default="", description="Nodo que generó la violación")


class GuardrailCheck(BaseModel):
    approved: bool = Field(description="¿El contenido es seguro?")
    violations: list[SafetyViolation] = Field(default_factory=list)
    interruption_level: InterruptionLevel = Field(default=InterruptionLevel.OBSERVE)
    modifications_suggested: list[str] = Field(default_factory=list)
    escalation_required: bool = Field(default=False)
    escalation_reason: str = Field(default="")
