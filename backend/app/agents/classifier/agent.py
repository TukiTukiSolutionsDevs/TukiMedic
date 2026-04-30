"""
Classifier Agent — Tercer nodo del grafo de orquestación MedAgent.

Determina qué especialidades médicas deben activarse para el caso,
produciendo una lista ponderada. Solo activa especialidades con peso >= 0.4.
Model: GPT-4o, Temperature: 0.2.
"""

from langchain_openai import ChatOpenAI

from app.agents._llm_safe import safe_ainvoke
from app.orchestrator.state import ClinicalCaseState
from app.agents.classifier.schemas import ClassificationResult
from app.agents.classifier.prompts import CLASSIFIER_SYSTEM_PROMPT
from app.agents.classifier.tools import format_specialty_hints

# Umbral mínimo para activar una especialidad
WEIGHT_THRESHOLD = 0.4

# Fail-safe: route to general medicine when LLM is unavailable. Generalist
# is the safest default — covers most cases without missing a specialty.
_CLASSIFIER_FALLBACK = ClassificationResult(
    specialties=[],
    primary_specialty="medicina_general",
    reasoning="LLM no disponible; derivando a medicina general por defecto.",
    differential_considerations=[],
)


class ClassifierAgent:
    """Agente clasificador de especialidades — nodo de LangGraph."""

    def __init__(self, api_key: str, model: str = "gpt-4o", base_url: str | None = None):
        self.llm = ChatOpenAI(
            model=model,
            temperature=0.2,
            api_key=api_key,
            base_url=base_url,
        ).with_structured_output(ClassificationResult)

    async def __call__(self, state: ClinicalCaseState) -> dict:
        """Execute classification and return partial state update."""
        messages = [
            {"role": "system", "content": CLASSIFIER_SYSTEM_PROMPT},
        ]

        # Inject extracted facts as clinical context
        existing_facts: list[dict] = state.get("extracted_facts") or []
        if existing_facts:
            facts_lines = "\n".join(
                f"- [{f.get('fact_type', 'unknown')}] {f.get('value', '')}"
                for f in existing_facts
            )
            messages.append({
                "role": "system",
                "content": (
                    "HECHOS CLÍNICOS RECOPILADOS (base para la clasificación):\n"
                    + facts_lines
                ),
            })

        # Inject specialty map hints based on known symptom keywords
        symptom_keywords = _extract_symptom_keywords(existing_facts, state["current_message"])
        if symptom_keywords:
            hints = format_specialty_hints(symptom_keywords)
            messages.append({
                "role": "system",
                "content": hints,
            })

        # Add current patient message
        messages.append({
            "role": "user",
            "content": state["current_message"],
        })

        result: ClassificationResult = await safe_ainvoke(
            self.llm,
            messages,
            fallback=_CLASSIFIER_FALLBACK,
            agent_name="classifier",
        )

        # Filter: only activate specialties above threshold
        active = [
            s.model_dump()
            for s in result.specialties
            if s.weight >= WEIGHT_THRESHOLD
        ]

        # Sort by weight descending
        active.sort(key=lambda x: x["weight"], reverse=True)

        return {
            "active_specialties": active,
            "primary_specialty": result.primary_specialty,
            "current_node": "classifier",
        }


def _extract_symptom_keywords(facts: list[dict], message: str) -> list[str]:
    """
    Heurística simple para mapear hechos/mensaje a claves del YAML.
    El LLM refina esto — este paso solo mejora el hint inicial.
    """
    text = " ".join(
        [f.get("value", "") for f in facts] + [message]
    ).lower()

    keyword_map = {
        "dolor abdominal": "dolor_abdominal",
        "dolor de panza": "dolor_abdominal",
        "fatiga": "fatiga_cronica",
        "cansancio": "fatiga_cronica",
        "cefalea": "cefalea",
        "dolor de cabeza": "cefalea",
        "dolor toracico": "dolor_toracico",
        "dolor en el pecho": "dolor_toracico",
        "pecho": "dolor_toracico",
        "piel": "problemas_piel",
        "erupcion": "problemas_piel",
        "articular": "dolor_articular",
        "articulacion": "dolor_articular",
        "rodilla": "dolor_articular",
        "ansiedad": "sintomas_emocionales",
        "depresion": "sintomas_emocionales",
        "tristeza": "sintomas_emocionales",
        "respirar": "sintomas_respiratorios",
        "tos": "sintomas_respiratorios",
        "disnea": "sintomas_respiratorios",
        "orina": "sintomas_urinarios",
        "urinario": "sintomas_urinarios",
        "menstrual": "sintomas_ginecologicos",
        "ginecologico": "sintomas_ginecologicos",
        "vaginal": "sintomas_ginecologicos",
        "embarazo": "sintomas_ginecologicos",
        "gestacion": "sintomas_ginecologicos",
        "niño": "sintomas_pediatricos",
        "bebe": "sintomas_pediatricos",
        "bebé": "sintomas_pediatricos",
        "infante": "sintomas_pediatricos",
        "lactante": "sintomas_pediatricos",
        "pediatr": "sintomas_pediatricos",
        "neonato": "fiebre_neonatal",
        "recien nacido": "fiebre_neonatal",
        "medicamento": "interaccion_medicamentos",
        "interaccion": "interaccion_medicamentos",
        "interacción": "interaccion_medicamentos",
        "farmaco": "interaccion_medicamentos",
        "fármaco": "interaccion_medicamentos",
        "pastilla": "interaccion_medicamentos",
        "dosis": "interaccion_medicamentos",
        "diabetes": "sintomas_metabolicos",
        "hipertension": "sintomas_metabolicos",
        "hipertensión": "sintomas_metabolicos",
        "colesterol": "sintomas_metabolicos",
        "tiroides": "sintomas_metabolicos",
        "cronica": "enfermedad_cronica",
        "crónica": "enfermedad_cronica",
        "fiebre semanas": "fiebre_prolongada",
        "fiebre dias": "fiebre_prolongada",
    }

    detected = set()
    for keyword, symptom_key in keyword_map.items():
        if keyword in text:
            detected.add(symptom_key)

    return list(detected)


def classification_router(state: ClinicalCaseState) -> str:
    """Route after classification — siempre despacha a specialists."""
    return "specialists"
