"""S3/MinIO storage client placeholder."""

# Will be implemented in Phase 2 (Documents)
# For now, just the config structure


class StorageClient:
    def __init__(self):
        from app.core.config import settings

        self.endpoint = settings.S3_ENDPOINT
        self.access_key = settings.S3_ACCESS_KEY
        self.secret_key = settings.S3_SECRET_KEY
        self.bucket = settings.S3_BUCKET


storage_client = StorageClient()
