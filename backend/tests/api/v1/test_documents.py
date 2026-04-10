"""
Unit tests for Documents REST API.
Storage and DB are fully mocked — no real MinIO or PostgreSQL.
"""
import uuid
import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.core.dependencies import get_current_user
from app.core.database import get_db
from app.models.user import User

# ---------------------------------------------------------------------------
# Magic bytes for MIME detection (filetype lib reads file signatures)
# ---------------------------------------------------------------------------
PDF_MAGIC = b"%PDF-1.4 " + b"fake pdf content " * 10
JPEG_MAGIC = b"\xff\xd8\xff\xe0" + b"\x00" * 200
PNG_MAGIC = b"\x89PNG\r\n\x1a\n" + b"\x00" * 200

USER_ID = uuid.uuid4()
OTHER_USER_ID = uuid.uuid4()
DOC_ID = uuid.uuid4()

BASE_URL = "http://test"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_user(user_id=USER_ID):
    user = MagicMock(spec=User)
    user.id = user_id
    user.is_active = True
    return user


def _make_doc(doc_id=DOC_ID, user_id=USER_ID, status="pending"):
    doc = MagicMock()
    doc.id = doc_id
    doc.user_id = user_id
    doc.original_filename = "test.pdf"
    doc.mime_type = "application/pdf"
    doc.file_size = len(PDF_MAGIC)
    doc.storage_path = f"{user_id}/{doc_id}/test.pdf"
    doc.doc_type = None
    doc.doc_type_confidence = None
    doc.processing_status = status
    doc.ocr_text = None
    doc.case_id = None
    doc.created_at = datetime(2026, 4, 10, 12, 0, 0, tzinfo=timezone.utc)
    return doc


def _make_db():
    db = AsyncMock()
    db.add = MagicMock()       # sync in SQLAlchemy
    db.delete = MagicMock()    # sync in SQLAlchemy
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    db.execute = AsyncMock()
    return db


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_user():
    return _make_user()


@pytest.fixture
def mock_db():
    return _make_db()


@pytest.fixture
def client(mock_user, mock_db):
    """Sync-style fixture: overrides deps, yields raw AsyncClient."""
    async def _get_db():
        yield mock_db

    app.dependency_overrides[get_current_user] = lambda: mock_user
    app.dependency_overrides[get_db] = _get_db
    yield AsyncClient(transport=ASGITransport(app=app), base_url=BASE_URL)
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Upload tests
# ---------------------------------------------------------------------------

async def test_upload_valid_pdf(client, mock_db):
    doc = _make_doc()
    mock_db.refresh = AsyncMock(side_effect=lambda d: None)

    with (
        patch("app.api.v1.documents.filetype") as mock_ft,
        patch("app.api.v1.documents.storage_client") as mock_storage,
        patch("app.api.v1.documents.uuid") as mock_uuid,
        patch("app.api.v1.documents._process_document_bg", new_callable=AsyncMock),
    ):
        mock_ft.guess.return_value = MagicMock(mime="application/pdf")
        mock_storage.upload_file = AsyncMock(return_value=doc.storage_path)
        mock_uuid.uuid4.return_value = DOC_ID

        # Simulate refresh populating doc fields on the created object
        async def fake_refresh(obj):
            obj.id = DOC_ID
            obj.processing_status = "pending"
            obj.created_at = doc.created_at
            obj.original_filename = "lab_result.pdf"
            obj.mime_type = "application/pdf"
            obj.file_size = len(PDF_MAGIC)

        mock_db.refresh = AsyncMock(side_effect=fake_refresh)

        async with client as c:
            response = await c.post(
                "/api/v1/documents/upload",
                files={"file": ("lab_result.pdf", PDF_MAGIC, "application/pdf")},
            )

    assert response.status_code == 201
    data = response.json()
    assert data["processing_status"] == "pending"
    assert data["original_filename"] == "lab_result.pdf"
    assert data["mime_type"] == "application/pdf"
    assert mock_db.add.call_count >= 1  # doc + audit log entry
    mock_db.commit.assert_called_once()  # single commit: doc + audit


