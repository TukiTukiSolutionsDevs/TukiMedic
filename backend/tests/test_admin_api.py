"""
TDD — Phase 5: Admin API endpoints.
All tests require admin user. Non-admin → 403.
"""
import json
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
USER_ID = uuid.uuid4()
KB_ID = uuid.uuid4()
BASE_URL = "http://test"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_admin():
    u = MagicMock(spec=User)
    u.id = USER_ID
    u.is_active = True
    u.is_admin = True
    return u


def _make_regular():
    u = MagicMock(spec=User)
    u.id = USER_ID
    u.is_active = True
    u.is_admin = False
    return u


def _make_db():
    db = AsyncMock()
    db.add = MagicMock()
    # AsyncSession.delete() IS awaitable in SQLAlchemy 2.0 — must be AsyncMock
    db.delete = AsyncMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    db.execute = AsyncMock()
    db.flush = AsyncMock()
    return db


def _make_kb_chunk():
    c = MagicMock()
    c.id = KB_ID
    c.source = "medlineplus"
    c.title = "Hypertension Overview"
    c.content = "Hypertension is high blood pressure..."
    c.chunk_index = 0
    c.specialty_tags = ["cardiology"]
    c.embedding = None
    c.created_at = datetime(2026, 4, 10, tzinfo=timezone.utc)
    return c


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

    app.dependency_overrides[get_current_user] = lambda: _make_admin()
    app.dependency_overrides[get_db] = _get_db
    yield AsyncClient(transport=ASGITransport(app=app), base_url=BASE_URL)
    app.dependency_overrides.clear()


@pytest.fixture
def user_client(mock_db):
    async def _get_db():
        yield mock_db

    app.dependency_overrides[get_current_user] = lambda: _make_regular()
    app.dependency_overrides[get_db] = _get_db
    yield AsyncClient(transport=ASGITransport(app=app), base_url=BASE_URL)
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# 1. test_metrics_returns_counts
# ---------------------------------------------------------------------------

async def test_metrics_returns_counts(admin_client, mock_db):
    # Each scalar() call returns a count value
    def _scalar_result(val):
        r = MagicMock()
        r.scalar.return_value = val
        return r

    def _all_result(rows):
        r = MagicMock()
        r.all.return_value = rows
        return r

    # Metrics does multiple aggregate queries — patch all execute calls
    mock_db.execute = AsyncMock(side_effect=[
        _scalar_result(42),   # total cases
        _scalar_result(15),   # total users
        _scalar_result(8),    # total documents
        _scalar_result(200),  # kb chunks
        _all_result([]),      # cases by status
        _all_result([]),      # triage distribution
    ])

    with (
        patch("app.api.v1.admin._get_cached_metrics", return_value=None),
        patch("app.api.v1.admin._cache_metrics"),
    ):
        async with admin_client as c:
            resp = await c.get("/api/v1/admin/metrics")

    assert resp.status_code == 200
    data = resp.json()
    assert "total_cases" in data
    assert "total_users" in data
    assert "total_documents" in data
    assert "kb_chunks" in data


# ---------------------------------------------------------------------------
# 2. test_metrics_requires_admin
# ---------------------------------------------------------------------------

async def test_metrics_requires_admin(user_client):
    async with user_client as c:
        resp = await c.get("/api/v1/admin/metrics")
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# 3. test_kb_list
# ---------------------------------------------------------------------------

async def test_kb_list(admin_client, mock_db):
    chunk = _make_kb_chunk()
    count_result = MagicMock()
    count_result.scalar.return_value = 1

    rows_result = MagicMock()
    rows_result.scalars.return_value.all.return_value = [chunk]

    mock_db.execute = AsyncMock(side_effect=[count_result, rows_result])

    async with admin_client as c:
        resp = await c.get("/api/v1/admin/kb")

    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert data["total"] == 1
    assert data["items"][0]["source"] == "medlineplus"


# ---------------------------------------------------------------------------
# 4. test_kb_add_chunk
# ---------------------------------------------------------------------------

