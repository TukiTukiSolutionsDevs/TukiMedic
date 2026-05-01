"""
TDD — Phase 5: AuditLog service + admin audit-log endpoint.
Tests 1-3: pure service unit tests (no HTTP).
Tests 4-6: HTTP endpoint tests (admin/audit-log).
"""
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.models.audit_log import AuditLog
from app.services.audit import log_action

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
USER_ID = uuid.uuid4()
CASE_ID = uuid.uuid4()
BASE_URL = "http://test"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_admin_user():
    u = MagicMock(spec=User)
    u.id = USER_ID
    u.is_active = True
    u.role = "admin"
    return u


def _make_regular_user():
    u = MagicMock(spec=User)
    u.id = USER_ID
    u.is_active = True
    u.role = "customer"
    return u


def _make_db(chain_head: str | None = None):
    """Async-mock SQLAlchemy session.

    ``chain_head`` controls what ``_current_chain_head`` resolves to:
    - ``None`` (default) → empty chain → genesis ("0"*64)
    - any 64-char hex   → chain has one prior row with that chain_hash
    """
    db = AsyncMock()
    db.add = MagicMock()
    db.flush = AsyncMock()
    db.commit = AsyncMock()

    # Default execute returns a result whose scalar_one_or_none yields
    # ``chain_head`` (mimicking a 1-column SELECT against an empty or
    # populated table). HTTP endpoint tests override db.execute with a
    # side_effect list and do not exercise the chain code path.
    head_result = MagicMock()
    head_result.scalar_one_or_none = MagicMock(return_value=chain_head)
    db.execute = AsyncMock(return_value=head_result)
    return db


def _make_audit_row(action="login"):
    row = MagicMock()
    row.id = uuid.uuid4()
    row.user_id = USER_ID
    row.action = action
    row.entity_type = "user"
    row.entity_id = USER_ID
    row.details = None
    row.ip_address = "127.0.0.1"
    row.created_at = datetime(2026, 4, 10, 12, 0, 0, tzinfo=timezone.utc)
    return row


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_db():
    return _make_db()


@pytest.fixture
def admin_client(mock_db):
    async def _get_db():
        yield mock_db

    app.dependency_overrides[get_current_user] = lambda: _make_admin_user()
    app.dependency_overrides[get_db] = _get_db
    yield AsyncClient(transport=ASGITransport(app=app), base_url=BASE_URL)
    app.dependency_overrides.clear()


@pytest.fixture
def user_client(mock_db):
    async def _get_db():
        yield mock_db

    app.dependency_overrides[get_current_user] = lambda: _make_regular_user()
    app.dependency_overrides[get_db] = _get_db
    yield AsyncClient(transport=ASGITransport(app=app), base_url=BASE_URL)
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# 1. test_log_action_creates_entry
# ---------------------------------------------------------------------------

async def test_log_action_creates_entry():
    db = _make_db()
    user_id = uuid.uuid4()

    entry = await log_action(
        db=db,
        user_id=user_id,
        action="login",
        entity_type="user",
        entity_id=user_id,
        ip_address="127.0.0.1",
    )

    db.add.assert_called_once_with(entry)
    db.flush.assert_awaited_once()
    assert isinstance(entry, AuditLog)
    assert entry.action == "login"
    assert entry.user_id == user_id
    assert entry.ip_address == "127.0.0.1"
    # Chain wiring: genesis row when DB is empty.
    assert entry.previous_hash == "0" * 64
    assert isinstance(entry.chain_hash, str) and len(entry.chain_hash) == 64
    # inputs_hash is auto-synthesized for log_action so the chain has a
    # stable invariant per row even when callers pass no details.
    assert "inputs_hash" in entry.details
    assert len(entry.details["inputs_hash"]) == 64


# ---------------------------------------------------------------------------
# 2. test_log_action_with_details
# ---------------------------------------------------------------------------

