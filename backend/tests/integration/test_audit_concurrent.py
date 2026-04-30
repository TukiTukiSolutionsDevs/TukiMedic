"""
Integration — BUG 2: _audit_node writes rows for every clinical decision.

Verifies that concurrent asyncio.gather operations do not cause silent
transaction failures in _audit_node. Each wrapped node must produce exactly
one audit row, even when 5 concurrent audit calls share the same DB pool.

Run with: RUN_INTEGRATION=1 poetry run pytest -m integration tests/integration/test_audit_concurrent.py
"""
from __future__ import annotations

import asyncio
import uuid
from contextlib import asynccontextmanager
from unittest.mock import patch

import pytest
from sqlalchemy import select

from app.models.audit_log import AuditLog
from app.models.user import User
from app.orchestrator.graph import _audit_node


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
async def audit_user(db_session):
    """Minimal user to satisfy audit_logs.user_id FK."""
    from app.core.security import get_password_hash

    user = User(
        email=f"audit_conc_{uuid.uuid4().hex[:8]}@test.com",
        password_hash=get_password_hash("test-pass-audit-conc-123!"),
        role="user",
        is_active=True,
    )
    db_session.add(user)
    await db_session.flush()
    await db_session.commit()
    return user


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_session_patcher(session_factory):
    """Return a callable that mimics async_session() using the test DB factory."""

    def _factory():
        @asynccontextmanager
        async def _ctx():
            async with session_factory() as session:
                yield session

        return _ctx()

    return _factory


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.asyncio
async def test_audit_node_writes_row_per_invocation(session_factory, audit_user):
    """
    _audit_node must write exactly one audit row per call.

    Five concurrent calls to the same wrapped node must produce five
    independent rows — no silent failures from concurrent session access.
    """
    case_id = uuid.uuid4()

    async def noop_node(state: dict) -> dict:
        return {}

    def build_details(state: dict, result: dict) -> dict:
        return {"concurrency_test": True}

    wrapped = _audit_node(
        noop_node,
        action="concurrency_test",
        model_version="test-v1",
        build_details=build_details,
    )

    state = {
        "case_id": str(case_id),
        "user_id": str(audit_user.id),
    }

    session_patcher = _make_session_patcher(session_factory)

    with patch("app.orchestrator.graph.async_session", session_patcher):
        # Five concurrent audit writes — simulates parallel node completion
        await asyncio.gather(*[wrapped(state) for _ in range(5)])

    async with session_factory() as s:
        result = await s.execute(
            select(AuditLog).where(AuditLog.entity_id == case_id)
        )
        rows = result.scalars().all()

    assert len(rows) == 5, (
        f"Expected 5 audit rows from 5 concurrent calls, got {len(rows)}. "
        "_audit_node is failing silently under concurrent load — "
        "check that each call opens its own fresh DB session."
    )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_audit_node_survives_node_failure(session_factory, audit_user):
    """
    _audit_node is fail-open: a node that raises must still return something
    (the node exception propagates, audit never blocks clinical flow).

    If the wrapped node raises, _audit_node must NOT suppress it — but the
    audit path itself must not additionally fail when sessions are involved.
    """
    case_id = uuid.uuid4()

    async def failing_node(state: dict) -> dict:
        raise RuntimeError("Simulated node failure")

    wrapped = _audit_node(
        failing_node,
        action="fail_test",
        model_version="v-fail",
        build_details=lambda s, r: {},
    )

    state = {"case_id": str(case_id), "user_id": str(audit_user.id)}
    session_patcher = _make_session_patcher(session_factory)

    with patch("app.orchestrator.graph.async_session", session_patcher):
        with pytest.raises(RuntimeError, match="Simulated node failure"):
            await wrapped(state)

    # Audit row is NOT written if node itself fails (we audit the result, not the attempt)
    async with session_factory() as s:
        result = await s.execute(
            select(AuditLog).where(AuditLog.entity_id == case_id)
        )
        rows = result.scalars().all()

    assert len(rows) == 0, "Audit row must not be written when node raises"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_audit_node_fail_open_on_db_error(audit_user):
    """
    _audit_node is fail-open: if the DB write fails, the node result is
    still returned (clinical flow is not blocked).
    """
    case_id = uuid.uuid4()
    node_result = {"synthesized_response": "All good."}

    async def ok_node(state: dict) -> dict:
        return node_result

    wrapped = _audit_node(
        ok_node,
        action="db_fail_test",
        model_version="v1",
        build_details=lambda s, r: {},
    )

    state = {"case_id": str(case_id), "user_id": str(audit_user.id)}

    # Patch async_session to raise — simulates DB being down
    @asynccontextmanager
    async def broken_session():
        raise OSError("DB connection refused")
        yield  # unreachable — satisfies generator

    with patch("app.orchestrator.graph.async_session", lambda: broken_session()):
        result = await wrapped(state)

    # Clinical result must be returned even when audit DB is down
    assert result == node_result, (
        "_audit_node must be fail-open: node result must be returned "
        "even when the audit DB write fails."
    )
