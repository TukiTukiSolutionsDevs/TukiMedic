"""Document processing pipeline — OCR → classify → extract labs.

Phase 2.2: OCR
Phase 2.3: document classification via LLM
Phase 2.4: lab value extraction via LLM
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import DocumentModel, LabValueModel
from app.services.document_classifier import classify_document
from app.services.lab_extractor import extract_lab_values
from app.services.ocr import ocr_document


async def process_document(
    db: AsyncSession,
    document_id: str,
    file_data: bytes,
    mime_type: str,
    api_key: str,
) -> None:
    """Process an uploaded document: OCR → classify → extract labs (if applicable).

    Updates the document row in-place. Commits on success, marks failed on error.
    """
    result = await db.execute(
        select(DocumentModel).where(DocumentModel.id == document_id)
    )
    doc = result.scalar_one()
    doc.processing_status = "processing"
    await db.flush()

    try:
        # Step 1: OCR
        ocr_result = await ocr_document(file_data, mime_type)
        doc.ocr_text = ocr_result["text"]
        doc.ocr_engine = ocr_result["engine"]

        # Step 2: Classify
        classification = await classify_document(ocr_result["text"], api_key)
        doc.doc_type = classification.doc_type
        doc.doc_type_confidence = classification.confidence

        # Step 3: Extract lab values (only for lab result documents)
        if classification.doc_type == "lab_result":
            lab_values = await extract_lab_values(ocr_result["text"], api_key)
            for lv in lab_values:
                lab = LabValueModel(
                    document_id=doc.id,
                    user_id=doc.user_id,
                    test_name=lv.test_name,
                    value=lv.value,
                    unit=lv.unit,
                    reference_range=lv.reference_range,
                    flag=lv.flag,
                    raw_text=ocr_result["text"][:500],
                )
                db.add(lab)

        doc.processing_status = "done"
    except Exception as exc:  # noqa: BLE001
        doc.processing_status = "failed"
        doc.error_message = str(exc)

    await db.commit()


async def _process_document_bg(
    document_id: str, file_data: bytes, mime_type: str, api_key: str
) -> None:
    """Background-task wrapper — creates its own DB session (FastAPI BackgroundTasks runs
    after the response is sent, so the request-scoped session is already closed).
    """
    from app.core.database import async_session

    async with async_session() as db:
        await process_document(db, document_id, file_data, mime_type, api_key)
