"""
PostgreSQL Memory Level 3 — Patient Timeline + Profile.

Provides structured clinical history (cross-case, chronological) and an
always-current patient profile (allergies, medications, chronic conditions).

All functions accept an AsyncSession. OpenAI api_key is optional (BYOK pattern)
— if omitted, embeddings are skipped but the event is still stored.
"""

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.patient import PatientProfile, PatientTimelineEvent
from app.memory.pg_facts import get_embedding


async def store_timeline_event(
    db: AsyncSession,
    user_id: str,
    case_id: str | None,
    event_type: str,
    summary: str,
    details: dict | None = None,
    api_key: str | None = None,
) -> PatientTimelineEvent:
    """Store a clinical event in the patient timeline.

    Optionally embeds the summary for future semantic retrieval.
    Returns the created PatientTimelineEvent (unflushed FK visible after flush).
    """
    embedding = None
    if api_key:
        embedding = await get_embedding(f"{event_type}: {summary}", api_key)

    event = PatientTimelineEvent(
        user_id=user_id,
        case_id=case_id,
        event_type=event_type,
        summary=summary,
        details=details,
        embedding=embedding,
        occurred_at=datetime.now(timezone.utc),
    )
    db.add(event)
    await db.flush()
    return event


async def get_patient_timeline(
    db: AsyncSession,
    user_id: str,
    limit: int = 20,
) -> list[dict]:
    """Return the most recent timeline events for a patient, newest first."""
    result = await db.execute(
        select(PatientTimelineEvent)
        .where(PatientTimelineEvent.user_id == user_id)
        .order_by(PatientTimelineEvent.occurred_at.desc())
        .limit(limit)
    )
    return [
        {
            "event_type": e.event_type,
            "summary": e.summary,
            "details": e.details,
            "occurred_at": str(e.occurred_at),
        }
        for e in result.scalars().all()
    ]


async def get_or_create_profile(
    db: AsyncSession,
    user_id: str,
) -> dict:
    """Return patient profile as dict; creates an empty one if none exists."""
    result = await db.execute(
        select(PatientProfile).where(PatientProfile.user_id == user_id)
    )
    profile = result.scalar_one_or_none()

    if not profile:
        profile = PatientProfile(
            user_id=user_id,
            allergies=[],
            active_medications=[],
            chronic_conditions=[],
        )
        db.add(profile)
        await db.flush()

    return {
        "allergies": profile.allergies or [],
        "active_medications": profile.active_medications or [],
        "chronic_conditions": profile.chronic_conditions or [],
        "blood_type": profile.blood_type,
        "age": profile.age,
        "sex": profile.sex,
    }


async def update_profile(
    db: AsyncSession,
    user_id: str,
    updates: dict,
) -> None:
    """Update patient profile fields (upsert — creates if missing)."""
    result = await db.execute(
        select(PatientProfile).where(PatientProfile.user_id == user_id)
    )
    profile = result.scalar_one_or_none()

    if not profile:
        profile = PatientProfile(user_id=user_id)
        db.add(profile)

    for key, value in updates.items():
        if hasattr(profile, key):
            setattr(profile, key, value)

    await db.flush()
