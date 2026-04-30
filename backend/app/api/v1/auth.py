import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.core.rate_limit import limiter
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    get_password_hash,
    verify_password,
)
from app.core.storage import storage_client
from app.models.case import Case
from app.models.clinical_fact import ClinicalFactModel
from app.models.document import DocumentModel, LabValueModel
from app.models.message import Message
from app.models.patient import PatientProfile, PatientTimelineEvent
from app.models.user import User
from app.schemas.auth import (
    LoginRequest,
    LoginResponse,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
    UserResponse,
)
from app.services.audit import log_action

log = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED
)
@limiter.limit("3/hour")
async def register(
    request: Request,
    body: RegisterRequest,
    db: AsyncSession = Depends(get_db),
):
    # Check if email exists
    result = await db.execute(select(User).where(User.email == body.email))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email already registered")

    user = User(
        email=body.email,
        password_hash=get_password_hash(body.password),
        display_name=body.display_name,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    ip = request.client.host if request.client else None
    await log_action(
        db,
        user_id=user.id,
        action="register",
        entity_type="user",
        entity_id=user.id,
        ip_address=ip,
    )
    await db.commit()

    return TokenResponse(
        access_token=create_access_token(
            {
                "sub": str(user.id),
                "role": user.role,
                "subscription_tier": user.subscription_tier,
            }
        ),
        refresh_token=create_refresh_token({"sub": str(user.id)}),
    )


@router.post("/login", response_model=LoginResponse)
@limiter.limit("5/minute")
async def login(
    request: Request,
    body: LoginRequest,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()

    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account disabled")

    ip = request.client.host if request.client else None
    await log_action(
        db,
        user_id=user.id,
        action="login",
        entity_type="user",
        entity_id=user.id,
        ip_address=ip,
    )
    await db.commit()

    return LoginResponse(
        access_token=create_access_token(
            {
                "sub": str(user.id),
                "role": user.role,
                "subscription_tier": user.subscription_tier,
            }
        ),
        refresh_token=create_refresh_token({"sub": str(user.id)}),
        user=UserResponse.model_validate(user),
    )


@router.post("/refresh", response_model=TokenResponse)
@limiter.limit("10/minute")
async def refresh_token(
    request: Request,
    body: RefreshRequest,
    db: AsyncSession = Depends(get_db),
):
    try:
        payload = decode_token(body.refresh_token)
        if payload.get("type") != "refresh":
            raise HTTPException(status_code=401, detail="Invalid token type")
        user_id = payload.get("sub")
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found")

    return TokenResponse(
        access_token=create_access_token({"sub": str(user.id)}),
        refresh_token=create_refresh_token({"sub": str(user.id)}),
    )


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    return current_user


# ---------------------------------------------------------------------------
# GDPR / Ley 25.326 — right to erasure (T2.14)
# ---------------------------------------------------------------------------

@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("3/hour")
async def delete_me(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Erase all PII tied to the authenticated user.

    Hard-deletes clinical data (facts, timeline events, profiles, documents
    + S3 objects, lab values, cases, messages). The User row is kept but
    anonymised (email replaced with `deleted_<id>@deleted.invalid`) so the
    audit trail of past actions remains valid for legal records — but no
    new login is ever possible (is_active=False).

    Returns 204 on success. Failures during S3 cleanup are logged but do
    NOT block erasure of DB rows: data minimisation wins over completeness.
    """
    user_id = current_user.id

    # 1) Best-effort delete of S3 objects for this user's documents.
    try:
        docs_result = await db.execute(
            select(DocumentModel).where(DocumentModel.user_id == user_id)
        )
        for doc in docs_result.scalars().all():
            try:
                await storage_client.delete_file(doc.storage_path)
            except Exception:  # noqa: BLE001
                log.exception("gdpr: failed to delete S3 object %s", doc.storage_path)
    except Exception:  # noqa: BLE001
        log.exception("gdpr: enumerate documents failed for user %s", user_id)

    # 2) Hard delete clinical data — order matters for FK constraints.
    #    LabValue → Document → ClinicalFact → PatientTimeline → PatientProfile
    #    Then: Message → Case
    await db.execute(
        delete(LabValueModel).where(
            LabValueModel.document_id.in_(
                select(DocumentModel.id).where(DocumentModel.user_id == user_id)
            )
        )
    )
    await db.execute(delete(DocumentModel).where(DocumentModel.user_id == user_id))
    await db.execute(delete(ClinicalFactModel).where(ClinicalFactModel.user_id == user_id))
    await db.execute(delete(PatientTimelineEvent).where(PatientTimelineEvent.user_id == user_id))
    await db.execute(delete(PatientProfile).where(PatientProfile.user_id == user_id))
    await db.execute(
        delete(Message).where(
            Message.case_id.in_(select(Case.id).where(Case.user_id == user_id))
        )
    )
    await db.execute(delete(Case).where(Case.user_id == user_id))

    # 3) Anonymise + disable the user row (NOT delete: audit trail must stay valid).
    current_user.email = f"deleted_{user_id}@deleted.invalid"
    current_user.password_hash = "!"  # never matches any verify_password()
    current_user.display_name = None
    current_user.birth_year = None
    current_user.biological_sex = None
    current_user.preferences = {}
    current_user.is_active = False
    current_user.deleted_at = datetime.now(timezone.utc)

    # 4) Audit the erasure for legal record. The user_id stays valid; details
    #    contain the IP and a marker so we can prove the user requested it.
    ip = request.client.host if request.client else None
    await log_action(
        db,
        user_id=user_id,
        action="gdpr_delete",
        entity_type="user",
        entity_id=user_id,
        details={"reason": "user_request"},
        ip_address=ip,
    )
    await db.commit()
    return None
