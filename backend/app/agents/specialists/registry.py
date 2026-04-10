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

REGISTRY: dict[str, type] = {}


def register(cls: type) -> type:
    """Decorator — registra un agente especialista por specialty_name."""
    REGISTRY[cls.specialty_name] = cls
    return cls


def get_specialist(name: str, api_key: str) -> object | None:
    """Instancia y retorna un especialista por nombre. None si no existe."""
    cls = REGISTRY.get(name)
    if cls is None:
        return None
    return cls(api_key=api_key)


def get_available_specialties() -> list[str]:
    """Lista todos los nombres de especialidades registradas."""
    return list(REGISTRY.keys())
