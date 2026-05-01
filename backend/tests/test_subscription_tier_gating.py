"""
TDD — hard blocker #1 (tier gating real).

Adds a FastAPI dependency `require_subscription_tier(min_tier)` that
gates endpoints by `User.subscription_tier`. Mapping:

    TIER_RANK = {"free": 0, "paid": 1}

A user satisfies a requirement when their rank >= the required rank.
Rejection is HTTP 403 with a stable machine-readable detail:

    {"code": "tier_required", "required_tier": <str>, "current_tier": <str>}

Endpoints gated in this batch (matrix decided 2026-05-01):
    - POST /api/v1/documents/upload      → paid
    - GET  /api/v1/cases/{id}/export/pdf → paid

Chat WS specialist gating is a separate batch (touches the orchestrator
graph, not a dep swap).
"""
from __future__ import annotations

import io
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import Depends, FastAPI
from httpx import ASGITransport, AsyncClient

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_subscription_tier
from app.main import app
from app.models.user import User

pytestmark = pytest.mark.asyncio

BASE_URL = "http://test"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_user(tier: str = "free", role: str = "customer") -> User:
    u = MagicMock(spec=User)
    u.id = uuid.uuid4()
    u.is_active = True
    u.role = role
    u.subscription_tier = tier
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
# 1-3. Dependency unit behaviour (mounted on a throwaway sub-app so we don't
# couple to any specific real endpoint for the pure dep contract).
# ---------------------------------------------------------------------------


def _make_sub_app(min_tier: str) -> FastAPI:
    sub = FastAPI()

    @sub.get("/probe")
    async def _probe(user: User = Depends(require_subscription_tier(min_tier))):
        return {"ok": True, "tier": user.subscription_tier}

    return sub


async def test_require_subscription_tier_blocks_free_when_paid_required():
    sub = _make_sub_app("paid")
    sub.dependency_overrides[get_current_user] = lambda: _make_user(tier="free")

    async with AsyncClient(transport=ASGITransport(app=sub), base_url=BASE_URL) as c:
        resp = await c.get("/probe")

    assert resp.status_code == 403
    body = resp.json()
    detail = body["detail"]
    assert detail["code"] == "tier_required"
    assert detail["required_tier"] == "paid"
    assert detail["current_tier"] == "free"


async def test_require_subscription_tier_allows_paid_when_paid_required():
    sub = _make_sub_app("paid")
    sub.dependency_overrides[get_current_user] = lambda: _make_user(tier="paid")

    async with AsyncClient(transport=ASGITransport(app=sub), base_url=BASE_URL) as c:
        resp = await c.get("/probe")

    assert resp.status_code == 200
    assert resp.json() == {"ok": True, "tier": "paid"}


async def test_tier_ordering_paid_satisfies_free_minimum():
    """A paid user must satisfy any endpoint that only requires free."""
    sub = _make_sub_app("free")
    sub.dependency_overrides[get_current_user] = lambda: _make_user(tier="paid")

    async with AsyncClient(transport=ASGITransport(app=sub), base_url=BASE_URL) as c:
        resp = await c.get("/probe")

    assert resp.status_code == 200


async def test_unknown_tier_treated_as_zero_and_blocked():
    """Defensive: garbage in DB must not silently grant access."""
    sub = _make_sub_app("paid")
    sub.dependency_overrides[get_current_user] = lambda: _make_user(tier="legacy_x")

    async with AsyncClient(transport=ASGITransport(app=sub), base_url=BASE_URL) as c:
        resp = await c.get("/probe")

    assert resp.status_code == 403
    assert resp.json()["detail"]["code"] == "tier_required"


# ---------------------------------------------------------------------------
# 4-5. POST /documents/upload gating
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_db():
    return _make_db()


@pytest.fixture
def free_client(mock_db):
    async def _get_db():
        yield mock_db

    app.dependency_overrides[get_current_user] = lambda: _make_user(tier="free")
    app.dependency_overrides[get_db] = _get_db
    yield AsyncClient(transport=ASGITransport(app=app), base_url=BASE_URL)
    app.dependency_overrides.clear()


@pytest.fixture
def paid_client(mock_db):
    async def _get_db():
        yield mock_db

    app.dependency_overrides[get_current_user] = lambda: _make_user(tier="paid")
    app.dependency_overrides[get_db] = _get_db
    yield AsyncClient(transport=ASGITransport(app=app), base_url=BASE_URL)
    app.dependency_overrides.clear()


# Minimal valid PNG (8-byte signature + IHDR for a 1x1 image).
_TINY_PNG = (
    b"\x89PNG\r\n\x1a\n"
    b"\x00\x00\x00\rIHDR"
    b"\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00"
    b"\x1f\x15\xc4\x89"
    b"\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01"
    b"\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
)


async def test_documents_upload_rejects_free_user(free_client):
    files = {"file": ("p.png", io.BytesIO(_TINY_PNG), "image/png")}
    async with free_client as c:
        resp = await c.post("/api/v1/documents/upload", files=files)

    assert resp.status_code == 403
    assert resp.json()["detail"]["code"] == "tier_required"


async def test_documents_upload_allows_paid_user(paid_client):
    """We don't assert on the success body — storage and bg task are mocked
    out — only that the tier gate doesn't fire (no 403)."""
    with patch(
        "app.api.v1.documents.storage_client.upload_file",
        new=AsyncMock(return_value=None),
    ), patch(
        "app.api.v1.documents._process_document_bg",
        new=AsyncMock(return_value=None),
    ):
        files = {"file": ("p.png", io.BytesIO(_TINY_PNG), "image/png")}
        async with paid_client as c:
            resp = await c.post("/api/v1/documents/upload", files=files)

    # Anything except 403 is fine for the gate test; the upload path itself
    # is exercised by test_documents.py / test_anamnesis.py.
    assert resp.status_code != 403


# ---------------------------------------------------------------------------
# 6-7. GET /cases/{case_id}/export/pdf gating
# ---------------------------------------------------------------------------


async def test_export_pdf_rejects_free_user(free_client):
    case_id = uuid.uuid4()
    async with free_client as c:
        resp = await c.get(f"/api/v1/cases/{case_id}/export/pdf")

    assert resp.status_code == 403
    assert resp.json()["detail"]["code"] == "tier_required"


async def test_export_pdf_allows_paid_user(paid_client, mock_db):
    """Paid user passes the tier gate. Beyond the gate we expect 404 because
    the mocked DB returns no Case — that's fine, the gate is what we test."""
    # db.execute().scalar_one_or_none() should yield None → 404 inside handler.
    scalar_result = MagicMock()
    scalar_result.scalar_one_or_none = MagicMock(return_value=None)
    mock_db.execute = AsyncMock(return_value=scalar_result)

    case_id = uuid.uuid4()
    async with paid_client as c:
        resp = await c.get(f"/api/v1/cases/{case_id}/export/pdf")

    assert resp.status_code != 403
