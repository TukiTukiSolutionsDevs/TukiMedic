"""Tests for document_context service — Phase 2.5 (chat integration)."""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.document_context import (
    get_document_context,
    message_references_documents,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_doc(
    user_id,
    doc_type="lab_result",
    ocr_text="texto OCR del documento",
    filename="test.pdf",
):
    doc = MagicMock()
    doc.id = uuid.uuid4()
    doc.user_id = uuid.UUID(user_id) if isinstance(user_id, str) else user_id
    doc.doc_type = doc_type
    doc.original_filename = filename
    doc.ocr_text = ocr_text
    doc.processing_status = "done"
    return doc


def _make_lab_value(
    document_id,
    test_name="Glucosa",
    value="95",
    unit="mg/dL",
    reference_range="70-100",
    flag="normal",
):
    lv = MagicMock()
    lv.document_id = document_id
    lv.test_name = test_name
    lv.value = value
    lv.unit = unit
    lv.reference_range = reference_range
    lv.flag = flag
    return lv


def _make_db(*execute_results):
    """Create a mock AsyncSession where execute() returns the given results in order."""
    db = MagicMock()
    db.execute = AsyncMock(side_effect=list(execute_results))
    return db


def _scalars_result(items):
    result = MagicMock()
    result.scalars.return_value.all.return_value = list(items)
    return result


# ---------------------------------------------------------------------------
# message_references_documents
# ---------------------------------------------------------------------------

def test_message_references_documents_true():
    """Message containing doc keywords → True."""
    assert message_references_documents("mis resultados de laboratorio") is True


def test_message_references_documents_false():
    """Generic symptom message with no doc keywords → False."""
    assert message_references_documents("me duele la cabeza") is False


def test_message_references_documents_multiple_keywords():
    """Any matching keyword is enough."""
    assert message_references_documents("tengo un análisis y también una receta") is True


def test_message_references_documents_case_insensitive():
    """Keyword matching is case-insensitive (lowercased before compare)."""
    assert message_references_documents("Tengo un ANÁLISIS pendiente") is True


def test_message_references_documents_keyword_rx():
    """Short keyword 'rx' (radiografía) is recognized."""
    assert message_references_documents("me hice una rx de tórax") is True


# ---------------------------------------------------------------------------
# get_document_context
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_document_context_returns_docs():
    """Returns document summaries for the given user."""
    user_id = str(uuid.uuid4())
    doc = _make_doc(user_id, doc_type="lab_result", filename="sangre.pdf")

    docs_result = _scalars_result([doc])
    lv_result = _scalars_result([])  # no lab values for this doc

    db = _make_db(docs_result, lv_result)
    result = await get_document_context(db, user_id)

    assert len(result["documents"]) == 1
    summary = result["documents"][0]
    assert summary["doc_type"] == "lab_result"
    assert summary["filename"] == "sangre.pdf"
    assert "ocr_preview" in summary


@pytest.mark.asyncio
async def test_get_document_context_returns_lab_values():
    """Returns structured lab values extracted from documents."""
    user_id = str(uuid.uuid4())
    doc = _make_doc(user_id)
    lv = _make_lab_value(doc.id, test_name="Glucosa", value="95", unit="mg/dL", flag="normal")

    docs_result = _scalars_result([doc])
    lv_result = _scalars_result([lv])

    db = _make_db(docs_result, lv_result)
    result = await get_document_context(db, user_id)

    assert len(result["lab_values"]) == 1
    lab = result["lab_values"][0]
    assert lab["test_name"] == "Glucosa"
    assert lab["value"] == "95"
    assert lab["unit"] == "mg/dL"
    assert lab["flag"] == "normal"
    assert lab["reference_range"] == "70-100"


@pytest.mark.asyncio
async def test_get_document_context_empty():
    """No docs for user → empty lists (no crash)."""
    user_id = str(uuid.uuid4())

    docs_result = _scalars_result([])
    db = _make_db(docs_result)

    result = await get_document_context(db, user_id)

    assert result["documents"] == []
    assert result["lab_values"] == []


@pytest.mark.asyncio
async def test_get_document_context_filters_by_user():
    """db.execute is called exactly once for the docs query (user filter applied)."""
    user_id = str(uuid.uuid4())

    docs_result = _scalars_result([])
    db = _make_db(docs_result)

    await get_document_context(db, user_id)

    # One call for docs (no lab value calls because docs list is empty)
    db.execute.assert_called_once()


@pytest.mark.asyncio
async def test_get_document_context_ocr_preview_truncated():
    """OCR text longer than 500 chars is truncated in the preview."""
    user_id = str(uuid.uuid4())
    long_ocr = "x" * 1000
    doc = _make_doc(user_id, ocr_text=long_ocr)

    docs_result = _scalars_result([doc])
    lv_result = _scalars_result([])

    db = _make_db(docs_result, lv_result)
    result = await get_document_context(db, user_id)

    assert len(result["documents"][0]["ocr_preview"]) == 500


@pytest.mark.asyncio
async def test_get_document_context_multiple_docs_accumulate_lab_values():
    """Lab values from multiple docs are all returned in a flat list."""
    user_id = str(uuid.uuid4())
    doc1 = _make_doc(user_id, filename="doc1.pdf")
    doc2 = _make_doc(user_id, filename="doc2.pdf")

    lv1 = _make_lab_value(doc1.id, test_name="Hemoglobina", value="13.2")
    lv2 = _make_lab_value(doc2.id, test_name="Colesterol", value="180")

    docs_result = _scalars_result([doc1, doc2])
    lv_result1 = _scalars_result([lv1])
    lv_result2 = _scalars_result([lv2])

    db = _make_db(docs_result, lv_result1, lv_result2)
    result = await get_document_context(db, user_id)

    assert len(result["documents"]) == 2
    assert len(result["lab_values"]) == 2
    test_names = {lv["test_name"] for lv in result["lab_values"]}
    assert test_names == {"Hemoglobina", "Colesterol"}


@pytest.mark.asyncio
async def test_get_document_context_with_case_id():
    """Passing case_id doesn't crash; function accepts it as optional filter."""
    user_id = str(uuid.uuid4())
    case_id = str(uuid.uuid4())

    docs_result = _scalars_result([])
    db = _make_db(docs_result)

    # Should not raise
    result = await get_document_context(db, user_id, case_id=case_id)
    assert "documents" in result
    assert "lab_values" in result
