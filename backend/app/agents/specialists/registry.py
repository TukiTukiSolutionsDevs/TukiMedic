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

# Alias map: normalized variant → canonical registry key.
#
# The classifier LLM emits multi-word specialty names that, after
# `_normalize_specialty`, do not match any registered agent. Rather than
# coercing the prompt to fix every variant, we route compatible siblings
# explicitly here. Lookup order in `get_specialist`:
#   1. Direct match in REGISTRY (canonical key).
#   2. ALIASES[name] → canonical key → REGISTRY.
#   3. None.
#
# Aliases are normalized via `_normalize_specialty` at lookup time, so
# entries should already be in canonical snake_case ASCII form (matching
# what the normalizer produces).
ALIASES: dict[str, str] = {
    # Traumatology umbrella: classifier emits "Traumatología y Ortopedia"
    # and "Medicina Deportiva" — both fold into the trauma agent until a
    # dedicated sport-medicine specialist is added.
    "traumatologia_y_ortopedia": "traumatologia",
    "ortopedia": "traumatologia",
    "medicina_deportiva": "traumatologia",
    # Family medicine sits inside general medicine for our purposes.
    "medicina_familiar": "medicina_general",
    "medicina_general_familiar": "medicina_general",
    "medicina_general_y_familiar": "medicina_general",
    # Obstetrics shares the gynecology agent.
    "obstetricia": "ginecologia",
    "ginecologia_y_obstetricia": "ginecologia",
    # Dermatology — short alias used by classifier / users.
    # The accented "Dermatología" already normalizes to "dermatologia"
    # via _normalize_specialty, so only the short form needs an alias entry.
    "derma": "dermatologia",
}


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

    Lookup order:
      1. Direct match: ``REGISTRY[_normalize_specialty(name)]``.
      2. Alias fallback: ``REGISTRY[ALIASES[_normalize_specialty(name)]]``.
      3. ``None`` (specialty not implemented).

    Normalizes *name* before lookup so accented/capitalized variants from the
    classifier (e.g. "Ginecología", "Traumatología y Ortopedia") resolve
    correctly to a canonical registry key.

    Prefer passing *chat_model* (pre-built ChatOpenAI from llm_router) so
    the specialist uses the provider-correct model tier. Falls back to the
    legacy api_key/base_url path for backward compatibility.
    """
    canonical = _normalize_specialty(name)
    cls = REGISTRY.get(canonical)
    if cls is None:
        # Try alias resolution before giving up.
        aliased = ALIASES.get(canonical)
        if aliased is not None:
            cls = REGISTRY.get(aliased)
    if cls is None:
        return None
    if chat_model is not None:
        return cls(chat_model=chat_model)
    return cls(api_key=api_key, base_url=base_url)


def get_available_specialties() -> list[str]:
    """Lista todos los nombres de especialidades registradas."""
    return list(REGISTRY.keys())
