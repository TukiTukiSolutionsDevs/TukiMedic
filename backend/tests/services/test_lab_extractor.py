"""Tests for lab_extractor service — ALL mocked, no real LLM calls."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.lab_extractor import ExtractedLabValue, LabExtractionResult, extract_lab_values

FAKE_API_KEY = "sk-test-fake-key"

LAB_TEXT = """
RESULTADO DE LABORATORIO
Hemoglobina: 14.5 g/dL  Ref: 13.5-17.5  Normal
Glucosa: 115 mg/dL  Ref: 70-100  HIGH
Creatinina: 0.9 mg/dL  Ref: 0.7-1.3  Normal
Plaquetas: 45000 /uL  Ref: 150000-400000  CRITICAL LOW
"""


def _make_mock_llm(extraction_result: LabExtractionResult):
    """Build a ChatOpenAI mock that returns the given result via structured output."""
    mock_instance = MagicMock()
    mock_structured = MagicMock()
    mock_structured.ainvoke = AsyncMock(return_value=extraction_result)
    mock_instance.with_structured_output.return_value = mock_structured
    return mock_instance


# ---------------------------------------------------------------------------
# T1 — successfully extracts multiple lab values
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_extract_lab_values_success():
    """Valid lab OCR text → returns list of ExtractedLabValue with correct count."""
    fake_values = [
        ExtractedLabValue(test_name="Hemoglobina", value="14.5", unit="g/dL",
                          reference_range="13.5-17.5", flag="normal"),
        ExtractedLabValue(test_name="Glucosa", value="115", unit="mg/dL",
                          reference_range="70-100", flag="high"),
    ]
    fake_result = LabExtractionResult(values=fake_values)

    with patch("app.services.lab_extractor.ChatOpenAI") as mock_llm_cls:
        mock_llm_cls.return_value = _make_mock_llm(fake_result)
        result = await extract_lab_values(LAB_TEXT, FAKE_API_KEY)

    assert len(result) == 2
    assert result[0].test_name == "Hemoglobina"
    assert result[1].test_name == "Glucosa"


# ---------------------------------------------------------------------------
# T2 — empty / short text → returns empty list (no LLM call)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_extract_empty_text():
    """Empty or short text → empty list returned, LLM never invoked."""
    with patch("app.services.lab_extractor.ChatOpenAI") as mock_llm_cls:
        result_empty = await extract_lab_values("", FAKE_API_KEY)
        result_short = await extract_lab_values("hi", FAKE_API_KEY)

    assert result_empty == []
    assert result_short == []
    mock_llm_cls.assert_not_called()


# ---------------------------------------------------------------------------
# T3 — result items are ExtractedLabValue instances
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_extract_returns_structured():
    """Each item in the result is an ExtractedLabValue with expected fields."""
    fake_value = ExtractedLabValue(
        test_name="Creatinina", value="0.9", unit="mg/dL",
        reference_range="0.7-1.3", flag="normal"
    )
    fake_result = LabExtractionResult(values=[fake_value])

    with patch("app.services.lab_extractor.ChatOpenAI") as mock_llm_cls:
        mock_llm_cls.return_value = _make_mock_llm(fake_result)
        result = await extract_lab_values(LAB_TEXT, FAKE_API_KEY)

    assert len(result) == 1
    item = result[0]
    assert isinstance(item, ExtractedLabValue)
    assert item.test_name == "Creatinina"
    assert item.value == "0.9"
    assert item.unit == "mg/dL"
    assert item.reference_range == "0.7-1.3"
    assert item.flag == "normal"


# ---------------------------------------------------------------------------
# T4 — values with various flags (high, low, critical, normal)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_extract_with_flags():
    """Extracted values have the correct flag values from LLM response."""
    fake_values = [
        ExtractedLabValue(test_name="Glucosa", value="115", unit="mg/dL",
                          reference_range="70-100", flag="high"),
        ExtractedLabValue(test_name="Plaquetas", value="45000", unit="/uL",
                          reference_range="150000-400000", flag="critical"),
        ExtractedLabValue(test_name="Hemoglobina", value="14.5", unit="g/dL",
                          reference_range="13.5-17.5", flag="normal"),
    ]
    fake_result = LabExtractionResult(values=fake_values)

    with patch("app.services.lab_extractor.ChatOpenAI") as mock_llm_cls:
        mock_llm_cls.return_value = _make_mock_llm(fake_result)
        result = await extract_lab_values(LAB_TEXT, FAKE_API_KEY)

    flags = [v.flag for v in result]
    assert "high" in flags
    assert "critical" in flags
    assert "normal" in flags


# ---------------------------------------------------------------------------
# T5 — text > 3000 chars is truncated before being sent to LLM
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_extract_truncates_long_text():
    """Text longer than 3000 chars → prompt only contains first 3000 chars."""
    long_text = "B" * 4000
    fake_result = LabExtractionResult(values=[])
    captured_prompt = []

    async def capture_ainvoke(prompt):
        captured_prompt.append(prompt)
        return fake_result

    with patch("app.services.lab_extractor.ChatOpenAI") as mock_llm_cls:
        mock_instance = MagicMock()
        mock_structured = MagicMock()
        mock_structured.ainvoke = capture_ainvoke
        mock_instance.with_structured_output.return_value = mock_structured
        mock_llm_cls.return_value = mock_instance

        await extract_lab_values(long_text, FAKE_API_KEY)

    assert "B" * 3001 not in captured_prompt[0]
    assert "B" * 3000 in captured_prompt[0]
