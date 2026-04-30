"""
TDD — run_indexer: importable, returns stats dict, endpoint returns 202.

Strict TDD: these tests are written BEFORE the implementation (RED phase).
All three fail until run_indexer is added to kb_indexer.py.

Run: cd backend && poetry run pytest tests/test_kb_ingest.py -v
"""
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.main import app
from app.models.user import User

USER_ID = uuid.uuid4()
BASE_URL = "http://test"


def _make_admin():
    u = MagicMock(spec=User)
    u.id = USER_ID
    u.is_active = True
    u.role = "admin"
    return u


def _make_db():
    db = AsyncMock()
    db.add = MagicMock()
    db.commit = AsyncMock()
    db.flush = AsyncMock()
    db.execute = AsyncMock()
    return db


@pytest.fixture
def admin_client():
    mock_db = _make_db()

    async def _get_db():
        yield mock_db

    app.dependency_overrides[get_current_user] = lambda: _make_admin()
    app.dependency_overrides[get_db] = _get_db
    yield AsyncClient(transport=ASGITransport(app=app), base_url=BASE_URL)
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# T1 — run_indexer is importable (no ImportError)
# ---------------------------------------------------------------------------


def test_run_indexer_importable():
    """run_indexer must exist in kb_indexer — import must not raise ImportError."""
    from app.services.kb_indexer import run_indexer  # noqa: F401

    assert callable(run_indexer)


# ---------------------------------------------------------------------------
# T2 — run_indexer returns {indexed, skipped} when no articles fetched
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_indexer_no_articles_returns_zero_indexed():
    """run_indexer returns {indexed: 0, skipped: N} when fetch yields nothing."""
    from app.services.kb_indexer import run_indexer

    mock_db = AsyncMock()

    with (
        patch("app.services.kb_indexer.fetch_medlineplus", AsyncMock(return_value=[])),
        patch("app.core.database.async_session", return_value=mock_db),
    ):
        result = await run_indexer()

    assert isinstance(result, dict)
    assert "indexed" in result
    assert "skipped" in result
    assert result["indexed"] == 0


# ---------------------------------------------------------------------------
# T3 — POST /admin/kb/ingest returns 202 (run_indexer no longer missing)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_kb_ingest_endpoint_returns_202(admin_client):
    """POST /admin/kb/ingest must return 202 without crashing (no ImportError)."""
    with patch(
        "app.services.kb_indexer.run_indexer",
        AsyncMock(return_value={"indexed": 0, "skipped": 0}),
    ):
        async with admin_client as c:
            resp = await c.post("/api/v1/admin/kb/ingest")

    assert resp.status_code == 202
    data = resp.json()
    assert data["status"] == "accepted"
