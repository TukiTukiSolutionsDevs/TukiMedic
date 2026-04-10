"""Integration tests for document_processor — OCR + classify + extract pipeline."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.document_processor import process_document


FAKE_API_KEY = "sk-test-fake"
FAKE_DOC_ID = str(uuid.uuid4())
FAKE_USER_ID = uuid.uuid4()
FAKE_FILE = b"%PDF fake content"
FAKE_MIME = "application/pdf"


def _make_db_mock(doc):
    """Build an AsyncSession mock that returns `doc` from execute().scalar_one()."""
    db = AsyncMock()
    result = MagicMock()
    result.scalar_one.return_value = doc
    db.execute = AsyncMock(return_value=result)
    db.flush = AsyncMock()
    db.add = MagicMock()
    db.commit = AsyncMock()
    return db


def _make_doc():
    doc = MagicMock()
    doc.id = uuid.UUID(FAKE_DOC_ID)
    doc.user_id = FAKE_USER_ID
    doc.processing_status = "pending"
    doc.doc_type = None
    doc.doc_type_confidence = None
    doc.ocr_text = None
    doc.ocr_engine = None
    return doc


# ---------------------------------------------------------------------------
# T1 — OCR + classification both run, status ends as "done"
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_process_document_ocr_classify():
    """OCR runs, classification runs, doc.doc_type and status=done are set."""
    from app.services.document_classifier import DocumentClassification

    doc = _make_doc()
    db = _make_db_mock(doc)

    ocr_output = {"text": "Hemoglobina: 14.5 g/dL", "engine": "tesseract"}
    classification = DocumentClassification(
        doc_type="medical_report", confidence=0.80, reasoning="Report text"
    )

    with (
        patch("app.services.document_processor.ocr_document", AsyncMock(return_value=ocr_output)),
        patch("app.services.document_processor.classify_document", AsyncMock(return_value=classification)),
        patch("app.services.document_processor.extract_lab_values", AsyncMock(return_value=[])),
    ):
        await process_document(db, FAKE_DOC_ID, FAKE_FILE, FAKE_MIME, FAKE_API_KEY)

    assert doc.processing_status == "done"
    assert doc.doc_type == "medical_report"
    assert doc.doc_type_confidence == 0.80
    assert doc.ocr_text == "Hemoglobina: 14.5 g/dL"


# ---------------------------------------------------------------------------
# T2 — lab_result type → extract_lab_values is called and labs are saved
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_process_document_lab_extraction():
    """doc_type=lab_result → extract_lab_values is called and LabValueModel rows added."""
    from app.services.document_classifier import DocumentClassification
    from app.services.lab_extractor import ExtractedLabValue

    doc = _make_doc()
    db = _make_db_mock(doc)

    ocr_output = {"text": "Glucosa: 115 mg/dL Ref: 70-100 HIGH", "engine": "tesseract"}
    classification = DocumentClassification(
        doc_type="lab_result", confidence=0.95, reasoning="Lab values present"
    )
    lab_values = [
        ExtractedLabValue(
            test_name="Glucosa", value="115", unit="mg/dL",
            reference_range="70-100", flag="high"
        )
    ]

    with (
        patch("app.services.document_processor.ocr_document", AsyncMock(return_value=ocr_output)),
        patch("app.services.document_processor.classify_document", AsyncMock(return_value=classification)),
        patch("app.services.document_processor.extract_lab_values", AsyncMock(return_value=lab_values)),
    ):
        await process_document(db, FAKE_DOC_ID, FAKE_FILE, FAKE_MIME, FAKE_API_KEY)

    assert doc.processing_status == "done"
    assert doc.doc_type == "lab_result"
    # db.add should have been called once for the LabValueModel row
    db.add.assert_called_once()


# ---------------------------------------------------------------------------
# T3 — non-lab doc_type → extract_lab_values is NOT called
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_process_document_non_lab_skips_extraction():
    """doc_type != lab_result → extract_lab_values is never invoked."""
    from app.services.document_classifier import DocumentClassification

    doc = _make_doc()
    db = _make_db_mock(doc)

    ocr_output = {"text": "Receta médica Amoxicilina 500mg", "engine": "tesseract"}
    classification = DocumentClassification(
        doc_type="prescription", confidence=0.88, reasoning="Prescription text"
    )

    mock_extract = AsyncMock(return_value=[])

    with (
        patch("app.services.document_processor.ocr_document", AsyncMock(return_value=ocr_output)),
        patch("app.services.document_processor.classify_document", AsyncMock(return_value=classification)),
        patch("app.services.document_processor.extract_lab_values", mock_extract),
    ):
        await process_document(db, FAKE_DOC_ID, FAKE_FILE, FAKE_MIME, FAKE_API_KEY)

    mock_extract.assert_not_called()
    db.add.assert_not_called()
    assert doc.processing_status == "done"


# ---------------------------------------------------------------------------
# T4 — unhandled exception → status set to "failed"
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_process_document_error_sets_failed():
    """Any exception during processing → doc.processing_status='failed' and error saved."""
    doc = _make_doc()
    db = _make_db_mock(doc)

    with patch(
        "app.services.document_processor.ocr_document",
        AsyncMock(side_effect=RuntimeError("OCR service unavailable")),
    ):
        await process_document(db, FAKE_DOC_ID, FAKE_FILE, FAKE_MIME, FAKE_API_KEY)

    assert doc.processing_status == "failed"
    assert "OCR service unavailable" in doc.error_message
    db.commit.assert_called_once()
