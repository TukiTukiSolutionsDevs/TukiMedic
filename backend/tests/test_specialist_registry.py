"""
Tests for Specialist Registry — registry.py

Tests TDD (RED first):
1. test_registry_has_general_medicine
2. test_registry_has_all_specialties
3. test_get_specialist_returns_agent
4. test_get_specialist_unknown_returns_none
5. test_get_available_specialties
"""

import pytest

# Import __init__ to trigger all @register decorators
import app.agents.specialists  # noqa: F401


class TestSpecialistRegistry:
    def test_registry_has_general_medicine(self):
        """GeneralMedicineAgent auto-registers via @register decorator."""
        from app.agents.specialists.registry import REGISTRY
        assert "medicina_general" in REGISTRY

    def test_registry_has_all_specialties(self):
        """All 5 specialists must be registered after importing __init__."""
        from app.agents.specialists.registry import REGISTRY
        expected = {
            "medicina_general",
            "medicina_interna",
            "pediatria",
            "ginecologia",
            "farmacologia",
        }
        assert expected.issubset(set(REGISTRY.keys()))

    def test_get_specialist_returns_agent(self):
        """Valid specialty name returns an instantiated agent."""
        from app.agents.specialists.registry import get_specialist
        agent = get_specialist("medicina_general", api_key="test-key")
        assert agent is not None

    def test_get_specialist_unknown_returns_none(self):
        """Unknown specialty name returns None without raising."""
        from app.agents.specialists.registry import get_specialist
        agent = get_specialist("especialidad_inexistente", api_key="test-key")
        assert agent is None

    def test_get_available_specialties(self):
        """get_available_specialties returns a list with all registered names."""
        from app.agents.specialists.registry import get_available_specialties
        specialties = get_available_specialties()
        assert isinstance(specialties, list)
        assert len(specialties) >= 5
        assert "medicina_general" in specialties
        assert "medicina_interna" in specialties
        assert "pediatria" in specialties
        assert "ginecologia" in specialties
        assert "farmacologia" in specialties

    def test_register_decorator_returns_class_unchanged(self):
        """@register returns the class itself (identity), not a wrapper."""
        from app.agents.specialists.registry import register, REGISTRY
        from app.agents.specialists.base import BaseSpecialistAgent

        class _TestAgent(BaseSpecialistAgent):
            specialty_name = "_test_decorator_agent"

            def __init__(self):
                # Skip LLM init
                pass

            @property
            def system_prompt(self) -> str:
                return "test"

        result = register(_TestAgent)
        assert result is _TestAgent
        assert "_test_decorator_agent" in REGISTRY

        # cleanup
        del REGISTRY["_test_decorator_agent"]
