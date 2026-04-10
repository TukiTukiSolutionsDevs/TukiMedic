"""
Classifier Agent — Tools.

Carga el mapa síntoma→especialidad desde specialty_map.yaml y provee
get_base_specialties() para obtener pesos base antes de pasar al LLM.
"""

from pathlib import Path
import yaml

_SPECIALTY_MAP_PATH = Path(__file__).parent.parent.parent.parent / "data" / "specialty_map.yaml"
_specialty_map: dict | None = None


def _load_specialty_map() -> dict:
    global _specialty_map
    if _specialty_map is None:
        with open(_SPECIALTY_MAP_PATH, "r", encoding="utf-8") as f:
            _specialty_map = yaml.safe_load(f)
    return _specialty_map


def get_base_specialties(symptoms: list[str]) -> dict[str, float]:
    """
    Dado una lista de síntomas (claves del YAML), retorna un dict
    {especialidad: peso_máximo} fusionando todos los síntomas detectados.
    """
    specialty_map = _load_specialty_map()
    merged: dict[str, float] = {}

    for symptom in symptoms:
        if symptom not in specialty_map:
            continue
        for specialty, weight in specialty_map[symptom].items():
            if specialty not in merged or weight > merged[specialty]:
                merged[specialty] = weight

    return merged


def format_specialty_hints(symptoms: list[str]) -> str:
    """Formatea las especialidades base como texto para inyectar al LLM."""
    base = get_base_specialties(symptoms)
    if not base:
        return "No se encontraron especialidades base para los síntomas detectados."

    sorted_specialties = sorted(base.items(), key=lambda x: x[1], reverse=True)
    lines = [f"- {name}: {weight:.1f}" for name, weight in sorted_specialties]
    return "Pesos base sugeridos por el mapa de síntomas:\n" + "\n".join(lines)
