"""
Unit tests for StorageClient (boto3 + run_in_executor).
All boto3 calls are mocked — no real S3/MinIO connection.
"""
import pytest
from unittest.mock import MagicMock, patch


@pytest.fixture
def mock_boto3_client():
    """Patched boto3 module-level, returns a mock S3 client."""
    with patch("app.core.storage.boto3") as mock_boto3:
        mock_client = MagicMock()
        mock_boto3.client.return_value = mock_client
        yield mock_client


@pytest.fixture
def storage(mock_boto3_client):
    """StorageClient with mocked boto3 and settings."""
    with patch("app.core.storage.settings") as mock_settings:
        mock_settings.S3_ENDPOINT = "http://localhost:9000"
        mock_settings.S3_ACCESS_KEY = "minioadmin"
        mock_settings.S3_SECRET_KEY = "minioadmin"
        mock_settings.S3_BUCKET = "tuki-docs"

        from app.core.storage import StorageClient

        client = StorageClient()
        # Inject the mock client directly so run_in_executor calls use it
        client._client = mock_boto3_client
        client._bucket = "tuki-docs"
        return client


async def test_upload_file(storage, mock_boto3_client):
    path = await storage.upload_file(b"file content", "user/doc/file.pdf", "application/pdf")

    mock_boto3_client.put_object.assert_called_once_with(
        Bucket="tuki-docs",
        Key="user/doc/file.pdf",
        Body=b"file content",
        ContentType="application/pdf",
    )
    assert path == "user/doc/file.pdf"


async def test_download_file(storage, mock_boto3_client):
    mock_body = MagicMock()
    mock_body.read.return_value = b"downloaded data"
    mock_boto3_client.get_object.return_value = {"Body": mock_body}

    result = await storage.download_file("user/doc/file.pdf")

    mock_boto3_client.get_object.assert_called_once_with(
        Bucket="tuki-docs", Key="user/doc/file.pdf"
    )
    assert result == b"downloaded data"


async def test_delete_file(storage, mock_boto3_client):
    await storage.delete_file("user/doc/file.pdf")

    mock_boto3_client.delete_object.assert_called_once_with(
        Bucket="tuki-docs", Key="user/doc/file.pdf"
    )


async def test_ensure_bucket_exists(storage, mock_boto3_client):
    """head_bucket succeeds → create_bucket is NOT called."""
    mock_boto3_client.head_bucket.return_value = {}

    await storage.ensure_bucket()

    mock_boto3_client.head_bucket.assert_called_once_with(Bucket="tuki-docs")
    mock_boto3_client.create_bucket.assert_not_called()


async def test_ensure_bucket_creates(storage, mock_boto3_client):
    """head_bucket raises → create_bucket IS called."""
    mock_boto3_client.head_bucket.side_effect = Exception("NoSuchBucket")

    await storage.ensure_bucket()

    mock_boto3_client.create_bucket.assert_called_once_with(Bucket="tuki-docs")
