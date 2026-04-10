"""
BaseSpecialistAgent — Template for ALL specialist agents.

Each specialist subclass only needs to define:
- specialty_name (class var)
- system_prompt (property)
"""

from abc import ABC, abstractmethod

from langchain_openai import ChatOpenAI

from app.orchestrator.graph import ClinicalCaseState
from app.agents.specialists.schemas import SpecialistAnalysis


class BaseSpecialistAgent(ABC):
    """Base class for all specialist agents."""

    specialty_name: str = ""
    default_model: str = "gpt-4o"
    default_temperature: float = 0.3

    def __init__(self, api_key: str, model: str | None = None):
        self.llm = ChatOpenAI(
            model=model or self.default_model,
            temperature=self.default_temperature,
            api_key=api_key,
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

        return "\n".join(parts)

    async def __call__(self, state: ClinicalCaseState) -> dict:
        """Execute specialist analysis and merge into specialist_outputs."""
        context = self._build_context(state)

        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": context},
        ]

        result: SpecialistAnalysis = await self.llm.ainvoke(messages)

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
