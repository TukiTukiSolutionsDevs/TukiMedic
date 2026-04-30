"""
BaseSpecialistAgent — Template for ALL specialist agents.

Each specialist subclass only needs to define:
- specialty_name (class var)
- system_prompt (property)
"""

from abc import ABC, abstractmethod

from langchain_openai import ChatOpenAI

from app.agents._llm_safe import safe_ainvoke
from app.orchestrator.state import ClinicalCaseState
from app.agents.specialists.schemas import SpecialistAnalysis


def _specialist_fallback(specialty_name: str) -> SpecialistAnalysis:
    """Build a fail-safe analysis when the specialist LLM is unavailable.

    Empty differentials + low confidence + needs_referral=True so the rest of
    the graph treats this specialist as inconclusive instead of authoritative.
    """
    return SpecialistAnalysis(
        specialty_name=specialty_name or "unknown",
        clinical_impression=(
            "LLM no disponible; no se pudo realizar el análisis del especialista."
        ),
        differential_diagnosis=[],
        suggested_studies=[],
        risk_factors=[],
        recommendations=[
            "Reintentar la consulta o derivar a evaluación clínica presencial."
        ],
        alarm_signs=[],
        confidence=0.0,
        needs_referral=True,
        referral_to=[],
    )


class BaseSpecialistAgent(ABC):
    """Base class for all specialist agents."""

    specialty_name: str = ""
    default_model: str = "gpt-4o"
    default_temperature: float = 0.3

    def __init__(self, api_key: str, model: str | None = None, base_url: str | None = None):
        self.llm = ChatOpenAI(
            model=model or self.default_model,
            temperature=self.default_temperature,
            api_key=api_key,
            base_url=base_url,
        ).with_structured_output(SpecialistAnalysis)

    def _build_context(self, state: ClinicalCaseState) -> str:
        """Build clinical context string from state."""
        parts = []
        parts.append(f"Motivo de consulta: {state['current_message']}")

        if state.get("extracted_facts"):
            facts = "\n".join(f"- {f.get('value', '')}" for f in state["extracted_facts"])
            parts.append(f"\nHechos clínicos:\n{facts}")

        if state.get("triage_level"):
            parts.append(f"\nNivel de triage: {state['triage_level']}")

        if state.get("red_flags"):
            flags = ", ".join(state["red_flags"])
            parts.append(f"\nRed flags: {flags}")

        # Level-3 memory: patient profile (allergies, medications, conditions)
        profile = state.get("patient_profile") or {}
        if profile:
            profile_lines = []
            if profile.get("allergies"):
                profile_lines.append(f"  - Alergias: {', '.join(profile['allergies'])}")
            if profile.get("active_medications"):
                profile_lines.append(f"  - Medicamentos activos: {', '.join(profile['active_medications'])}")
            if profile.get("chronic_conditions"):
                profile_lines.append(f"  - Condiciones crónicas: {', '.join(profile['chronic_conditions'])}")
            if profile.get("blood_type"):
                profile_lines.append(f"  - Grupo sanguíneo: {profile['blood_type']}")
            if profile.get("age"):
                profile_lines.append(f"  - Edad: {profile['age']}")
            if profile.get("sex"):
                profile_lines.append(f"  - Sexo: {profile['sex']}")
            if profile_lines:
                parts.append("\nPerfil del paciente:\n" + "\n".join(profile_lines))

        # Knowledge Base: relevant medical literature context
        kb_context = state.get("kb_context") or ""
        if kb_context:
            parts.append(f"\n## Contexto Médico Relevante (Knowledge Base)\n{kb_context}")

        return "\n".join(parts)

    async def __call__(self, state: ClinicalCaseState) -> dict:
        """Execute specialist analysis and merge into specialist_outputs."""
        context = self._build_context(state)

        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": context},
        ]

        result: SpecialistAnalysis = await safe_ainvoke(
            self.llm,
            messages,
            fallback=_specialist_fallback(self.specialty_name),
            agent_name=f"specialist_{self.specialty_name or 'unknown'}",
        )

        # Merge into specialist_outputs — do NOT overwrite other specialists
        current_outputs = dict(state.get("specialist_outputs", {}))
        current_outputs[self.specialty_name] = result.model_dump()

        return {
            "specialist_outputs": current_outputs,
            "current_node": f"specialist_{self.specialty_name}",
        }

    @property
    @abstractmethod
    def system_prompt(self) -> str:
        """Each specialist defines its own system prompt."""
        ...
