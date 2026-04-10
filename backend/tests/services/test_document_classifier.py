"""Tests for document_classifier service — Phase 2.3."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.document_classifier import DocumentClassification, classify_document


@pytest.mark.asyncio
async def test_classify_lab_result():
    """OCR text with lab values → classified as lab_result."""
    ocr_text = "Hemograma completo\nGlóbulos rojos: 4.5 M/uL\nHemoglobina: 13.2 g/dL"

    expected = DocumentClassification(
        doc_type="lab_result", confidence=0.95, reasoning="Contains lab values"
    )
    mock_llm = MagicMock()
    mock_structured = MagicMock()
    mock_structured.ainvoke = AsyncMock(return_value=expected)
    mock_llm.with_structured_output = MagicMock(return_value=mock_structured)

    with patch("app.services.document_classifier.ChatOpenAI", return_value=mock_llm):
        result = await classify_document(ocr_text, "fake-key")

    assert result.doc_type == "lab_result"
    assert result.confidence == 0.95


@pytest.mark.asyncio
async def test_classify_prescription():
    """Prescription OCR text → classified as prescription."""
    ocr_text = "Receta médica\nAmoxicilina 500mg — 3 veces por día\nDr. García"

    expected = DocumentClassification(
        doc_type="prescription", confidence=0.90, reasoning="Contains prescription details"
    )
    mock_llm = MagicMock()
    mock_structured = MagicMock()
    mock_structured.ainvoke = AsyncMock(return_value=expected)
    mock_llm.with_structured_output = MagicMock(return_value=mock_structured)

    with patch("app.services.document_classifier.ChatOpenAI", return_value=mock_llm):
        result = await classify_document(ocr_text, "fake-key")

    assert result.doc_type == "prescription"
    assert result.confidence > 0


@pytest.mark.asyncio
async def test_classify_empty_text():
    """Empty or very short text → unknown with 0 confidence, no LLM call."""
    with patch("app.services.document_classifier.ChatOpenAI") as mock_cls:
        result_empty = await classify_document("", "fake-key")
        result_short = await classify_document("hi", "fake-key")

    assert result_empty.doc_type == "unknown"
    assert result_empty.confidence == 0.0
    assert result_short.doc_type == "unknown"
    assert result_short.confidence == 0.0
    mock_cls.assert_not_called()


@pytest.mark.asyncio
async def test_classify_uses_structured_output():
    """with_structured_output is called with DocumentClassification schema."""
    ocr_text = "Análisis de sangre completo — glucosa 95 mg/dL"

    mock_llm = MagicMock()
    mock_structured = MagicMock()
    mock_structured.ainvoke = AsyncMock(
        return_value=DocumentClassification(
            doc_type="lab_result", confidence=0.88, reasoning="Lab values present"
        )
    )
    mock_llm.with_structured_output = MagicMock(return_value=mock_structured)

    with patch("app.services.document_classifier.ChatOpenAI", return_value=mock_llm):
        await classify_document(ocr_text, "fake-key")

    mock_llm.with_structured_output.assert_called_once_with(DocumentClassification)


@pytest.mark.asyncio
async def test_classify_truncates_long_text():
    """Text > 2000 chars is truncated before being sent to LLM."""
    long_text = "x" * 5000
    captured_prompt: list[str] = []

    mock_llm = MagicMock()
    mock_structured = MagicMock()

    async def capture_ainvoke(prompt: str):
        captured_prompt.append(prompt)
        return DocumentClassification(doc_type="unknown", confidence=0.5, reasoning="test")

    mock_structured.ainvoke = capture_ainvoke
    mock_llm.with_structured_output = MagicMock(return_value=mock_structured)

    with patch("app.services.document_classifier.ChatOpenAI", return_value=mock_llm):
        await classify_document(long_text, "fake-key")

    assert len(captured_prompt) == 1
    assert "x" * 2001 not in captured_prompt[0]
    assert "x" * 2000 in captured_prompt[0]
