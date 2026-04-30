"""ProviderCredential — encrypted API key for an LLM provider.

Fields:
- id:                   UUID primary key
- provider:             Provider name (e.g. "openai", "gemini", "anthropic")
- label:                Human-readable label (e.g. "Production key")
- encrypted_key:        AES-256-GCM encrypted API key bytes (BYTEA)
- iv:                   12-byte AES-GCM nonce (BYTEA)
- tag:                  16-byte GCM authentication tag (BYTEA)
- is_active:            Only the active credential is used by the LLM router
- created_at:           Creation timestamp
- rotated_at:           Timestamp of last key rotation (NULL if never rotated)
- created_by_user_id:   FK → users.id (SET NULL on user deletion)

Invariant: at most one active credential per provider enforced by a partial
unique index on (provider) WHERE is_active = true.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, LargeBinary, String, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ProviderCredential(Base):
    __tablename__ = "provider_credentials"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    provider: Mapped[str] = mapped_column(String(100), nullable=False)
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    encrypted_key: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    iv: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    tag: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    rotated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    __table_args__ = (
        # Partial unique index: at most ONE active credential per provider.
        Index(
            "uq_provider_credentials_active_provider",
            "provider",
            unique=True,
            postgresql_where=text("is_active = true"),
        ),
    )
