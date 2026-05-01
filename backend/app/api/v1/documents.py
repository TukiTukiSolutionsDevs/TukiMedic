"""Documents REST API — upload, list, get, delete."""

import os
import re
import uuid
from typing import Any

import filetype
from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.dependencies import get_current_user, require_subscription_tier
from app.core.storage import storage_client
from app.models.document import DocumentModel, LabValueModel
from app.models.user import User
from app.services.audit import log_action
from app.services.document_processor import _process_document_bg

router = APIRouter(prefix="/documents", tags=["documents"])

MAX_FILE_SIZE = 20 * 1024 * 1024  # 20 MB
ALLOWED_MIMES = {"application/pdf", "image/jpeg", "image/png"}

# Whitelist for filename chars — anything else collapses to "_". This blocks
# path traversal (../foo), null bytes, and shell metacharacters.
_FILENAME_SAFE_CHARS = re.compile(r"[^A-Za-z0-9._-]+")


def sanitize_filename(raw: str | None, fallback: str = "upload") -> str:
    """Return a filesystem-safe, length-bounded filename.

    - Strips path components (no traversal).
    - Replaces non-[A-Za-z0-9._-] runs with a single underscore.
    - Strips leading dots so the file can never be a hidden/special name.
    - Caps total length at 200 chars (preserving the extension when possible).
    - Returns ``fallback`` if the result would be empty.
    """
    if not raw:
        return fallback
    base = os.path.basename(str(raw))
    base = _FILENAME_SAFE_CHARS.sub("_", base).strip("._")
    if not base:
        return fallback
    if len(base) > 200:
        # Try to preserve extension
        root, ext = os.path.splitext(base)
        ext = ext[:16]  # never trust an unbounded extension
        base = (root[: 200 - len(ext)] + ext) if ext else root[:200]
    return base


# ---------------------------------------------------------------------------
# Upload
# ---------------------------------------------------------------------------

@router.post("/upload", status_code=status.HTTP_201_CREATED)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    case_id: uuid.UUID | None = Form(None),
    current_user: User = Depends(require_subscription_tier("paid")),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    file_data = await file.read()

    # --- size validation ---
    if len(file_data) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413,
            detail="File too large. Maximum allowed size is 20 MB.",
        )

    # --- MIME validation (trust file magic, NOT client Content-Type) ---
    kind = filetype.guess(file_data)
    if kind is None or kind.mime not in ALLOWED_MIMES:
        raise HTTPException(
            status_code=400,
            detail="Invalid file type. Allowed formats: PDF, JPEG, PNG.",
        )

    # --- upload to MinIO ---
    doc_id = uuid.uuid4()
    safe_name = sanitize_filename(file.filename)
    storage_path = f"{current_user.id}/{doc_id}/{safe_name}"
    await storage_client.upload_file(file_data, storage_path, kind.mime)

    # --- persist to DB ---
    doc = DocumentModel(
        id=doc_id,
        user_id=current_user.id,
        case_id=case_id,
        original_filename=safe_name,
        mime_type=kind.mime,
        file_size=len(file_data),
        storage_path=storage_path,
        processing_status="pending",
    )
    db.add(doc)
    await db.flush()   # assign ID without committing
    await db.refresh(doc)

    # Kick off async processing pipeline (OCR → classify → extract)
    background_tasks.add_task(_process_document_bg, str(doc.id), file_data, kind.mime, settings.OPENAI_API_KEY)

    await log_action(
        db,
        user_id=current_user.id,
        action="document_upload",
        entity_type="document",
        entity_id=doc.id,
        details={"filename": safe_name, "mime": kind.mime, "size": len(file_data)},
    )
    await db.commit()  # single commit: document + audit log

    return {
        "id": str(doc.id),
        "original_filename": doc.original_filename,
        "mime_type": doc.mime_type,
        "file_size": doc.file_size,
        "processing_status": doc.processing_status,
        "created_at": doc.created_at.isoformat() if doc.created_at else None,
    }


# ---------------------------------------------------------------------------
# List
# ---------------------------------------------------------------------------

@router.get("/")
async def list_documents(
    skip: int = 0,
    limit: int = 20,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[dict[str, Any]]:
    result = await db.execute(
        select(DocumentModel)
        .where(DocumentModel.user_id == current_user.id)
        .order_by(DocumentModel.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    docs = result.scalars().all()
    return [
        {
            "id": str(d.id),
            "original_filename": d.original_filename,
            "mime_type": d.mime_type,
            "file_size": d.file_size,
            "doc_type": d.doc_type,
            "processing_status": d.processing_status,
            "created_at": d.created_at.isoformat() if d.created_at else None,
        }
        for d in docs
    ]


# ---------------------------------------------------------------------------
# Get single document (with lab values)
# ---------------------------------------------------------------------------

@router.get("/{document_id}")
async def get_document(
    document_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    result = await db.execute(
        select(DocumentModel).where(DocumentModel.id == document_id)
    )
    doc = result.scalar_one_or_none()

    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found.")

    if doc.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied.")

    lv_result = await db.execute(
        select(LabValueModel).where(LabValueModel.document_id == document_id)
    )
    lab_values = lv_result.scalars().all()

    return {
        "id": str(doc.id),
        "original_filename": doc.original_filename,
        "mime_type": doc.mime_type,
        "file_size": doc.file_size,
        "storage_path": doc.storage_path,
        "doc_type": doc.doc_type,
        "doc_type_confidence": doc.doc_type_confidence,
        "processing_status": doc.processing_status,
        "ocr_text": doc.ocr_text,
        "created_at": doc.created_at.isoformat() if doc.created_at else None,
        "lab_values": [
            {
                "id": str(lv.id),
                "test_name": lv.test_name,
                "value": lv.value,
                "unit": lv.unit,
                "reference_range": lv.reference_range,
                "flag": lv.flag,
            }
            for lv in lab_values
        ],
    }


# ---------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------

@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    document_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    result = await db.execute(
        select(DocumentModel).where(DocumentModel.id == document_id)
    )
    doc = result.scalar_one_or_none()

    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found.")

    if doc.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied.")

    await storage_client.delete_file(doc.storage_path)
    await db.delete(doc)
    await db.commit()
