"""Admin API — metrics, audit log, KB CRUD. All endpoints require is_admin=True."""
from __future__ import annotations

import json
import uuid
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.audit_log import AuditLog
from app.models.case import Case
from app.models.document import DocumentModel
from app.models.patient import KnowledgeBaseChunk
from app.models.user import User
from app.services.audit import log_action

router = APIRouter(prefix="/admin", tags=["admin"])

# ---------------------------------------------------------------------------
# Guard
# ---------------------------------------------------------------------------


async def require_admin(current_user: User = Depends(get_current_user)) -> User:
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    return current_user


# ---------------------------------------------------------------------------
# Redis cache helpers (patched in tests)
# ---------------------------------------------------------------------------


async def _get_cached_metrics() -> Optional[dict]:
    """Return cached metrics dict or None on miss/error."""
    try:
        import redis.asyncio as aioredis
        from app.core.config import settings

        r = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
        raw = await r.get("admin:metrics")
        await r.aclose()
        return json.loads(raw) if raw else None
    except Exception:
        return None


async def _cache_metrics(data: dict) -> None:
    """Cache metrics dict with 5-minute TTL. Silently fails."""
    try:
        import redis.asyncio as aioredis
        from app.core.config import settings

        r = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
        await r.setex("admin:metrics", 300, json.dumps(data, default=str))
        await r.aclose()
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Embedding helper (patched in tests)
# ---------------------------------------------------------------------------


async def _generate_embedding(text: str) -> list[float]:
    from langchain_openai import OpenAIEmbeddings

    embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
    return await embeddings.aembed_query(text)


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class KBChunkCreate(BaseModel):
    source: str
    title: str
    content: str
    chunk_index: int = 0
    specialty_tags: list[str] = []


# ---------------------------------------------------------------------------
# GET /admin/metrics
# ---------------------------------------------------------------------------


