"""
Anamnesis Agent — Segundo nodo del grafo de orquestación MedAgent.

Genera preguntas clínicas para recopilar información faltante del paciente.
NO responde al paciente — PREGUNTA. Temperature 0.3 para balance entre
consistencia clínica y naturalidad en el lenguaje.
"""

from langchain_openai import ChatOpenAI

from app.orchestrator.state import ClinicalCaseState
from app.agents.anamnesis.schemas import AnamnesisResult, ClinicalFact
from app.agents.anamnesis.prompts import ANAMNESIS_SYSTEM_PROMPT


class AnamnesisAgent:
    """Agente de anamnesis clínica — nodo de LangGraph."""

    def __init__(self, api_key: str, model: str = "gpt-4o"):
        self.llm = ChatOpenAI(
            model=model,
            temperature=0.3,
            api_key=api_key,
        ).with_structured_output(AnamnesisResult)

    async def __call__(self, state: ClinicalCaseState) -> dict:
        """Execute anamnesis and return partial state update."""
        messages = [
            {"role": "system", "content": ANAMNESIS_SYSTEM_PROMPT},
        ]

        # Inject existing facts as context so LLM doesn't repeat answered questions
        existing_facts: list[dict] = state.get("extracted_facts") or []
        if existing_facts:
            facts_lines = "\n".join(
                f"- [{f.get('fact_type', 'unknown')}] {f.get('value', '')}"
                for f in existing_facts
            )
            messages.append({
                "role": "system",
                "content": (
                    "HECHOS CLÍNICOS YA CONOCIDOS (no preguntes sobre estos):\n"
                    + facts_lines
                ),
            })

        # Inject pending questions so LLM knows what's already been asked
        pending: list[str] = state.get("pending_questions") or []
        if pending:
            pending_lines = "\n".join(f"- {q}" for q in pending)
            messages.append({
                "role": "system",
                "content": (
                    "PREGUNTAS YA FORMULADAS (no repetir):\n" + pending_lines
                ),
            })

        # Add conversation history
        for msg in state.get("messages") or []:
            messages.append(msg)

        # Add current patient message
        messages.append({
            "role": "user",
            "content": state["current_message"],
        })

        result: AnamnesisResult = await self.llm.ainvoke(messages)

        # Merge new facts with existing — never overwrite, only append non-duplicates
        merged_facts = list(existing_facts)
        existing_values = {f.get("value", "").lower() for f in existing_facts}

        for fact in result.extracted_facts:
            fact_dict = fact.model_dump()
            if fact_dict["value"].lower() not in existing_values:
                merged_facts.append(fact_dict)
                existing_values.add(fact_dict["value"].lower())

        # Build updated pending questions list
        new_questions = [q.question for q in result.questions]
        all_pending = list(pending) + [q for q in new_questions if q not in pending]

        return {
            "extracted_facts": merged_facts,
            "pending_questions": all_pending,
            "completeness_score": result.completeness_score,
            "current_node": "anamnesis",
        }
