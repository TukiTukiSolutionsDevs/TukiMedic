"""Admin API — metrics, audit log, KB CRUD. All endpoints require is_admin=True."""
from __future__ import annotations

import json
import uuid
from typing import Any, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import func, select, update as sa_update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import crypto
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.core.graph_cache import clear as clear_graph_cache
from app.models.audit_log import AuditLog
from app.models.case import Case
from app.models.document import DocumentModel
from app.models.patient import KnowledgeBaseChunk
from app.models.provider_credential import ProviderCredential
from app.models.user import User
from app.schemas.admin import AdminUserPatch, CredentialCreate, CredentialRotate
from app.services.audit import log_action

router = APIRouter(prefix="/admin", tags=["admin"])

# ---------------------------------------------------------------------------
# Guard
# ---------------------------------------------------------------------------


async def require_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != "admin":
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
# GET /admin/users
# ---------------------------------------------------------------------------


@router.get("/users")
async def list_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    offset = (page - 1) * page_size

    total = (await db.execute(select(func.count(User.id)))).scalar() or 0

    rows = (
        await db.execute(
            select(User).order_by(User.created_at.desc()).offset(offset).limit(page_size)
        )
    ).scalars().all()

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [
            {
                "id": str(u.id),
                "email": u.email,
                "display_name": u.display_name,
                "role": u.role,
                "subscription_tier": u.subscription_tier,
                "is_active": u.is_active,
                "created_at": u.created_at.isoformat() if u.created_at else None,
            }
            for u in rows
        ],
    }


# ---------------------------------------------------------------------------
# GET /admin/users/{user_id}
# ---------------------------------------------------------------------------