async def test_upload_valid_image(client, mock_db):
    with (
        patch("app.api.v1.documents.filetype") as mock_ft,
        patch("app.api.v1.documents.storage_client") as mock_storage,
        patch("app.api.v1.documents._process_document_bg", new_callable=AsyncMock),
    ):
        mock_ft.guess.return_value = MagicMock(mime="image/jpeg")
        mock_storage.upload_file = AsyncMock()

        async def fake_refresh(obj):
            obj.id = DOC_ID
            obj.processing_status = "pending"
            obj.created_at = datetime(2026, 4, 10, tzinfo=timezone.utc)
            obj.original_filename = "scan.jpg"
            obj.mime_type = "image/jpeg"
            obj.file_size = len(JPEG_MAGIC)

        mock_db.refresh = AsyncMock(side_effect=fake_refresh)

        async with client as c:
            response = await c.post(
                "/api/v1/documents/upload",
                files={"file": ("scan.jpg", JPEG_MAGIC, "image/jpeg")},
            )

    assert response.status_code == 201
    assert response.json()["mime_type"] == "image/jpeg"


async def test_upload_too_large(client, mock_db):
    large_file = b"x" * (25 * 1024 * 1024)  # 25 MB — exceeds 20 MB limit

    with patch("app.api.v1.documents.filetype") as mock_ft:
        mock_ft.guess.return_value = MagicMock(mime="application/pdf")

        async with client as c:
            response = await c.post(
                "/api/v1/documents/upload",
                files={"file": ("big.pdf", large_file, "application/pdf")},
            )

    assert response.status_code == 413
    mock_db.add.assert_not_called()


async def test_upload_invalid_mime(client, mock_db):
    with patch("app.api.v1.documents.filetype") as mock_ft:
        mock_ft.guess.return_value = MagicMock(mime="application/x-msdownload")

        async with client as c:
            response = await c.post(
                "/api/v1/documents/upload",
                files={"file": ("malware.exe", b"MZ\x90\x00" + b"\x00" * 100, "application/octet-stream")},
            )

    assert response.status_code == 400
    mock_db.add.assert_not_called()


# ---------------------------------------------------------------------------
# List tests
# ---------------------------------------------------------------------------

async def test_list_documents(client, mock_db):
    doc = _make_doc()
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [doc]
    mock_db.execute = AsyncMock(return_value=mock_result)

    async with client as c:
        response = await c.get("/api/v1/documents/")

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 1
    assert data[0]["id"] == str(DOC_ID)
    assert data[0]["original_filename"] == "test.pdf"


async def test_list_documents_empty(client, mock_db):
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    mock_db.execute = AsyncMock(return_value=mock_result)

    async with client as c:
        response = await c.get("/api/v1/documents/")

    assert response.status_code == 200
    assert response.json() == []


# ---------------------------------------------------------------------------
# Get single document tests
# ---------------------------------------------------------------------------

async def test_get_document(client, mock_db):
    doc = _make_doc()

    # First execute → document, second execute → lab values
    doc_result = MagicMock()
    doc_result.scalar_one_or_none.return_value = doc

    lv_result = MagicMock()
    lv_result.scalars.return_value.all.return_value = []

    mock_db.execute = AsyncMock(side_effect=[doc_result, lv_result])

    async with client as c:
        response = await c.get(f"/api/v1/documents/{DOC_ID}")

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == str(DOC_ID)
    assert data["processing_status"] == "pending"
    assert data["lab_values"] == []


async def test_get_document_not_found(client, mock_db):
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_db.execute = AsyncMock(return_value=mock_result)

    async with client as c:
        response = await c.get(f"/api/v1/documents/{uuid.uuid4()}")

    assert response.status_code == 404


async def test_get_document_wrong_user(client, mock_db):
    """Document belongs to OTHER_USER_ID, current user is USER_ID → 403."""
    doc = _make_doc(user_id=OTHER_USER_ID)  # owned by someone else

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = doc
    mock_db.execute = AsyncMock(return_value=mock_result)

    async with client as c:
        response = await c.get(f"/api/v1/documents/{DOC_ID}")

    assert response.status_code == 403


# ---------------------------------------------------------------------------
# Delete tests
# ---------------------------------------------------------------------------

async def test_delete_document(client, mock_db):
    doc = _make_doc()

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = doc
    mock_db.execute = AsyncMock(return_value=mock_result)

    with patch("app.api.v1.documents.storage_client") as mock_storage:
        mock_storage.delete_file = AsyncMock()

        async with client as c:
            response = await c.delete(f"/api/v1/documents/{DOC_ID}")

    assert response.status_code == 204
    mock_storage.delete_file.assert_called_once_with(doc.storage_path)
    mock_db.delete.assert_called_once_with(doc)
    mock_db.commit.assert_called_once()
