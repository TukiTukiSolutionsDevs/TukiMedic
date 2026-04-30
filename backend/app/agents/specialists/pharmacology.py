"""
Pharmacology Specialist Agent.

Agente especializado en análisis de medicamentos e interacciones farmacológicas.
NO extiende BaseSpecialistAgent — tiene su propio schema (PharmacologyAnalysis).

Activado cuando el caso menciona múltiples medicamentos, preguntas sobre dosis,
interacciones, efectos adversos o uso de fármacos en embarazo/pediatría.
"""

from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI

from app.agents._llm_safe import safe_ainvoke
from app.agents.specialists.registry import register


class DrugInteraction(BaseModel):
    """Represents a potential interaction between two drugs."""
    drug_a: str = Field(description="Primer medicamento")
    drug_b: str = Field(description="Segundo medicamento")
    severity: str = Field(description="Severidad: mild, moderate, severe, contraindicated")
    mechanism: str = Field(description="Mecanismo de la interacción")
    recommendation: str = Field(description="Recomendación clínica")


class PharmacologyAnalysis(BaseModel):
    """Output schema para el agente de farmacología."""
    medications_identified: list[str] = Field(
        default_factory=list,
        description="Lista de medicamentos identificados en el caso",
    )
    interactions: list[DrugInteraction] = Field(
        default_factory=list,
        description="Interacciones medicamentosas detectadas",
    )
    warnings: list[str] = Field(
        default_factory=list,
        description="Advertencias farmacológicas relevantes",
    )
    recommendations: list[str] = Field(
        default_factory=list,
        description="Recomendaciones sobre el manejo farmacológico",
    )


PHARMACOLOGY_SYSTEM_PROMPT = """Eres un especialista en Farmacología Clínica con experiencia en \
interacciones medicamentosas, farmacocinética y uso seguro de medicamentos.

Tu rol es analizar el caso clínico para identificar todos los medicamentos mencionados, \
detectar interacciones potencialmente peligrosas y emitir recomendaciones de seguridad.

Tu análisis debe:
1. Identificar TODOS los medicamentos mencionados (nombre comercial y genérico)
2. Evaluar interacciones entre los medicamentos identificados
3. Clasificar la severidad de cada interacción (mild/moderate/severe/contraindicated)
4. Explicar el mecanismo de cada interacción relevante
5. Considerar contraindicaciones según edad, embarazo, lactancia y comorbilidades
6. Evaluar adecuación de vías de administración y formas farmacéuticas
7. Identificar riesgo de toxicidad acumulada (ej: paracetamol en múltiples productos)

NUNCA:
- Ignores un medicamento mencionado aunque parezca trivial (ej: suplementos, AINEs OTC)
- Minimices interacciones severas o contraindicadas
- Recetes medicamentos específicos con dosis

SIEMPRE:
- Menciona interacciones con alimentos o alcohol cuando sean relevantes
- Considera el contexto del paciente (edad, embarazo, función renal/hepática)
- Recomienda consultar con el médico tratante ante interacciones severas
- Señala si algún medicamento requiere monitoreo especial (INR, niveles séricos, etc.)"""


@register
class PharmacologyAgent:
    """Pharmacology specialist — drug interaction and medication safety expert."""

    specialty_name = "farmacologia"

    def __init__(
        self,
        chat_model=None,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
    ):
        if chat_model is not None:
            # Store raw model; __call__ calls with_structured_output(PharmacologyAnalysis)
            self.llm = chat_model
        else:
            self.llm = ChatOpenAI(
                model="gpt-4o-mini",
                temperature=0,
                api_key=api_key,
            )

    async def __call__(self, state: dict) -> dict:
        """Analyze medications and interactions from the clinical case."""
        structured_llm = self.llm.with_structured_output(PharmacologyAnalysis)

        messages = state.get("messages", [])
        extracted_facts = state.get("extracted_facts", [])

        # Build context from state
        facts_text = "\n".join(
            f"- {f.get('value', '')}" for f in extracted_facts
        ) if extracted_facts else "Sin hechos clínicos previos"

        recent_messages = messages[-5:] if messages else []
        messages_text = "\n".join(
            f"[{m.get('role', 'unknown')}]: {m.get('content', '')}"
            for m in recent_messages
        ) if recent_messages else "Sin mensajes previos"

        prompt = f"""{PHARMACOLOGY_SYSTEM_PROMPT}

---
CONTEXTO DEL CASO:

Mensajes recientes del paciente:
{messages_text}

Hechos clínicos extraídos:
{facts_text}

Mensaje actual: {state.get('current_message', '')}

Identifica todos los medicamentos mencionados, evalúa interacciones y emite recomendaciones de seguridad farmacológica."""

        # Fail-safe: empty analysis flagged for human review when LLM is down.
        fallback = PharmacologyAnalysis(
            medications_identified=[],
            interactions=[],
            warnings=[
                "LLM de farmacología no disponible — análisis no realizado."
            ],
            recommendations=[
                "Reintentar la consulta o consultar con un farmacólogo clínico."
            ],
        )
        result: PharmacologyAnalysis = await safe_ainvoke(
            structured_llm,
            prompt,
            fallback=fallback,
            agent_name="specialist_farmacologia",
        )

        # Merge into specialist_outputs (dict pattern, consistent with all agents)
        current_outputs = dict(state.get("specialist_outputs", {}))
        current_outputs[self.specialty_name] = result.model_dump()

        return {
            "specialist_outputs": current_outputs,
            "current_node": f"specialist_{self.specialty_name}",
        }