@router.get("/users/{user_id}")
async def get_user(
    user_id: uuid.UUID,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    return {
        "id": str(user.id),
        "email": user.email,
        "display_name": user.display_name,
        "role": user.role,
        "subscription_tier": user.subscription_tier,
        "is_active": user.is_active,
        "created_at": user.created_at.isoformat() if user.created_at else None,
    }


# ---------------------------------------------------------------------------
# PATCH /admin/users/{user_id}
# ---------------------------------------------------------------------------


@router.patch("/users/{user_id}")
async def patch_user(
    user_id: uuid.UUID,
    body: AdminUserPatch,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    # Last-admin guard: SELECT FOR UPDATE serialises concurrent demotions.
    if body.role is not None and body.role != "admin" and user.role == "admin":
        count_result = await db.execute(
            select(func.count(User.id))
            .where(User.role == "admin")
            .with_for_update()
        )
        admin_count = count_result.scalar() or 0
        if admin_count <= 1:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Cannot demote the last admin",
            )

    changes: dict[str, Any] = {}
    if body.role is not None:
        changes["role"] = body.role
        user.role = body.role
    if body.subscription_tier is not None:
        changes["subscription_tier"] = body.subscription_tier
        user.subscription_tier = body.subscription_tier
    if body.is_active is not None:
        changes["is_active"] = body.is_active
        user.is_active = body.is_active

    await log_action(
        db,
        user_id=admin.id,
        action="user_patch",
        entity_type="user",
        entity_id=user_id,
        details={"changes": changes, "target_user_id": str(user_id)},
    )
    await db.commit()
    await db.refresh(user)

    return {
        "id": str(user.id),
        "email": user.email,
        "display_name": user.display_name,
        "role": user.role,
        "subscription_tier": user.subscription_tier,
        "is_active": user.is_active,
        "created_at": user.created_at.isoformat() if user.created_at else None,
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
    background_tasks: BackgroundTasks,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """Trigger KB ingestion. Runs after the response is sent (T3.5 — was
    `asyncio.create_task(...)` without holding a reference, which let the
    GC cancel the task at any moment)."""
    from app.services.kb_indexer import run_indexer

    await log_action(
        db,
        user_id=admin.id,
        action="kb_ingest",
        details={"triggered_by": str(admin.id)},
    )
    await db.commit()

    # FastAPI keeps the reference alive until the task finishes; if the
    # indexer raises, the framework logs it via its task error handler.
    background_tasks.add_task(run_indexer)

    return {"status": "accepted", "message": "KB ingestion started in background"}


# ---------------------------------------------------------------------------
# S4.0.c — Encrypted API key vault
# ---------------------------------------------------------------------------


def _cred_response(cred) -> dict[str, Any]:
    """Safe credential response — NEVER includes encrypted_key, iv, or tag."""
    return {
        "id": str(cred.id),
        "provider": cred.provider,
        "label": cred.label,
        "is_active": cred.is_active,
        "created_at": cred.created_at.isoformat() if cred.created_at else None,
        "rotated_at": cred.rotated_at.isoformat() if cred.rotated_at else None,
        "created_by_user_id": (
            str(cred.created_by_user_id) if cred.created_by_user_id else None
        ),
    }


# POST /admin/credentials


@router.post("/credentials", status_code=status.HTTP_201_CREATED)
async def create_credential(
    body: CredentialCreate,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    ciphertext, iv, tag = crypto.encrypt(body.plaintext_key.encode())
    cred = ProviderCredential(
        provider=body.provider,
        label=body.label,
        encrypted_key=ciphertext,
        iv=iv,
        tag=tag,
        is_active=False,
        created_by_user_id=admin.id,
    )
    db.add(cred)
    await db.flush()

    if body.activate:
        await db.execute(
            sa_update(ProviderCredential)
            .where(ProviderCredential.provider == body.provider)
            .where(ProviderCredential.id != cred.id)
            .values(is_active=False)
        )
        cred.is_active = True

    await log_action(
        db,
        user_id=admin.id,
        action="api_key_create",
        entity_type="api_key",
        entity_id=cred.id,
        details={
            "provider": body.provider,
            "label": body.label,
            "activated": body.activate,
        },
    )
    await db.commit()
    await db.refresh(cred)
    clear_graph_cache()
    return _cred_response(cred)


# GET /admin/credentials


@router.get("/credentials")
async def list_credentials(
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    rows = (
        await db.execute(
            select(ProviderCredential).order_by(ProviderCredential.created_at.desc())
        )
    ).scalars().all()
    return {"items": [_cred_response(c) for c in rows]}


# PATCH /admin/credentials/{id}/rotate


@router.patch("/credentials/{credential_id}/rotate")
async def rotate_credential(
    credential_id: uuid.UUID,
    body: CredentialRotate,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    from datetime import datetime, timezone

    result = await db.execute(
        select(ProviderCredential).where(ProviderCredential.id == credential_id)
    )
    cred = result.scalar_one_or_none()
    if cred is None:
        raise HTTPException(status_code=404, detail="Credential not found")

    ciphertext, iv, tag = crypto.encrypt(body.plaintext_key.encode())
    cred.encrypted_key = ciphertext
    cred.iv = iv
    cred.tag = tag
    cred.rotated_at = datetime.now(timezone.utc)

    await log_action(
        db,
        user_id=admin.id,
        action="api_key_rotate",
        entity_type="api_key",
        entity_id=credential_id,
        details={"provider": cred.provider, "label": cred.label},
    )
    await db.commit()
    await db.refresh(cred)
    clear_graph_cache()
    return _cred_response(cred)


# PATCH /admin/credentials/{id}/activate


@router.patch("/credentials/{credential_id}/activate")
async def activate_credential(
    credential_id: uuid.UUID,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    result = await db.execute(
        select(ProviderCredential).where(ProviderCredential.id == credential_id)
    )
    cred = result.scalar_one_or_none()
    if cred is None:
        raise HTTPException(status_code=404, detail="Credential not found")

    # Deactivate all other credentials for this provider (single-active invariant)
    await db.execute(
        sa_update(ProviderCredential)
        .where(ProviderCredential.provider == cred.provider)
        .where(ProviderCredential.id != credential_id)
        .values(is_active=False)
    )
    cred.is_active = True

    await log_action(
        db,
        user_id=admin.id,
        action="api_key_activate",
        entity_type="api_key",
        entity_id=credential_id,
        details={"provider": cred.provider, "label": cred.label},
    )
    await db.commit()
    await db.refresh(cred)
    clear_graph_cache()
    return _cred_response(cred)


# DELETE /admin/credentials/{id}


@router.delete("/credentials/{credential_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_credential(
    credential_id: uuid.UUID,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> None:
    result = await db.execute(
        select(ProviderCredential).where(ProviderCredential.id == credential_id)
    )
    cred = result.scalar_one_or_none()
    if cred is None:
        raise HTTPException(status_code=404, detail="Credential not found")

    await db.delete(cred)
    await log_action(
        db,
        user_id=admin.id,
        action="api_key_delete",
        entity_type="api_key",
        entity_id=credential_id,
        details={"provider": cred.provider, "label": cred.label},
    )
    await db.commit()
    clear_graph_cache()
