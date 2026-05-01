"""
Specialist Registry — registro central de agentes especialistas.

Uso:
    @register
    class MySpecialist(BaseSpecialistAgent):
        specialty_name = "mi_especialidad"
        ...

REGISTRY se puebla automáticamente al importar cada módulo especialista.
__init__.py importa todos los módulos para garantizar el registro.
"""

from __future__ import annotations

import unicodedata

REGISTRY: dict[str, type] = {}


def _normalize_specialty(name: str) -> str:
    """Normalize a specialty name for registry lookup.

    The classifier LLM produces names with capitals, accents, and spaces
    ("Medicina Interna", "Cardiología Pediátrica", "Medicina General/Familiar"),
    but registry keys are snake_case ASCII ("medicina_interna"). Without
    space/slash/hyphen normalization every multi-word specialty silently
    fell back to GeneralMedicineAgent — neutralizing the entire specialist
    routing layer.

    Applies in order:
      1. strip + lowercase
      2. replace " ", "/", "-" with "_"
      3. NFD decompose + drop combining marks (accents)
      4. collapse repeated "_"
      5. strip leading/trailing "_"

    Examples:
        "Ginecología"                    → "ginecologia"
        "Medicina Interna"               → "medicina_interna"
        "Cardiología Pediátrica"         → "cardiologia_pediatrica"
        "Medicina General/Familiar"      → "medicina_general_familiar"
        "  Pediatría  "                  → "pediatria"
    """
    lowered = (
        name.strip()
        .lower()
        .replace(" ", "_")
        .replace("/", "_")
        .replace("-", "_")
    )
    nfd = unicodedata.normalize("NFD", lowered)
    cleaned = "".join(c for c in nfd if unicodedata.category(c) != "Mn")
    while "__" in cleaned:
        cleaned = cleaned.replace("__", "_")
    return cleaned.strip("_")


def register(cls: type) -> type:
    """Decorator — registra un agente especialista por specialty_name (normalizado)."""
    REGISTRY[_normalize_specialty(cls.specialty_name)] = cls
    return cls


def get_specialist(
    name: str,
    api_key: str | None = None,
    base_url: str | None = None,
    *,
    chat_model=None,
) -> object | None:
    """Instancia y retorna un especialista por nombre normalizado. None si no existe.

    Normalizes *name* before lookup so accented/capitalized variants from the
    classifier (e.g. "Ginecología") resolve correctly to the registry key
    "ginecologia".

    Prefer passing *chat_model* (pre-built ChatOpenAI from llm_router) so
    the specialist uses the provider-correct model tier. Falls back to the
    legacy api_key/base_url path for backward compatibility.
    """
    cls = REGISTRY.get(_normalize_specialty(name))
    if cls is None:
        return None
    if chat_model is not None:
        return cls(chat_model=chat_model)
    return cls(api_key=api_key, base_url=base_url)


def get_available_specialties() -> list[str]:
    """Lista todos los nombres de especialidades registradas."""
    return list(REGISTRY.keys())
