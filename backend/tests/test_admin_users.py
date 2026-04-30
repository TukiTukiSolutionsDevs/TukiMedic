"""TDD — S4.0.b: Admin user management (list, get, patch, guard, audit)."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
ADMIN_ID = uuid.uuid4()
TARGET_ID = uuid.uuid4()
BASE_URL = "http://test"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_admin():
    u = MagicMock(spec=User)
    u.id = ADMIN_ID
    u.is_active = True
    u.role = "admin"
    return u


def _make_customer():
    u = MagicMock(spec=User)
    u.id = uuid.uuid4()
    u.is_active = True
    u.role = "customer"
    return u


def _make_user_row(user_id=None, role="customer", is_active=True):
    u = MagicMock()
    u.id = user_id or uuid.uuid4()
    u.email = "user@example.com"
    u.display_name = "Test User"
    u.role = role
    u.subscription_tier = "free"
    u.is_active = is_active
    u.created_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
    return u


def _make_db():
    db = AsyncMock()
    db.add = MagicMock()
    db.delete = AsyncMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    db.execute = AsyncMock()
    db.flush = AsyncMock()
    return db


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
def customer_client(mock_db):
    async def _get_db():
        yield mock_db

    app.dependency_overrides[get_current_user] = lambda: _make_customer()
    app.dependency_overrides[get_db] = _get_db
    yield AsyncClient(transport=ASGITransport(app=app), base_url=BASE_URL)
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# S4.0.b-1 — Test admin users listing
# ---------------------------------------------------------------------------


async def test_list_users_returns_paginated_list(admin_client, mock_db):
    user = _make_user_row()
    count_result = MagicMock()
    count_result.scalar.return_value = 1
    rows_result = MagicMock()
    rows_result.scalars.return_value.all.return_value = [user]
    mock_db.execute = AsyncMock(side_effect=[count_result, rows_result])

    async with admin_client as c:
        resp = await c.get("/api/v1/admin/users")

    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["page"] == 1
    assert len(data["items"]) == 1
    item = data["items"][0]
    assert item["email"] == user.email
    assert "role" in item
    assert "subscription_tier" in item
    assert "is_active" in item


async def test_list_users_requires_admin(customer_client):
    async with customer_client as c:
        resp = await c.get("/api/v1/admin/users")
    assert resp.status_code == 403


async def test_get_user_returns_single_user(admin_client, mock_db):
    user = _make_user_row(user_id=TARGET_ID)
    result = MagicMock()
    result.scalar_one_or_none.return_value = user
    mock_db.execute = AsyncMock(return_value=result)

    async with admin_client as c:
        resp = await c.get(f"/api/v1/admin/users/{TARGET_ID}")

    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == str(TARGET_ID)
    assert data["email"] == user.email


async def test_get_user_404(admin_client, mock_db):
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    mock_db.execute = AsyncMock(return_value=result)

    async with admin_client as c:
        resp = await c.get(f"/api/v1/admin/users/{TARGET_ID}")

    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# S4.0.b-3 — Test admin user patching
# ---------------------------------------------------------------------------


async def test_patch_user_updates_fields(admin_client, mock_db):
    user = _make_user_row(user_id=TARGET_ID, role="customer")
    fetch_result = MagicMock()
    fetch_result.scalar_one_or_none.return_value = user
    mock_db.execute = AsyncMock(return_value=fetch_result)

    async with admin_client as c:
        resp = await c.patch(
            f"/api/v1/admin/users/{TARGET_ID}",
            json={"subscription_tier": "pro", "is_active": False},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == str(TARGET_ID)
    assert "role" in data
    assert "subscription_tier" in data
    assert "is_active" in data


async def test_patch_user_requires_admin(customer_client):
    async with customer_client as c:
        resp = await c.patch(
            f"/api/v1/admin/users/{TARGET_ID}",
            json={"is_active": False},
        )
    assert resp.status_code == 403


async def test_patch_user_not_found(admin_client, mock_db):
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    mock_db.execute = AsyncMock(return_value=result)

    async with admin_client as c:
        resp = await c.patch(
            f"/api/v1/admin/users/{TARGET_ID}",
            json={"is_active": False},
        )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# S4.0.b-5 — Test last-admin demotion guard
# ---------------------------------------------------------------------------


async def test_last_admin_demotion_rejected(admin_client, mock_db):
    """Only remaining admin cannot be demoted — returns 409."""
    user = _make_user_row(user_id=TARGET_ID, role="admin")
    fetch_result = MagicMock()
    fetch_result.scalar_one_or_none.return_value = user

    count_result = MagicMock()
    count_result.scalar.return_value = 1  # only one admin left

    mock_db.execute = AsyncMock(side_effect=[fetch_result, count_result])

    async with admin_client as c:
        resp = await c.patch(
            f"/api/v1/admin/users/{TARGET_ID}",
            json={"role": "customer"},
        )

    assert resp.status_code == 409
    assert "last admin" in resp.json()["detail"].lower()


async def test_non_last_admin_demotion_allowed(admin_client, mock_db):
    """Demoting an admin when multiple admins exist succeeds."""
    user = _make_user_row(user_id=TARGET_ID, role="admin")
    fetch_result = MagicMock()
    fetch_result.scalar_one_or_none.return_value = user

    count_result = MagicMock()
    count_result.scalar.return_value = 2  # two admins — safe to demote one

    mock_db.execute = AsyncMock(side_effect=[fetch_result, count_result])

    async with admin_client as c:
        resp = await c.patch(
            f"/api/v1/admin/users/{TARGET_ID}",
            json={"role": "customer"},
        )

    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# S4.0.b-7 — Test concurrent admin demotion guard
# ---------------------------------------------------------------------------


async def test_concurrent_demotion_at_least_one_409(admin_client, mock_db):
    """Two concurrent PATCH demotions of the last admin — at least one must 409."""
    import asyncio

    user = _make_user_row(user_id=TARGET_ID, role="admin")

    # A single shared result that works for both fetch (.scalar_one_or_none)
    # and count (.scalar) calls — both requests see count=1 (last admin).
    shared_result = MagicMock()
    shared_result.scalar_one_or_none.return_value = user
    shared_result.scalar.return_value = 1
    mock_db.execute = AsyncMock(return_value=shared_result)

    async with admin_client as c:
        r1, r2 = await asyncio.gather(
            c.patch(f"/api/v1/admin/users/{TARGET_ID}", json={"role": "customer"}),
            c.patch(f"/api/v1/admin/users/{TARGET_ID}", json={"role": "customer"}),
        )

    assert r1.status_code == 409 or r2.status_code == 409, (
        f"Expected at least one 409, got {r1.status_code} and {r2.status_code}"
    )


# ---------------------------------------------------------------------------
# S4.0.b-9 — Test user management audit logs
# ---------------------------------------------------------------------------


async def test_patch_user_writes_audit_log(admin_client, mock_db):
    """Successful PATCH writes an audit_log entry with entity_type=user."""
    from app.models.audit_log import AuditLog

    user = _make_user_row(user_id=TARGET_ID, role="customer")
    fetch_result = MagicMock()
    fetch_result.scalar_one_or_none.return_value = user
    mock_db.execute = AsyncMock(return_value=fetch_result)

    async with admin_client as c:
        resp = await c.patch(
            f"/api/v1/admin/users/{TARGET_ID}",
            json={"subscription_tier": "pro"},
        )

    assert resp.status_code == 200
    mock_db.flush.assert_called()
    added_objects = [call.args[0] for call in mock_db.add.call_args_list]
    audit_entries = [o for o in added_objects if isinstance(o, AuditLog)]
    assert len(audit_entries) >= 1
    entry = audit_entries[-1]
    assert entry.entity_type == "user"
    assert entry.action == "user_patch"
