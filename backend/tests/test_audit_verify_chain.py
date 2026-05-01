"""
TDD — gap #4 follow-up: GET /admin/audit/verify-chain.

Walks the global audit hash chain and reports whether it is intact, plus
the ids of any rows whose previous_hash / inputs_hash / chain_hash do not
line up. Used by CI smoke and by ops monitoring.

Auth contract:
    - non-admin role → 403
    - invalid / missing bearer → 401 (or 403 from FastAPI HTTPBearer when no
      header at all; we test the invalid-token path which deterministically
      yields 401 from `decode_token`).

Response shape:
    {
        "ok": bool,
        "broken_ids": list[str],   # UUIDs serialised as strings
        "checked_at": str           # ISO-8601 UTC timestamp
    }
"""
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.main import app
from app.models.user import User

pytestmark = pytest.mark.asyncio

pytestmark = pytest.mark.asyncio

USER_ID = uuid.uuid4()
BASE_URL = "http://test"
ENDPOINT = "/api/v1/admin/audit/verify-chain"


# ---------------------------------------------------------------------------
# Helpers (mirror tests/test_admin_api.py to stay consistent)
# ---------------------------------------------------------------------------


def _make_admin() -> User:
    u = MagicMock(spec=User)
    u.id = USER_ID
    u.is_active = True
    u.role = "admin"
    return u


def _make_regular() -> User:
    u = MagicMock(spec=User)
    u.id = USER_ID
    u.is_active = True
    u.role = "customer"
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
def user_client(mock_db):
    async def _get_db():
        yield mock_db

    app.dependency_overrides[get_current_user] = lambda: _make_regular()
    app.dependency_overrides[get_db] = _get_db
    yield AsyncClient(transport=ASGITransport(app=app), base_url=BASE_URL)
    app.dependency_overrides.clear()


@pytest.fixture
def anon_client():
    """No dependency overrides — exercises the real auth dependency."""
    yield AsyncClient(transport=ASGITransport(app=app), base_url=BASE_URL)


# ---------------------------------------------------------------------------
# 1. Non-admin → 403
# ---------------------------------------------------------------------------


async def test_verify_chain_endpoint_admin_only(user_client):
    async with user_client as c:
        resp = await c.get(ENDPOINT)
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# 2. Clean chain → ok=True, broken_ids=[]
# ---------------------------------------------------------------------------


async def test_verify_chain_returns_ok_on_clean_chain(admin_client):
    with patch(
        "app.api.v1.admin.verify_chain",
        new=AsyncMock(return_value=(True, [])),
    ) as verify_mock:
        async with admin_client as c:
            resp = await c.get(ENDPOINT)

    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert data["broken_ids"] == []
    assert isinstance(data["checked_at"], str)
    # Sanity: looks like an ISO-8601 timestamp (YYYY-MM-DDTHH:MM:SS...)
    assert "T" in data["checked_at"]
    assert verify_mock.await_count == 1


# ---------------------------------------------------------------------------
# 3. Broken chain → ok=False, broken_ids=[uuid_str, ...]
# ---------------------------------------------------------------------------


async def test_verify_chain_detects_broken_chain(admin_client):
    broken_uuids = [uuid.uuid4(), uuid.uuid4()]
    with patch(
        "app.api.v1.admin.verify_chain",
        new=AsyncMock(return_value=(False, broken_uuids)),
    ):
        async with admin_client as c:
            resp = await c.get(ENDPOINT)

    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is False
    assert data["broken_ids"] == [str(b) for b in broken_uuids]
    # All ids must round-trip as valid UUID strings
    for b in data["broken_ids"]:
        uuid.UUID(b)
    assert isinstance(data["checked_at"], str)


# ---------------------------------------------------------------------------
# 4. Invalid bearer → 401 (decode_token rejects non-JWT)
# ---------------------------------------------------------------------------


async def test_verify_chain_unauthenticated_returns_401(anon_client):
    async with anon_client as c:
        resp = await c.get(
            ENDPOINT,
            headers={"Authorization": "Bearer not-a-real-token"},
        )
    assert resp.status_code == 401
