"""
Document context retriever — Phase 2.5 (chat integration).

Retrieves relevant document context for the current user/case to be injected
into ClinicalCaseState BEFORE the graph runs. No new LangGraph node is added.
This follows the same graceful-degradation pattern as L1/L2 memory in chat.py.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import DocumentModel, LabValueModel

# ---------------------------------------------------------------------------
# Keywords that suggest the user is referencing documents / lab results
# ---------------------------------------------------------------------------

DOC_KEYWORDS: frozenset[str] = frozenset({
    "laboratorio", "análisis", "resultados", "lab", "examen", "estudio",
    "placa", "rx", "ecografía", "receta", "documento", "archivo",
    "informe", "reporte", "hemograma", "análisis", "glucosa",
})


def message_references_documents(content: str) -> bool:
    """Return True if the user message references medical documents or labs.

    Uses a simple keyword intersection (word-boundary safe via split()).
    Case-insensitive. Intentionally cheap — no regex, no NLP.
    """
    words = set(content.lower().split())
    return bool(words & DOC_KEYWORDS)


async def get_document_context(
    db: AsyncSession,
    user_id: str,
    case_id: str | None = None,
) -> dict:
    """Retrieve document context for the current user (and optionally case).

    Returns a dict with:
      - documents: list of {doc_type, filename, ocr_preview}
      - lab_values: list of {test_name, value, unit, reference_range, flag}

    Limits to 5 most recent documents with processing_status == "done".
    OCR preview is truncated to 500 chars to keep state lean.
    """
    query = (
        select(DocumentModel)
        .where(
            DocumentModel.user_id == user_id,
            DocumentModel.processing_status == "done",
        )
        .order_by(DocumentModel.created_at.desc())
        .limit(5)
    )

    if case_id:
        query = query.where(DocumentModel.case_id == case_id)

    result = await db.execute(query)
    docs = result.scalars().all()

    doc_summaries: list[dict] = []
    all_lab_values: list[dict] = []

    for doc in docs:
        doc_summaries.append({
            "doc_type": doc.doc_type,
            "filename": doc.original_filename,
            "ocr_preview": (doc.ocr_text or "")[:500],
        })

        lv_result = await db.execute(
            select(LabValueModel).where(LabValueModel.document_id == doc.id)
        )
        for lv in lv_result.scalars().all():
            all_lab_values.append({
                "test_name": lv.test_name,
                "value": lv.value,
                "unit": lv.unit,
                "reference_range": lv.reference_range,
                "flag": lv.flag,
            })

    return {"documents": doc_summaries, "lab_values": all_lab_values}
