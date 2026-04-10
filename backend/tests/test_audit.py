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
    u.is_admin = True
    return u


def _make_regular_user():
    u = MagicMock(spec=User)
    u.id = USER_ID
    u.is_active = True
    u.is_admin = False
    return u


def _make_db():
    db = AsyncMock()
    db.add = MagicMock()
    db.flush = AsyncMock()
    db.commit = AsyncMock()
    db.execute = AsyncMock()
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

    assert entry.details == details
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
