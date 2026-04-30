"""TDD — S4.0.c-7,9: Encrypted API key vault admin endpoints.

Tests cover:
- POST /admin/credentials (create, masked response, activate flag)
- GET  /admin/credentials (list, always masked)
- PATCH /admin/credentials/{id}/rotate
- PATCH /admin/credentials/{id}/activate (single-active-per-provider invariant)
- DELETE /admin/credentials/{id}
- Audit log entry per write operation
- 403 for non-admin on every endpoint
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.main import app
from app.models.user import User

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ADMIN_ID = uuid.uuid4()
CRED_ID = uuid.uuid4()
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


def _make_cred(cred_id=None, provider="openai", label="Main key", is_active=True):
    c = MagicMock()
    c.id = cred_id or uuid.uuid4()
    c.provider = provider
    c.label = label
    c.is_active = is_active
    c.created_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
    c.rotated_at = None
    c.created_by_user_id = ADMIN_ID
    # Sensitive — must NEVER appear in API responses
    c.encrypted_key = b"\x01\x02\x03"
    c.iv = b"\x04\x05\x06"
    c.tag = b"\x07\x08\x09"
    return c


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
# S4.0.c-7: POST /admin/credentials
# ---------------------------------------------------------------------------


async def test_create_credential_success(admin_client, mock_db):
    async with admin_client as c:
        resp = await c.post(
            "/api/v1/admin/credentials",
            json={"provider": "openai", "label": "Main key", "plaintext_key": "sk-test123"},
        )

    assert resp.status_code == 201
    data = resp.json()
    assert data["provider"] == "openai"
    assert data["label"] == "Main key"
    assert "is_active" in data
    assert "id" in data


async def test_create_credential_response_never_exposes_key(admin_client, mock_db):
    """Raw key material must NEVER appear in the response."""
    async with admin_client as c:
        resp = await c.post(
            "/api/v1/admin/credentials",
            json={"provider": "openai", "label": "Prod", "plaintext_key": "sk-secret-key"},
        )

    assert resp.status_code == 201
    body = resp.json()
    # Field names forbidden in response
    for forbidden_field in ("encrypted_key", "iv", "tag", "plaintext_key"):
        assert forbidden_field not in body
    # Plaintext value must not appear in any string field
    for v in body.values():
        assert "sk-secret-key" not in str(v)


async def test_create_credential_requires_admin(customer_client):
    async with customer_client as c:
        resp = await c.post(
            "/api/v1/admin/credentials",
            json={"provider": "openai", "label": "k", "plaintext_key": "sk-x"},
        )
    assert resp.status_code == 403


async def test_create_credential_with_activate_flag(admin_client, mock_db):
    """Creating with activate=True immediately marks the credential active."""
    async with admin_client as c:
        resp = await c.post(
            "/api/v1/admin/credentials",
            json={
                "provider": "openai",
                "label": "k",
                "plaintext_key": "sk-x",
                "activate": True,
            },
        )

    assert resp.status_code == 201
    assert resp.json()["is_active"] is True


# ---------------------------------------------------------------------------
# S4.0.c-7: GET /admin/credentials
# ---------------------------------------------------------------------------


async def test_list_credentials_success(admin_client, mock_db):
    cred = _make_cred(cred_id=CRED_ID)
    rows_result = MagicMock()
    rows_result.scalars.return_value.all.return_value = [cred]
    mock_db.execute = AsyncMock(return_value=rows_result)

    async with admin_client as c:
        resp = await c.get("/api/v1/admin/credentials")

    assert resp.status_code == 200
    items = resp.json()["items"]
    assert len(items) == 1
    assert items[0]["provider"] == "openai"
    assert items[0]["label"] == "Main key"


async def test_list_credentials_never_exposes_raw_key(admin_client, mock_db):
    """GET items must never contain encrypted_key, iv, tag, or plaintext_key."""
    cred = _make_cred()
    rows_result = MagicMock()
    rows_result.scalars.return_value.all.return_value = [cred]
    mock_db.execute = AsyncMock(return_value=rows_result)

    async with admin_client as c:
        resp = await c.get("/api/v1/admin/credentials")

    for item in resp.json()["items"]:
        for forbidden in ("encrypted_key", "iv", "tag", "plaintext_key"):
            assert forbidden not in item


async def test_list_credentials_requires_admin(customer_client):
    async with customer_client as c:
        resp = await c.get("/api/v1/admin/credentials")
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# S4.0.c-7: PATCH /admin/credentials/{id}/rotate
# ---------------------------------------------------------------------------


async def test_rotate_credential_success(admin_client, mock_db):
    cred = _make_cred(cred_id=CRED_ID)
    fetch_result = MagicMock()
    fetch_result.scalar_one_or_none.return_value = cred
    mock_db.execute = AsyncMock(return_value=fetch_result)

    async with admin_client as c:
        resp = await c.patch(
            f"/api/v1/admin/credentials/{CRED_ID}/rotate",
            json={"plaintext_key": "sk-new-rotated-key"},
        )

    assert resp.status_code == 200
    body = resp.json()
    assert "encrypted_key" not in body
    assert "plaintext_key" not in body


async def test_rotate_credential_404(admin_client, mock_db):
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    mock_db.execute = AsyncMock(return_value=result)

    async with admin_client as c:
        resp = await c.patch(
            f"/api/v1/admin/credentials/{CRED_ID}/rotate",
            json={"plaintext_key": "sk-x"},
        )
    assert resp.status_code == 404


async def test_rotate_requires_admin(customer_client):
    async with customer_client as c:
        resp = await c.patch(
            f"/api/v1/admin/credentials/{CRED_ID}/rotate",
            json={"plaintext_key": "sk-x"},
        )
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# S4.0.c-9: PATCH /admin/credentials/{id}/activate
# ---------------------------------------------------------------------------


async def test_activate_credential_success(admin_client, mock_db):
    cred = _make_cred(cred_id=CRED_ID, is_active=False)
    fetch_result = MagicMock()
    fetch_result.scalar_one_or_none.return_value = cred
    # SELECT + UPDATE
    mock_db.execute = AsyncMock(side_effect=[fetch_result, MagicMock()])

    async with admin_client as c:
        resp = await c.patch(f"/api/v1/admin/credentials/{CRED_ID}/activate")

    assert resp.status_code == 200
    assert resp.json()["is_active"] is True


async def test_activate_deactivates_other_same_provider(admin_client, mock_db):
    """Activating a credential must issue an UPDATE to deactivate others for the provider."""
    cred = _make_cred(cred_id=CRED_ID, is_active=False, provider="gemini")
    fetch_result = MagicMock()
    fetch_result.scalar_one_or_none.return_value = cred
    mock_db.execute = AsyncMock(side_effect=[fetch_result, MagicMock()])

    async with admin_client as c:
        await c.patch(f"/api/v1/admin/credentials/{CRED_ID}/activate")

    # 1st execute = SELECT, 2nd execute = UPDATE (deactivate others)
    assert mock_db.execute.call_count == 2


async def test_activate_credential_404(admin_client, mock_db):
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    mock_db.execute = AsyncMock(return_value=result)

    async with admin_client as c:
        resp = await c.patch(f"/api/v1/admin/credentials/{CRED_ID}/activate")
    assert resp.status_code == 404


async def test_activate_requires_admin(customer_client):
    async with customer_client as c:
        resp = await c.patch(f"/api/v1/admin/credentials/{CRED_ID}/activate")
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# S4.0.c-7: DELETE /admin/credentials/{id}
# ---------------------------------------------------------------------------


async def test_delete_credential_success(admin_client, mock_db):
    cred = _make_cred(cred_id=CRED_ID)
    fetch_result = MagicMock()
    fetch_result.scalar_one_or_none.return_value = cred
    mock_db.execute = AsyncMock(return_value=fetch_result)

    async with admin_client as c:
        resp = await c.delete(f"/api/v1/admin/credentials/{CRED_ID}")
    assert resp.status_code == 204


async def test_delete_credential_404(admin_client, mock_db):
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    mock_db.execute = AsyncMock(return_value=result)

    async with admin_client as c:
        resp = await c.delete(f"/api/v1/admin/credentials/{CRED_ID}")
    assert resp.status_code == 404


async def test_delete_requires_admin(customer_client):
    async with customer_client as c:
        resp = await c.delete(f"/api/v1/admin/credentials/{CRED_ID}")
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# S4.0.c-9: Audit log entry per write
# ---------------------------------------------------------------------------


async def test_create_writes_audit_log(admin_client, mock_db):
    from app.models.audit_log import AuditLog

    async with admin_client as c:
        await c.post(
            "/api/v1/admin/credentials",
            json={"provider": "openai", "label": "k", "plaintext_key": "sk-x"},
        )

    mock_db.flush.assert_called()
    added = [call.args[0] for call in mock_db.add.call_args_list]
    audit_entries = [o for o in added if isinstance(o, AuditLog)]
    assert len(audit_entries) >= 1
    assert audit_entries[-1].entity_type == "api_key"


async def test_rotate_writes_audit_log(admin_client, mock_db):
    from app.models.audit_log import AuditLog

    cred = _make_cred(cred_id=CRED_ID)
    fetch_result = MagicMock()
    fetch_result.scalar_one_or_none.return_value = cred
    mock_db.execute = AsyncMock(return_value=fetch_result)

    async with admin_client as c:
        await c.patch(
            f"/api/v1/admin/credentials/{CRED_ID}/rotate",
            json={"plaintext_key": "sk-new"},
        )

    added = [call.args[0] for call in mock_db.add.call_args_list]
    audit_entries = [o for o in added if isinstance(o, AuditLog)]
    assert len(audit_entries) >= 1
    assert audit_entries[-1].entity_type == "api_key"


async def test_activate_writes_audit_log(admin_client, mock_db):
    from app.models.audit_log import AuditLog

    cred = _make_cred(cred_id=CRED_ID, is_active=False)
    fetch_result = MagicMock()
    fetch_result.scalar_one_or_none.return_value = cred
    mock_db.execute = AsyncMock(side_effect=[fetch_result, MagicMock()])

    async with admin_client as c:
        await c.patch(f"/api/v1/admin/credentials/{CRED_ID}/activate")

    added = [call.args[0] for call in mock_db.add.call_args_list]
    audit_entries = [o for o in added if isinstance(o, AuditLog)]
    assert len(audit_entries) >= 1
    assert audit_entries[-1].entity_type == "api_key"


async def test_delete_writes_audit_log(admin_client, mock_db):
    from app.models.audit_log import AuditLog

    cred = _make_cred(cred_id=CRED_ID)
    fetch_result = MagicMock()
    fetch_result.scalar_one_or_none.return_value = cred
    mock_db.execute = AsyncMock(return_value=fetch_result)

    async with admin_client as c:
        await c.delete(f"/api/v1/admin/credentials/{CRED_ID}")

    added = [call.args[0] for call in mock_db.add.call_args_list]
    audit_entries = [o for o in added if isinstance(o, AuditLog)]
    assert len(audit_entries) >= 1
    assert audit_entries[-1].entity_type == "api_key"


# ---------------------------------------------------------------------------
# S4.0.d-5: graph cache is cleared on every credential mutation
# ---------------------------------------------------------------------------


async def test_create_clears_graph_cache(admin_client, mock_db):
    """POST /admin/credentials must clear the graph cache so the new key is picked up."""
    with patch("app.api.v1.admin.clear_graph_cache") as mock_clear:
        async with admin_client as c:
            await c.post(
                "/api/v1/admin/credentials",
                json={"provider": "gemini", "label": "k", "plaintext_key": "sk-x"},
            )
    mock_clear.assert_called_once()


async def test_rotate_clears_graph_cache(admin_client, mock_db):
    """PATCH /rotate must clear the graph cache."""
    cred = _make_cred(cred_id=CRED_ID)
    fetch_result = MagicMock()
    fetch_result.scalar_one_or_none.return_value = cred
    mock_db.execute = AsyncMock(return_value=fetch_result)

    with patch("app.api.v1.admin.clear_graph_cache") as mock_clear:
        async with admin_client as c:
            await c.patch(
                f"/api/v1/admin/credentials/{CRED_ID}/rotate",
                json={"plaintext_key": "sk-new"},
            )
    mock_clear.assert_called_once()


async def test_activate_clears_graph_cache(admin_client, mock_db):
    """PATCH /activate must clear the graph cache."""
    cred = _make_cred(cred_id=CRED_ID, is_active=False)
    fetch_result = MagicMock()
    fetch_result.scalar_one_or_none.return_value = cred
    mock_db.execute = AsyncMock(side_effect=[fetch_result, MagicMock()])

    with patch("app.api.v1.admin.clear_graph_cache") as mock_clear:
        async with admin_client as c:
            await c.patch(f"/api/v1/admin/credentials/{CRED_ID}/activate")
    mock_clear.assert_called_once()


async def test_delete_clears_graph_cache(admin_client, mock_db):
    """DELETE /credentials/{id} must clear the graph cache."""
    cred = _make_cred(cred_id=CRED_ID)
    fetch_result = MagicMock()
    fetch_result.scalar_one_or_none.return_value = cred
    mock_db.execute = AsyncMock(return_value=fetch_result)

    with patch("app.api.v1.admin.clear_graph_cache") as mock_clear:
        async with admin_client as c:
            await c.delete(f"/api/v1/admin/credentials/{CRED_ID}")
    mock_clear.assert_called_once()