async def test_kb_add_chunk(admin_client, mock_db):
    chunk = _make_kb_chunk()

    async def fake_refresh(obj):
        obj.id = KB_ID
        obj.created_at = datetime(2026, 4, 10, tzinfo=timezone.utc)

    mock_db.refresh = AsyncMock(side_effect=fake_refresh)

    with patch("app.api.v1.admin._generate_embedding", return_value=[0.1] * 1536):
        async with admin_client as c:
            resp = await c.post(
                "/api/v1/admin/kb",
                json={
                    "source": "medlineplus",
                    "title": "Hypertension Overview",
                    "content": "Hypertension is high blood pressure...",
                    "chunk_index": 0,
                    "specialty_tags": ["cardiology"],
                },
            )

    assert resp.status_code == 201
    data = resp.json()
    assert data["source"] == "medlineplus"


# ---------------------------------------------------------------------------
# 5. test_kb_delete_chunk
# ---------------------------------------------------------------------------

async def test_kb_delete_chunk(admin_client, mock_db):
    chunk = _make_kb_chunk()
    result = MagicMock()
    result.scalar_one_or_none.return_value = chunk
    mock_db.execute = AsyncMock(return_value=result)

    async with admin_client as c:
        resp = await c.delete(f"/api/v1/admin/kb/{KB_ID}")

    assert resp.status_code == 204
    mock_db.delete.assert_called_once_with(chunk)
    mock_db.commit.assert_called_once()


async def test_admin_delete_kb_entry_removes_row(admin_client, mock_db):
    """Regression: db.delete(chunk) MUST be awaited — otherwise SQLAlchemy 2.0
    AsyncSession returns a coroutine and the DELETE never reaches PostgreSQL."""
    chunk = _make_kb_chunk()
    result = MagicMock()
    result.scalar_one_or_none.return_value = chunk
    mock_db.execute = AsyncMock(return_value=result)

    async with admin_client as c:
        resp = await c.delete(f"/api/v1/admin/kb/{KB_ID}")

    assert resp.status_code == 204
    mock_db.delete.assert_awaited_once_with(chunk)
    mock_db.commit.assert_awaited_once()


# ---------------------------------------------------------------------------
# 6. test_kb_stats
# ---------------------------------------------------------------------------

async def test_kb_stats(admin_client, mock_db):
    # Returns rows of (source, count)
    rows_result = MagicMock()
    rows_result.all.return_value = [
        ("medlineplus", 150),
        ("vademecum", 50),
    ]
    mock_db.execute = AsyncMock(return_value=rows_result)

    async with admin_client as c:
        resp = await c.get("/api/v1/admin/kb/stats")

    assert resp.status_code == 200
    data = resp.json()
    assert "by_source" in data
    assert len(data["by_source"]) == 2


# ---------------------------------------------------------------------------
# 7. test_audit_log_endpoint
# ---------------------------------------------------------------------------

async def test_audit_log_endpoint(admin_client, mock_db):
    from tests.test_audit import _make_audit_row
    rows = [_make_audit_row("login"), _make_audit_row("register")]

    count_result = MagicMock()
    count_result.scalar.return_value = 2

    rows_result = MagicMock()
    rows_result.scalars.return_value.all.return_value = rows

    mock_db.execute = AsyncMock(side_effect=[count_result, rows_result])

    async with admin_client as c:
        resp = await c.get("/api/v1/admin/audit-log")

    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2
    assert len(data["items"]) == 2


# ---------------------------------------------------------------------------
# 8. test_non_admin_gets_403
# ---------------------------------------------------------------------------

async def test_non_admin_gets_403(user_client):
    async with user_client as c:
        r1 = await c.get("/api/v1/admin/metrics")
        r2 = await c.get("/api/v1/admin/kb")
        r3 = await c.delete(f"/api/v1/admin/kb/{KB_ID}")
        r4 = await c.get("/api/v1/admin/kb/stats")

    assert r1.status_code == 403
    assert r2.status_code == 403
    assert r3.status_code == 403
    assert r4.status_code == 403
