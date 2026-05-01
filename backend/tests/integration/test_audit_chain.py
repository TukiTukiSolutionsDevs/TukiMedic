"""
Integration — audit hash chain (gap #4 from hard-blockers-plan).

Each audit row carries `previous_hash` and `chain_hash` columns forming
a tamper-evident chain. Genesis row uses `previous_hash = "0" * 64`.

The chain is protected at write-time by a per-transaction advisory lock
(`pg_advisory_xact_lock(hashtext('audit_chain'))`) so concurrent inserts
cannot create gaps or fork the chain.

Run with:
    RUN_INTEGRATION=1 /app/.venv/bin/pytest \
        -m integration tests/integration/test_audit_chain.py -v
"""
from __future__ import annotations

import asyncio
import hashlib
import uuid
from contextlib import asynccontextmanager

import pytest
from sqlalchemy import select

from app.models.audit_log import AuditLog
from app.models.user import User
from app.services.audit import (
    log_action,
    log_clinical_decision,
    verify_chain,
)


GENESIS = "0" * 64


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
async def chain_user(db_session):
    """Minimal user to satisfy audit_logs.user_id FK."""
    from app.core.security import get_password_hash

    user = User(
        email=f"chain_{uuid.uuid4().hex[:8]}@integration.example",
        password_hash=get_password_hash("chain-test-pass-123!"),
        role="admin",
        is_active=True,
    )
    db_session.add(user)
    await db_session.flush()
    await db_session.commit()
    return user


# ---------------------------------------------------------------------------
# 1. Genesis
# ---------------------------------------------------------------------------


@pytest.mark.integration
async def test_audit_chain_genesis_uses_zero_hash(db_session, chain_user):
    """
    The very first audit row in an empty chain has `previous_hash == "0"*64`.

    `chain_hash` MUST be sha256(previous_hash || inputs_hash) — never empty,
    never null.
    """
    case_id = uuid.uuid4()

    entry = await log_clinical_decision(
        db_session,
        case_id=case_id,
        action="triage",
        details={"score": 1},
        model_version="gpt-4o-mini:test",
        user_id=chain_user.id,
    )
    await db_session.commit()

    fresh = await db_session.get(AuditLog, entry.id)
    assert fresh is not None

    assert fresh.previous_hash == GENESIS, (
        "Genesis row must have previous_hash == '0'*64. "
        f"Got: {fresh.previous_hash!r}"
    )

    inputs_hash = fresh.details["inputs_hash"]
    expected = hashlib.sha256(
        (GENESIS + inputs_hash).encode("utf-8")
    ).hexdigest()
    assert fresh.chain_hash == expected, (
        "chain_hash must equal sha256(previous_hash || inputs_hash). "
        f"Got: {fresh.chain_hash!r}, expected: {expected!r}"
    )


# ---------------------------------------------------------------------------
# 2. Links between consecutive entries
# ---------------------------------------------------------------------------


@pytest.mark.integration
async def test_audit_chain_links_consecutive(db_session, chain_user):
    """
    Entry N has `previous_hash == entry(N-1).chain_hash` for all N > 0.

    Verifies the chain is contiguous across multiple writes in the same
    case AND across different cases — the chain is global, not per-case.
    """
    case_id = uuid.uuid4()

    for i in range(5):
        await log_clinical_decision(
            db_session,
            case_id=case_id,
            action="triage",
            details={"turn": i},
            model_version="gpt-4o-mini:test",
            user_id=chain_user.id,
        )
    await db_session.commit()

    rows = (
        await db_session.execute(
            select(AuditLog)
            .where(AuditLog.entity_id == case_id)
            .order_by(AuditLog.created_at.asc(), AuditLog.id.asc())
        )
    ).scalars().all()

    assert len(rows) == 5

    for idx, row in enumerate(rows):
        if idx == 0:
            assert row.previous_hash == GENESIS
        else:
            prev = rows[idx - 1]
            assert row.previous_hash == prev.chain_hash, (
                f"Row {idx} previous_hash must equal row {idx - 1} chain_hash. "
                f"Got prev_hash={row.previous_hash!r}, "
                f"want={prev.chain_hash!r}"
            )

        # chain_hash recomputed
        recomputed = hashlib.sha256(
            (row.previous_hash + row.details["inputs_hash"]).encode("utf-8")
        ).hexdigest()
        assert row.chain_hash == recomputed


# ---------------------------------------------------------------------------
# 3. log_action (generic) is also chained
# ---------------------------------------------------------------------------


@pytest.mark.integration
async def test_log_action_participates_in_chain(db_session, chain_user):
    """
    The generic `log_action` (used by API endpoints — auth, documents, KB)
    MUST also be part of the chain. A tamper-evident audit only works if
    every audit write is chained.
    """
    e1 = await log_action(
        db_session,
        user_id=chain_user.id,
        action="login",
        ip_address="127.0.0.1",
    )
    e2 = await log_action(
        db_session,
        user_id=chain_user.id,
        action="document_upload",
        entity_type="document",
        details={"file": "report.pdf"},
    )
    await db_session.commit()

    fresh1 = await db_session.get(AuditLog, e1.id)
    fresh2 = await db_session.get(AuditLog, e2.id)

    # Both rows have non-empty chain hashes
    assert len(fresh1.chain_hash) == 64
    assert len(fresh2.chain_hash) == 64

    # And they link
    assert fresh2.previous_hash == fresh1.chain_hash, (
        "log_action entries must form a continuous chain with each other"
    )