async def test_log_action_with_details():
    db = _make_db()
    details = {"file": "report.pdf", "size": 1024}

    entry = await log_action(
        db=db,
        action="document_upload",
        entity_type="document",
        details=details,
    )

    # Caller-supplied keys must be preserved verbatim.
    assert entry.details["file"] == "report.pdf"
    assert entry.details["size"] == 1024
    # The chain wiring auto-injects inputs_hash so every audit row has a
    # stable invariant — see app/services/audit.py::log_action.
    assert "inputs_hash" in entry.details
    assert len(entry.details["inputs_hash"]) == 64
    assert entry.entity_type == "document"
    assert entry.action == "document_upload"


# ---------------------------------------------------------------------------
# 3. test_log_action_without_user
# ---------------------------------------------------------------------------

async def test_log_action_without_user():
    db = _make_db()

    entry = await log_action(db=db, action="kb_ingest")

    assert entry.user_id is None
    assert entry.action == "kb_ingest"
    assert entry.entity_type is None
    assert entry.entity_id is None


# ---------------------------------------------------------------------------
# 4. test_get_audit_log_paginated
# ---------------------------------------------------------------------------

async def test_get_audit_log_paginated(admin_client, mock_db):
    rows = [_make_audit_row("login") for _ in range(3)]

    # First execute: count, second execute: rows
    count_result = MagicMock()
    count_result.scalar.return_value = 25

    rows_result = MagicMock()
    rows_result.scalars.return_value.all.return_value = rows

    mock_db.execute = AsyncMock(side_effect=[count_result, rows_result])

    async with admin_client as c:
        resp = await c.get("/api/v1/admin/audit-log?page=1&page_size=3")

    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert data["total"] == 25
    assert len(data["items"]) == 3


# ---------------------------------------------------------------------------
# 5. test_get_audit_log_filter_action
# ---------------------------------------------------------------------------

async def test_get_audit_log_filter_action(admin_client, mock_db):
    rows = [_make_audit_row("login"), _make_audit_row("login")]

    count_result = MagicMock()
    count_result.scalar.return_value = 2

    rows_result = MagicMock()
    rows_result.scalars.return_value.all.return_value = rows

    mock_db.execute = AsyncMock(side_effect=[count_result, rows_result])

    async with admin_client as c:
        resp = await c.get("/api/v1/admin/audit-log?action=login")

    assert resp.status_code == 200
    for item in resp.json()["items"]:
        assert item["action"] == "login"


# ---------------------------------------------------------------------------
# 6. test_require_admin_blocks_non_admin
# ---------------------------------------------------------------------------

async def test_require_admin_blocks_non_admin(user_client):
    async with user_client as c:
        resp = await c.get("/api/v1/admin/audit-log")

    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Fix A.4 — clinical decision auditing
# ---------------------------------------------------------------------------


def _async_session_cm(db):
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=db)
    cm.__aexit__ = AsyncMock(return_value=False)
    return cm


async def test_log_clinical_decision_persists_with_hash_and_version():
    from app.services.audit import log_clinical_decision

    db = _make_db()
    case_id = uuid.uuid4()
    entry = await log_clinical_decision(
        db,
        case_id=case_id,
        action="triage_decision",
        details={"urgency_level": "yellow", "red_flags_detected": ["dolor"]},
        model_version="gpt-4o-mini@triage",
    )
    assert isinstance(entry, AuditLog)
    assert entry.action == "triage_decision"
    assert entry.entity_type == "case"
    assert entry.entity_id == case_id
    assert entry.details["urgency_level"] == "yellow"
    assert entry.details["model_version"] == "gpt-4o-mini@triage"
    assert "inputs_hash" in entry.details
    assert len(entry.details["inputs_hash"]) == 64
    # Chain wiring
    assert entry.previous_hash == "0" * 64
    assert isinstance(entry.chain_hash, str) and len(entry.chain_hash) == 64


