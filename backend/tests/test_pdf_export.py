"""
TDD — Phase 5: PDF Export service + endpoint.
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

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
USER_ID = uuid.uuid4()
OTHER_USER_ID = uuid.uuid4()
CASE_ID = uuid.uuid4()
BASE_URL = "http://test"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_user(user_id=USER_ID, is_admin=False):
    u = MagicMock(spec=User)
    u.id = user_id
    u.is_active = True
    u.role = "admin" if is_admin else "customer"
    u.display_name = "Test User"
    u.email = "test@example.com"
    return u


def _make_db():
    db = AsyncMock()
    db.add = MagicMock()
    db.execute = AsyncMock()
    return db


def _make_case(user_id=USER_ID):
    c = MagicMock()
    c.id = CASE_ID
    c.user_id = user_id
    c.title = "Test Clinical Case"
    c.chief_complaint = "Headache and fever"
    c.status = "active"
    c.triage_level = "YELLOW"
    c.triage_confidence = 0.85
    c.created_at = datetime(2026, 4, 10, tzinfo=timezone.utc)
    c.resolved_at = None
    return c


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_db():
    return _make_db()


@pytest.fixture
def client(mock_db):
    async def _get_db():
        yield mock_db

    app.dependency_overrides[get_current_user] = lambda: _make_user()
    app.dependency_overrides[get_db] = _get_db
    yield AsyncClient(transport=ASGITransport(app=app), base_url=BASE_URL)
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# 1. test_generate_case_pdf_returns_bytes
# ---------------------------------------------------------------------------

async def test_pdf_only_includes_labs_from_requested_case():
    """Regression: PDF lab query must filter by case_id, not only by user_id.
    Otherwise a patient with multiple cases sees ALL their labs in every PDF
    (PII leak across cases)."""
    from app.services.pdf_export import generate_case_pdf

    db = _make_db()
    case = _make_case()

    case_result = MagicMock()
    case_result.scalar_one_or_none.return_value = case

    empty_scalars = MagicMock()
    empty_scalars.scalars.return_value.all.return_value = []

    db.execute = AsyncMock(side_effect=[
        case_result,    # 1. case
        empty_scalars,  # 2. messages
        empty_scalars,  # 3. clinical facts
        empty_scalars,  # 4. labs       <-- the query under test
        empty_scalars,  # 5. timeline
    ])

    await generate_case_pdf(db, str(CASE_ID), str(USER_ID))

    # Inspect the 4th execute call — labs query.
    labs_call = db.execute.call_args_list[3]
    labs_stmt = labs_call.args[0]
    compiled = labs_stmt.compile()
    sql = str(compiled)

    assert "case_id" in sql.lower(), (
        f"PDF labs query must filter by case_id but SQL was:\n{sql}"
    )
    # Verify the bound case_id parameter equals the requested CASE_ID
    bound = {str(v) for v in compiled.params.values()}
    assert str(CASE_ID) in bound, (
        f"PDF labs query must bind the requested case_id ({CASE_ID}). "
        f"Bound params were: {bound}"
    )


async def test_generate_case_pdf_returns_bytes():
    from app.services.pdf_export import generate_case_pdf

    db = _make_db()
    case = _make_case()

    # case query
    case_result = MagicMock()
    case_result.scalar_one_or_none.return_value = case

    # messages query
    msgs_result = MagicMock()
    msgs_result.scalars.return_value.all.return_value = []

    # clinical facts query
    facts_result = MagicMock()
    facts_result.scalars.return_value.all.return_value = []

    # lab values query
    labs_result = MagicMock()
    labs_result.scalars.return_value.all.return_value = []

    # timeline query
    timeline_result = MagicMock()
    timeline_result.scalars.return_value.all.return_value = []

    db.execute = AsyncMock(side_effect=[
        case_result,
        msgs_result,
        facts_result,
        labs_result,
        timeline_result,
    ])

    pdf_bytes = await generate_case_pdf(db, str(CASE_ID), str(USER_ID))

    assert isinstance(pdf_bytes, bytes)
    assert len(pdf_bytes) > 100
    # PDF magic bytes
    assert pdf_bytes[:4] == b"%PDF"


# ---------------------------------------------------------------------------
# 2. test_export_endpoint_returns_pdf
# ---------------------------------------------------------------------------

async def test_export_endpoint_returns_pdf(client, mock_db):
    case = _make_case(user_id=USER_ID)

    with patch(
        "app.api.v1.export.generate_case_pdf",
        new_callable=AsyncMock,
        return_value=b"%PDF-1.4 fake-content",
    ):
        # Case ownership check
        case_result = MagicMock()
        case_result.scalar_one_or_none.return_value = case
        mock_db.execute = AsyncMock(return_value=case_result)

        async with client as c:
            resp = await c.get(f"/api/v1/cases/{CASE_ID}/export/pdf")

    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"
    assert "attachment" in resp.headers.get("content-disposition", "")


# ---------------------------------------------------------------------------
# 3. test_export_wrong_user_forbidden
# ---------------------------------------------------------------------------

async def test_export_wrong_user_forbidden(client, mock_db):
    case = _make_case(user_id=OTHER_USER_ID)  # owned by someone else

    case_result = MagicMock()
    case_result.scalar_one_or_none.return_value = case
    mock_db.execute = AsyncMock(return_value=case_result)

    async with client as c:
        resp = await c.get(f"/api/v1/cases/{CASE_ID}/export/pdf")

    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# 4. test_export_case_not_found
# ---------------------------------------------------------------------------

async def test_export_case_not_found(client, mock_db):
    case_result = MagicMock()
    case_result.scalar_one_or_none.return_value = None
    mock_db.execute = AsyncMock(return_value=case_result)

    async with client as c:
        resp = await c.get(f"/api/v1/cases/{uuid.uuid4()}/export/pdf")

    assert resp.status_code == 404