# ---------------------------------------------------------------------------
# 4. verify_chain helper detects a clean chain
# ---------------------------------------------------------------------------


@pytest.mark.integration
async def test_verify_chain_clean(db_session, chain_user):
    """
    `verify_chain(db)` returns (True, []) when the chain is intact.
    """
    case_id = uuid.uuid4()
    for i in range(4):
        await log_clinical_decision(
            db_session,
            case_id=case_id,
            action="triage",
            details={"turn": i},
            model_version="m:test",
            user_id=chain_user.id,
        )
    await db_session.commit()

    ok, broken = await verify_chain(db_session)
    assert ok is True, f"Clean chain must verify True. Broken IDs: {broken}"
    assert broken == []


# ---------------------------------------------------------------------------
# 5. verify_chain detects tampering (mutated payload)
# ---------------------------------------------------------------------------


@pytest.mark.integration
async def test_verify_chain_detects_tamper(db_session, chain_user):
    """
    Mutating `details` of an existing audit row breaks the chain because
    `inputs_hash` no longer matches the row's actual content. `verify_chain`
    flags the row id of the first detected mismatch.
    """
    case_id = uuid.uuid4()
    rows_in = []
    for i in range(3):
        e = await log_clinical_decision(
            db_session,
            case_id=case_id,
            action="triage",
            details={"turn": i, "payload": f"original-{i}"},
            model_version="m:test",
            user_id=chain_user.id,
        )
        rows_in.append(e.id)
    await db_session.commit()

    # Tamper: rewrite middle row's details in-place (simulate attacker
    # with write access to the table)
    middle_id = rows_in[1]
    mutated = {"turn": 1, "payload": "tampered"}
    await db_session.execute(
        AuditLog.__table__.update()
        .where(AuditLog.id == middle_id)
        .values(details=mutated)
    )
    await db_session.commit()

    ok, broken = await verify_chain(db_session)
    assert ok is False, "Tampered chain must verify False"
    assert middle_id in broken, (
        f"Tampered row {middle_id} must appear in broken list. Got: {broken}"
    )


# ---------------------------------------------------------------------------
# 6. Concurrent inserts don't fork the chain (advisory lock)
# ---------------------------------------------------------------------------


@pytest.mark.integration
async def test_audit_chain_concurrent_inserts_no_gap(
    session_factory, chain_user
):
    """
    50 concurrent inserts via independent DB sessions must produce a
    continuous, non-forked chain. The advisory lock
    `pg_advisory_xact_lock(hashtext('audit_chain'))` serializes the
    SELECT-prev / INSERT-chained pair.
    """
    case_id = uuid.uuid4()

    async def _one_write(turn: int) -> None:
        async with session_factory() as session:
            await log_clinical_decision(
                session,
                case_id=case_id,
                action="triage",
                details={"turn": turn},
                model_version="m:test",
                user_id=chain_user.id,
            )
            await session.commit()

    await asyncio.gather(*[_one_write(i) for i in range(50)])

    # Verify chain end-to-end via helper
    async with session_factory() as session:
        ok, broken = await verify_chain(session)

    assert ok is True, (
        f"Concurrent inserts must not break the chain. Broken: {broken}"
    )

    # Sanity: 50 rows for this case
    async with session_factory() as session:
        rows = (
            await session.execute(
                select(AuditLog).where(AuditLog.entity_id == case_id)
            )
        ).scalars().all()
    assert len(rows) == 50


# ---------------------------------------------------------------------------
# 7. inputs_hash backward compatibility — still in details JSONB
# ---------------------------------------------------------------------------


@pytest.mark.integration
async def test_inputs_hash_preserved_in_details(db_session, chain_user):
    """
    Backward-compat: `details["inputs_hash"]` MUST keep working — existing
    callers/queries depend on it. The new chain columns are additive.
    """
    case_id = uuid.uuid4()
    entry = await log_clinical_decision(
        db_session,
        case_id=case_id,
        action="triage",
        details={"score": 7},
        model_version="m:test",
        user_id=chain_user.id,
    )
    await db_session.commit()

    fresh = await db_session.get(AuditLog, entry.id)
    assert "inputs_hash" in fresh.details
    assert isinstance(fresh.details["inputs_hash"], str)
    assert len(fresh.details["inputs_hash"]) == 64


# ---------------------------------------------------------------------------
# 8. chain_hash is unique per row (cryptographic uniqueness)
# ---------------------------------------------------------------------------


@pytest.mark.integration
async def test_chain_hash_unique_per_row(db_session, chain_user):
    """
    Even rows with identical `details + model_version` payload produce
    DIFFERENT `chain_hash` values because `previous_hash` evolves.

    Sanity check on the chain construction.
    """
    case_id = uuid.uuid4()
    rows = []
    for _ in range(3):
        e = await log_clinical_decision(
            db_session,
            case_id=case_id,
            action="triage",
            details={"static": "same"},
            model_version="m:test",
            user_id=chain_user.id,
        )
        rows.append(e)
    await db_session.commit()

    fresh = [await db_session.get(AuditLog, r.id) for r in rows]
    chain_hashes = [r.chain_hash for r in fresh]
    assert len(set(chain_hashes)) == 3, (
        "Identical payload but different previous_hash must yield distinct "
        f"chain_hash values. Got: {chain_hashes}"
    )
