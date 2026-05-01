"""
Integration: audit service writes real rows with correct inputs_hash to PostgreSQL.

Exercises app.services.audit.log_clinical_decision against the session-scoped
container DB — no mocks, no in-memory SQLite.
"""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select

from app.models.audit_log import AuditLog
from app.models.user import User
from app.services.audit import log_clinical_decision


# ---------------------------------------------------------------------------
# Shared fixture
# ---------------------------------------------------------------------------


@pytest.fixture
async def audit_user(db_session):
    """Minimal user needed to satisfy audit_logs.user_id FK."""
    from app.core.security import get_password_hash

    user = User(
        email=f"audit_{uuid.uuid4().hex[:8]}@integration.example",
        password_hash=get_password_hash("audit-test-pass-123!"),
        role="admin",
        is_active=True,
    )
    db_session.add(user)
    await db_session.flush()
    await db_session.commit()
    return user


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.integration
async def test_audit_entries_have_inputs_hash(db_session, audit_user):
    """
    log_clinical_decision stores a 64-char SHA-256 hex inputs_hash in JSONB.

    Fetches rows fresh from DB to confirm persistence (not just in-memory state).
    """
    case_id = uuid.uuid4()

    for i in range(3):
        await log_clinical_decision(
            db_session,
            case_id=case_id,
            action="triage",
            details={"score": i, "payload": f"turn-{i}"},
            model_version="gpt-4o-mini:integration-test",
            user_id=audit_user.id,
        )

    await db_session.commit()

    result = await db_session.execute(
        select(AuditLog)
        .where(AuditLog.entity_id == case_id)
        .order_by(AuditLog.created_at.asc())
    )
    rows = result.scalars().all()

    assert len(rows) == 3, f"Expected 3 audit rows, got {len(rows)}"

    for row in rows:
        assert row.details is not None, "details JSONB must not be NULL"
        assert "inputs_hash" in row.details, (
            "inputs_hash missing from audit details — "
            "log_clinical_decision must set it"
        )
        h = row.details["inputs_hash"]
        assert isinstance(h, str) and len(h) == 64, (
            f"inputs_hash must be a 64-char SHA-256 hex string, got {h!r}"
        )


@pytest.mark.integration
async def test_audit_created_at_is_monotonic(db_session, audit_user):
    """
    Multiple audit entries for the same case must have non-decreasing created_at.

    Guards against clock skew or wrong DEFAULT on the column.
    """
    case_id = uuid.uuid4()

    for i in range(4):
        await log_clinical_decision(
            db_session,
            case_id=case_id,
            action="guardrail",
            details={"turn": i},
            model_version="gpt-4o-mini:integration-test",
            user_id=audit_user.id,
        )

    await db_session.commit()

    result = await db_session.execute(
        select(AuditLog)
        .where(AuditLog.entity_id == case_id)
        .order_by(AuditLog.created_at.asc())
    )
    rows = result.scalars().all()

    timestamps = [r.created_at for r in rows]
    assert timestamps == sorted(timestamps), (
        "audit_log.created_at must be monotonically non-decreasing. "
        f"Got: {timestamps}"
    )


@pytest.mark.integration
async def test_audit_previous_hash_chain(db_session, audit_user):
    """
    Hash chain (gap #4) — tamper-evident chain across consecutive entries.

    Each row carries dedicated ``previous_hash`` / ``chain_hash`` columns
    (not JSONB) so the chain has database-level NOT NULL guarantees and an
    indexable lookup key.

    Invariant: ``row[N].previous_hash == row[N-1].chain_hash``.
    Detailed tests live in ``test_audit_chain.py``.
    """
    case_id = uuid.uuid4()

    for i in range(3):
        await log_clinical_decision(
            db_session,
            case_id=case_id,
            action="triage",
            details={"turn": i},
            model_version="gpt-4o-mini:integration-test",
            user_id=audit_user.id,
        )

    await db_session.commit()

    result = await db_session.execute(
        select(AuditLog)
        .where(AuditLog.entity_id == case_id)
        .order_by(AuditLog.created_at.asc())
    )
    rows = result.scalars().all()

    for idx, row in enumerate(rows[1:], 1):
        prev = rows[idx - 1]
        assert row.previous_hash == prev.chain_hash, (
            f"Row {idx} previous_hash must equal row {idx - 1} chain_hash. "
            f"Got prev_hash={row.previous_hash!r}, want={prev.chain_hash!r}"
        )
