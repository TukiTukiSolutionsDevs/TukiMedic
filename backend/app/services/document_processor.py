"""Document processing pipeline — orchestrates OCR → (future: classify → extract labs).

Phase 2.2: OCR only.
Phase 2.3: classification will be added here.
Phase 2.4: lab value extraction will be added here.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import DocumentModel
from app.services.ocr import ocr_document


async def process_document(
    db: AsyncSession, document_id: str, file_data: bytes, mime_type: str
) -> None:
    """Process an uploaded document: OCR → (future: classify → extract labs).

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

        # Steps 2–3 arrive in Phase 2.3 and 2.4

        doc.processing_status = "done"
    except Exception as exc:  # noqa: BLE001
        doc.processing_status = "failed"
        doc.error_message = str(exc)

    await db.commit()


async def _process_document_bg(
    document_id: str, file_data: bytes, mime_type: str
) -> None:
    """Background-task wrapper — creates its own DB session (FastAPI BackgroundTasks runs
    after the response is sent, so the request-scoped session is already closed).
    """
    from app.core.database import async_session

    async with async_session() as db:
        await process_document(db, document_id, file_data, mime_type)
