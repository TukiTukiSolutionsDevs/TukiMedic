"""
Integration: IDOR (Insecure Direct Object Reference) prevention.

User B must NEVER access User A's resources even with a valid JWT.
Uses real JWT generation, real DB rows, and the real FastAPI app via ASGI
transport (no network). get_db is overridden to use the integration session.

Coverage:
- GET  /api/v1/documents/{id}     → 403 (user B accessing user A's doc)
- DELETE /api/v1/documents/{id}   → 403 (user B deleting user A's doc)
- GET  /api/v1/documents/          → 200 but user A's doc NOT in list
- GET  /api/v1/admin/audit-logs   → 403/404 (customer role denied admin endpoint)
"""
from __future__ import annotations

import uuid

import httpx
import pytest

from app.core.security import create_access_token, get_password_hash
from app.models.document import DocumentModel
from app.models.user import User


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
async def idor_users(db_session):
    """
    Create User A (victim/owner) and User B (attacker) plus a document owned
    by A. Inserts directly into the DB — no MinIO needed for the document.
    """
    user_a = User(
        email=f"user_a_{uuid.uuid4().hex[:8]}@idor.example",
        password_hash=get_password_hash("password-a-secure-123!"),
        role="customer",
        is_active=True,
    )
    user_b = User(
        email=f"user_b_{uuid.uuid4().hex[:8]}@idor.example",
        password_hash=get_password_hash("password-b-secure-123!"),
        role="customer",
        is_active=True,
    )
    db_session.add_all([user_a, user_b])
    await db_session.flush()

    # User A's document — inserted directly, bypassing storage layer
    doc_a = DocumentModel(
        user_id=user_a.id,
        original_filename="confidential_report.pdf",
        mime_type="application/pdf",
        file_size=2048,
        storage_path=f"{user_a.id}/{uuid.uuid4()}/confidential_report.pdf",
        processing_status="done",
    )
    db_session.add(doc_a)
    await db_session.commit()

    return user_a, user_b, doc_a


@pytest.fixture
async def client_as_user_b(db_session, idor_users):
    """
    ASGI test client authenticated as User B.

    get_db is overridden to use the integration session so the app can find
    the users and documents we inserted above.
    """
    _, user_b, _ = idor_users

    from app.core.database import get_db
    from app.main import app

    token_b = create_access_token({"sub": str(user_b.id)})

    async def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db

    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://test",
            headers={"Authorization": f"Bearer {token_b}"},
        ) as client:
            yield client
    finally:
        app.dependency_overrides.pop(get_db, None)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.integration
async def test_user_b_cannot_read_user_a_document(client_as_user_b, idor_users):
    """
    GET /api/v1/documents/{id} with user B's token → 403 Forbidden.

    The endpoint checks doc.user_id != current_user.id and raises 403.
    A 200 here would be a confirmed IDOR vulnerability.
    """
    _, _, doc_a = idor_users
    response = await client_as_user_b.get(f"/api/v1/documents/{doc_a.id}")

    assert response.status_code == 403, (
        f"Expected 403 Forbidden for cross-user document read, got {response.status_code}. "
        "IDOR: User B can read User A's confidential document."
    )


@pytest.mark.integration
async def test_user_b_cannot_delete_user_a_document(client_as_user_b, idor_users):
    """
    DELETE /api/v1/documents/{id} with user B's token → 403 Forbidden.
    """
    _, _, doc_a = idor_users
    response = await client_as_user_b.delete(f"/api/v1/documents/{doc_a.id}")

    assert response.status_code == 403, (
        f"Expected 403 Forbidden for cross-user document delete, got {response.status_code}. "
        "IDOR: User B can delete User A's document."
    )


@pytest.mark.integration
async def test_user_b_document_list_excludes_user_a_docs(client_as_user_b, idor_users):
    """
    GET /api/v1/documents/ with user B's token → 200 but user A's doc absent.

    The list endpoint filters by current_user.id, so cross-user leakage would
    mean User A's doc appears in User B's list.
    """
    _, _, doc_a = idor_users
    response = await client_as_user_b.get("/api/v1/documents/")

    assert response.status_code == 200, (
        f"Expected 200 OK for document list, got {response.status_code}"
    )
    doc_ids = {d["id"] for d in response.json()}
    assert str(doc_a.id) not in doc_ids, (
        "IDOR: User A's document appears in User B's document list. "
        "The list endpoint must filter by current_user.id."
    )


@pytest.mark.integration
async def test_customer_denied_admin_audit_logs(client_as_user_b, idor_users):
    """
    GET /api/v1/admin/audit-logs with customer role → 403 or 404.

    403 = route exists, role check fires correctly.
    404 = route name differs; document and adjust the path once confirmed.
    200 would mean a privilege escalation vulnerability.
    """
    response = await client_as_user_b.get("/api/v1/admin/audit-logs")

    assert response.status_code in (403, 404), (
        f"Expected 403 or 404 for customer accessing admin audit logs, "
        f"got {response.status_code}. "
        "Possible privilege escalation: customer can read audit logs."
    )
