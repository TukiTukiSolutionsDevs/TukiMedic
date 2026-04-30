"""
Application settings.

SECRET_KEY validation enforces a hard floor on entropy and rejects well-known
placeholder values. Boot fails loudly rather than running with a forgeable JWT
secret.

Generate a strong key with:
    python -c "import secrets; print(secrets.token_urlsafe(48))"

VAULT_MASTER_KEY must be a base64-encoded 32-byte AES-256 key. The app
refuses to start without it. Generate with:
    python -c "import os, base64; print(base64.b64encode(os.urandom(32)).decode())"
"""
import base64

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Substrings that almost certainly indicate an unset / placeholder secret.
_FORBIDDEN_SECRET_TOKENS = (
    "change-me",
    "changeme",
    "change_me",
    "default",
    "placeholder",
    "secret-key",
    "your-secret",
)

_MIN_SECRET_LEN = 32


class Settings(BaseSettings):
    PROJECT_NAME: str = "MedAgent"
    VERSION: str = "0.1.0"
    API_V1_PREFIX: str = "/api/v1"

    # Environment marker — drives the production guard below.
    ENVIRONMENT: str = "development"

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://medagent:medagent@localhost:5432/medagent"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # Auth
    SECRET_KEY: str = "change-me-in-production"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # LLM
    OPENAI_API_KEY: str = ""
    OPENAI_API_BASE: str = ""  # Optional: set to a proxy URL (e.g. Meridian shim)
    ANTHROPIC_API_KEY: str = ""
    LLM_MODEL: str = "gpt-4o-mini"  # Default model used by agents that don't override

    # Encrypted API key vault (S4.0.c)
    # Base64-encoded 32-byte AES-256-GCM master key. Required at boot.
    VAULT_MASTER_KEY: str = ""

    # S3/MinIO
    S3_ENDPOINT: str = "http://localhost:9000"
    S3_ACCESS_KEY: str = "minioadmin"
    S3_SECRET_KEY: str = "minioadmin"
    S3_BUCKET: str = "medagent-documents"

    # CORS
    ALLOWED_ORIGINS: list[str] = ["http://localhost:3000"]

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @field_validator("SECRET_KEY")
    @classmethod
    def _validate_secret_key(cls, v: str, info) -> str:
        environment = (info.data.get("ENVIRONMENT") or "development").lower()

        if not isinstance(v, str) or not v:
            raise ValueError("SECRET_KEY must be a non-empty string")

        if len(v) < _MIN_SECRET_LEN:
            raise ValueError(
                f"SECRET_KEY must be at least {_MIN_SECRET_LEN} characters. "
                "Generate one with: "
                "python -c \"import secrets; print(secrets.token_urlsafe(48))\""
            )

        lowered = v.lower()
        for token in _FORBIDDEN_SECRET_TOKENS:
            if token in lowered:
                raise ValueError(
                    f"SECRET_KEY contains forbidden placeholder token "
                    f"'{token}'. Generate a real secret with: "
                    "python -c \"import secrets; print(secrets.token_urlsafe(48))\""
                )

        # Extra entropy check in production: require enough distinct chars to
        # rule out trivial patterns (e.g. 'a'*64).
        if environment == "production" and len(set(v)) < 16:
            raise ValueError(
                "SECRET_KEY entropy too low for production. "
                "Generate one with: "
                "python -c \"import secrets; print(secrets.token_urlsafe(48))\""
            )

        return v

    @field_validator("VAULT_MASTER_KEY")
    @classmethod
    def _validate_vault_master_key(cls, v: str) -> str:
        if not v:
            raise ValueError(
                "VAULT_MASTER_KEY is required. Generate with: "
                'python -c "import os, base64; print(base64.b64encode(os.urandom(32)).decode())"'
            )
        try:
            key_bytes = base64.b64decode(v)
        except Exception:
            raise ValueError(
                "VAULT_MASTER_KEY must be a valid base64-encoded string. "
                'Generate with: python -c "import os, base64; print(base64.b64encode(os.urandom(32)).decode())"'
            )
        if len(key_bytes) != 32:
            raise ValueError(
                f"VAULT_MASTER_KEY must decode to exactly 32 bytes (AES-256); "
                f"got {len(key_bytes)}. "
                'Re-generate with: python -c "import os, base64; print(base64.b64encode(os.urandom(32)).decode())"'
            )
        return v


settings = Settings()
