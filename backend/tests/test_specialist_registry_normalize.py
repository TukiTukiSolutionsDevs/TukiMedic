"""Unit tests for _normalize_specialty + alias resolution.

Closes the bug surfaced by the static audit (engram
tuki-medic/specialties-and-kb-plan): the classifier produces specialty
names like "Medicina Interna" or "Cardiología Pediátrica", but the
registry keys are snake_case ("medicina_interna"), and the previous
normalizer did NOT convert spaces to underscores. Result: every
multi-word specialty silently fell through to the GeneralMedicineAgent
fallback, neutralizing the entire specialist routing layer.

The new normalizer:
  - strip + lower
  - replace " ", "/", "-" with "_"
  - NFD decompose + drop combining marks (accents)
  - collapse repeated "_"
  - strip leading/trailing "_"

It also resolves a small alias table for common synonyms produced by
the classifier (e.g. "obstetricia" → "ginecologia").
"""

from unittest.mock import MagicMock

import pytest

from app.agents.specialists.registry import (
    REGISTRY,
    _normalize_specialty,
    get_specialist,
)


def _mock_chat_model():
    m = MagicMock()
    m.with_structured_output = MagicMock(return_value=m)
    return m


class TestNormalizeSpacesToUnderscores:
    def test_simple_space(self):
        assert _normalize_specialty("Medicina Interna") == "medicina_interna"

    def test_multiple_spaces_collapse(self):
        assert _normalize_specialty("Medicina  Interna   General") == "medicina_interna_general"

    def test_leading_trailing_whitespace(self):
        assert _normalize_specialty("  Pediatría  ") == "pediatria"

    def test_slash_to_underscore(self):
        assert _normalize_specialty("Medicina General/Familiar") == "medicina_general_familiar"

    def test_hyphen_to_underscore(self):
        assert _normalize_specialty("Cardio-vascular") == "cardio_vascular"

    def test_collapses_repeated_separators(self):
        # mixed " / " → multiple underscores → collapse
        assert _normalize_specialty("Cardio / Vascular") == "cardio_vascular"


class TestNormalizeAccents:
    def test_strips_acute(self):
        assert _normalize_specialty("Cardiología") == "cardiologia"

    def test_strips_acute_combined_with_space(self):
        assert _normalize_specialty("Cardiología Pediátrica") == "cardiologia_pediatrica"

    def test_strips_diaeresis(self):
        # "Otorrinolaringología" has a tilde; check a separate diaeresis case.
        assert _normalize_specialty("Pingüino") == "pinguino"


class TestPassthroughForAlreadyNormalized:
    @pytest.mark.parametrize("name", [
        "medicina_general",
        "medicina_interna",
        "pediatria",
        "ginecologia",
        "farmacologia",
    ])
    def test_already_canonical_unchanged(self, name):
        assert _normalize_specialty(name) == name


class TestRegistryLookupAfterFix:
    def test_classifier_output_resolves_for_medicina_interna(self):
        # Classifier emits "Medicina Interna"; registry has "medicina_interna".
        assert "medicina_interna" in REGISTRY
        agent = get_specialist("Medicina Interna", chat_model=_mock_chat_model())
        assert agent is not None
        assert type(agent).__name__ == "InternalMedicineAgent"

    def test_classifier_output_resolves_for_pediatria(self):
        agent = get_specialist("Pediatría", chat_model=_mock_chat_model())
        assert agent is not None
        assert type(agent).__name__ == "PediatricsAgent"

    def test_classifier_output_resolves_for_ginecologia(self):
        agent = get_specialist("Ginecología", chat_model=_mock_chat_model())
        assert agent is not None
        assert type(agent).__name__ == "GynecologyAgent"

    def test_unknown_specialty_returns_none(self):
        assert get_specialist("Inventología", chat_model=_mock_chat_model()) is None


class TestEdgeCases:
    def test_empty_string(self):
        assert _normalize_specialty("") == ""

    def test_only_separators(self):
        assert _normalize_specialty("   /  -  ") == ""

    def test_all_lowercase_no_op(self):
        assert _normalize_specialty("cardiologia") == "cardiologia"

    def test_all_uppercase(self):
        assert _normalize_specialty("CARDIOLOGIA") == "cardiologia"