@router.get("/metrics")
async def get_metrics(
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    # Cache hit
    cached = await _get_cached_metrics()
    if cached:
        return cached

    # Aggregate queries
    total_cases = (await db.execute(select(func.count(Case.id)))).scalar()
    total_users = (await db.execute(select(func.count(User.id)))).scalar()
    total_documents = (await db.execute(select(func.count(DocumentModel.id)))).scalar()
    kb_chunks = (await db.execute(select(func.count(KnowledgeBaseChunk.id)))).scalar()

    # Cases by status
    status_rows = (
        await db.execute(
            select(Case.status, func.count(Case.id)).group_by(Case.status)
        )
    ).all()
    cases_by_status = {row[0]: row[1] for row in status_rows}

    # Triage distribution
    triage_rows = (
        await db.execute(
            select(Case.triage_level, func.count(Case.id))
            .where(Case.triage_level.isnot(None))
            .group_by(Case.triage_level)
        )
    ).all()
    triage_distribution = {row[0]: row[1] for row in triage_rows}

    result: dict[str, Any] = {
        "total_cases": total_cases or 0,
        "total_users": total_users or 0,
        "total_documents": total_documents or 0,
        "kb_chunks": kb_chunks or 0,
        "cases_by_status": cases_by_status,
        "triage_distribution": triage_distribution,
    }

    await _cache_metrics(result)
    return result


# ---------------------------------------------------------------------------
# GET /admin/audit-log
# ---------------------------------------------------------------------------


@router.get("/audit-log")
async def get_audit_log(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    action: Optional[str] = Query(None),
    user_id: Optional[uuid.UUID] = Query(None),
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    offset = (page - 1) * page_size

    # Build filters
    filters = []
    if action:
        filters.append(AuditLog.action == action)
    if user_id:
        filters.append(AuditLog.user_id == user_id)

    # Count
    count_q = select(func.count(AuditLog.id))
    if filters:
        count_q = count_q.where(*filters)
    total = (await db.execute(count_q)).scalar() or 0

    # Rows
    rows_q = (
        select(AuditLog)
        .order_by(AuditLog.created_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    if filters:
        rows_q = rows_q.where(*filters)
    rows = (await db.execute(rows_q)).scalars().all()

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [
            {
                "id": str(r.id),
                "user_id": str(r.user_id) if r.user_id else None,
                "action": r.action,
                "entity_type": r.entity_type,
                "entity_id": str(r.entity_id) if r.entity_id else None,
                "details": r.details,
                "ip_address": r.ip_address,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ],
    }


# ---------------------------------------------------------------------------
# GET /admin/kb
# ---------------------------------------------------------------------------


@router.get("/kb")
async def list_kb(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    source: Optional[str] = Query(None),
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    offset = (page - 1) * page_size

    filters = []
    if source:
        filters.append(KnowledgeBaseChunk.source == source)

    count_q = select(func.count(KnowledgeBaseChunk.id))
    if filters:
        count_q = count_q.where(*filters)
    total = (await db.execute(count_q)).scalar() or 0

    rows_q = (
        select(KnowledgeBaseChunk)
        .order_by(KnowledgeBaseChunk.created_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    if filters:
        rows_q = rows_q.where(*filters)
    chunks = (await db.execute(rows_q)).scalars().all()

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [
            {
                "id": str(c.id),
                "source": c.source,
                "title": c.title,
                "content": c.content[:200],
                "chunk_index": c.chunk_index,
                "specialty_tags": c.specialty_tags,
                "created_at": c.created_at.isoformat() if c.created_at else None,
            }
            for c in chunks
        ],
    }


# ---------------------------------------------------------------------------
# POST /admin/kb
# ---------------------------------------------------------------------------


@router.post("/kb", status_code=status.HTTP_201_CREATED)
async def add_kb_chunk(
    body: KBChunkCreate,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    embedding = await _generate_embedding(f"{body.title}\n{body.content}")

    chunk = KnowledgeBaseChunk(
        source=body.source,
        title=body.title,
        content=body.content,
        chunk_index=body.chunk_index,
        specialty_tags=body.specialty_tags,
        embedding=embedding,
    )
    db.add(chunk)
    await db.commit()
    await db.refresh(chunk)

    await log_action(
        db,
        user_id=admin.id,
        action="kb_add_chunk",
        entity_type="kb_chunk",
        entity_id=chunk.id,
    )
    await db.commit()

    return {
        "id": str(chunk.id),
        "source": chunk.source,
        "title": chunk.title,
        "chunk_index": chunk.chunk_index,
        "specialty_tags": chunk.specialty_tags,
        "created_at": chunk.created_at.isoformat() if chunk.created_at else None,
    }


# ---------------------------------------------------------------------------
# DELETE /admin/kb/{id}
# ---------------------------------------------------------------------------


@router.delete("/kb/{chunk_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_kb_chunk(
    chunk_id: uuid.UUID,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> None:
    result = await db.execute(
        select(KnowledgeBaseChunk).where(KnowledgeBaseChunk.id == chunk_id)
    )
    chunk = result.scalar_one_or_none()
    if chunk is None:
        raise HTTPException(status_code=404, detail="KB chunk not found")

    await db.delete(chunk)
    await log_action(
        db,
        user_id=admin.id,
        action="kb_delete_chunk",
        entity_type="kb_chunk",
        entity_id=chunk_id,
    )
    await db.commit()


# ---------------------------------------------------------------------------
# GET /admin/kb/stats
# ---------------------------------------------------------------------------


@router.get("/kb/stats")
async def kb_stats(
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    rows = (
        await db.execute(
            select(KnowledgeBaseChunk.source, func.count(KnowledgeBaseChunk.id))
            .group_by(KnowledgeBaseChunk.source)
        )
    ).all()

    return {
        "by_source": [{"source": r[0], "count": r[1]} for r in rows],
        "total": sum(r[1] for r in rows),
    }


# ---------------------------------------------------------------------------
# POST /admin/kb/ingest  (bulk ingest from MedlinePlus)
# ---------------------------------------------------------------------------


@router.post("/kb/ingest", status_code=status.HTTP_202_ACCEPTED)
async def ingest_kb(
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    from app.services.kb_indexer import run_indexer

    await log_action(
        db,
        user_id=admin.id,
        action="kb_ingest",
        details={"triggered_by": str(admin.id)},
    )
    await db.commit()

    # Fire and forget — indexer handles its own DB session
    import asyncio
    asyncio.create_task(run_indexer())

    return {"status": "accepted", "message": "KB ingestion started in background"}
