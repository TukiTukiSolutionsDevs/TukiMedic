"""S3/MinIO storage client — boto3 (sync) wrapped with run_in_executor."""

import asyncio
from functools import partial

import boto3
from botocore.config import Config as BotoConfig

from app.core.config import settings


class StorageClient:
    def __init__(self) -> None:
        self._client = boto3.client(
            "s3",
            endpoint_url=settings.S3_ENDPOINT,
            aws_access_key_id=settings.S3_ACCESS_KEY,
            aws_secret_access_key=settings.S3_SECRET_KEY,
            config=BotoConfig(signature_version="s3v4"),
        )
        self._bucket = settings.S3_BUCKET

    async def upload_file(self, file_data: bytes, path: str, content_type: str) -> str:
        """Upload bytes to MinIO. Returns the storage path (object key)."""
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            partial(
                self._client.put_object,
                Bucket=self._bucket,
                Key=path,
                Body=file_data,
                ContentType=content_type,
            ),
        )
        return path

    async def download_file(self, path: str) -> bytes:
        """Download object from MinIO. Returns raw bytes."""
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            partial(self._client.get_object, Bucket=self._bucket, Key=path),
        )
        return response["Body"].read()

    async def delete_file(self, path: str) -> None:
        """Delete object from MinIO."""
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            partial(self._client.delete_object, Bucket=self._bucket, Key=path),
        )

    async def ensure_bucket(self) -> None:
        """Create bucket if it does not exist yet."""
        loop = asyncio.get_event_loop()
        try:
            await loop.run_in_executor(
                None,
                partial(self._client.head_bucket, Bucket=self._bucket),
            )
        except Exception:
            await loop.run_in_executor(
                None,
                partial(self._client.create_bucket, Bucket=self._bucket),
            )


storage_client = StorageClient()