async def test_triage_decision_logged():
    from app.orchestrator.graph import _audit_node, _triage_details, TRIAGE_MODEL

    db = _make_db()

    async def fake_triage(state):
        return {
            "triage_level": "yellow",
            "red_flags": ["dolor torácico"],
            "triage_confidence": 0.85,
            "current_node": "triage",
        }

    state = {"case_id": str(uuid.uuid4()), "current_message": "duele el pecho"}

    with patch("app.orchestrator.graph.async_session", MagicMock(return_value=_async_session_cm(db))):
        wrapped = _audit_node(
            fake_triage,
            action="triage_decision",
            model_version=TRIAGE_MODEL,
            build_details=_triage_details,
        )
        result = await wrapped(state)

    assert result["triage_level"] == "yellow"
    db.add.assert_called_once()
    entry = db.add.call_args.args[0]
    assert isinstance(entry, AuditLog)
    assert entry.action == "triage_decision"
    assert entry.details["urgency_level"] == "yellow"
    assert entry.details["red_flags_detected"] == ["dolor torácico"]
    assert entry.details["model_version"] == TRIAGE_MODEL
    assert "inputs_hash" in entry.details


async def test_guardrail_violation_logged():
    from app.orchestrator.graph import _audit_node, _guardrail_details, GUARDRAIL_MODEL

    db = _make_db()

    async def fake_guardrail(state):
        return {
            "guardrail_violations": [{"violation_type": "definitive_diagnosis", "severity": "high"}],
            "guardrail_interrupt": False,
            "current_node": "guardrail",
        }

    state = {"case_id": str(uuid.uuid4())}

    with patch("app.orchestrator.graph.async_session", MagicMock(return_value=_async_session_cm(db))):
        wrapped = _audit_node(
            fake_guardrail,
            action="guardrail_violation",
            model_version=GUARDRAIL_MODEL,
            build_details=_guardrail_details,
        )
        await wrapped(state)

    db.add.assert_called_once()
    entry = db.add.call_args.args[0]
    assert entry.action == "guardrail_violation"
    assert len(entry.details["violations"]) == 1
    assert entry.details["interrupt"] is False
    assert entry.details["model_version"] == GUARDRAIL_MODEL
    assert "inputs_hash" in entry.details


async def test_synthesis_logged():
    from app.orchestrator.graph import _audit_node, _synthesizer_details, SYNTHESIZER_MODEL

    db = _make_db()
    response = "Te recomendamos consultar a tu médico.\n\n---\n\nDisclaimer."

    async def fake_synth(state):
        return {
            "synthesized_response": response,
            "attention_level": "24-48h",
            "current_node": "synthesizer",
        }

    state = {"case_id": str(uuid.uuid4())}

    with patch("app.orchestrator.graph.async_session", MagicMock(return_value=_async_session_cm(db))):
        wrapped = _audit_node(
            fake_synth,
            action="response_synthesized",
            model_version=SYNTHESIZER_MODEL,
            build_details=_synthesizer_details,
        )
        await wrapped(state)

    db.add.assert_called_once()
    entry = db.add.call_args.args[0]
    assert entry.action == "response_synthesized"
    assert entry.details["attention_level"] == "24-48h"
    assert entry.details["response_length"] == len(response)
    assert entry.details["model_version"] == SYNTHESIZER_MODEL
    assert "inputs_hash" in entry.details


async def test_audit_failure_does_not_block_node():
    from app.orchestrator.graph import _audit_node, _triage_details, TRIAGE_MODEL

    async def fake_triage(state):
        return {"triage_level": "green", "red_flags": [], "current_node": "triage"}

    state = {"case_id": str(uuid.uuid4())}

    def boom(*args, **kwargs):
        raise RuntimeError("DB unavailable")

    with patch("app.orchestrator.graph.async_session", boom):
        wrapped = _audit_node(
            fake_triage,
            action="triage_decision",
            model_version=TRIAGE_MODEL,
            build_details=_triage_details,
        )
        result = await wrapped(state)
    assert result["triage_level"] == "green"
