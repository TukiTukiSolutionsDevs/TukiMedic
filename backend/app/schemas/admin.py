"""Admin-facing schemas."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, field_validator


class AdminUserResponse(BaseModel):
    id: uuid.UUID
    email: str
    display_name: Optional[str]
    role: str
    subscription_tier: str
    is_active: bool
    created_at: Optional[datetime]

    model_config = {"from_attributes": True}


class AdminUserPatch(BaseModel):
    role: Optional[str] = None
    subscription_tier: Optional[str] = None
    is_active: Optional[bool] = None

    @field_validator("subscription_tier")
    @classmethod
    def validate_tier(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in ("free", "paid"):
            raise ValueError(f"subscription_tier must be 'free' or 'paid', got {v!r}")
        return v

    @field_validator("role")
    @classmethod
    def validate_role(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in ("customer", "admin"):
            raise ValueError(f"role must be 'customer' or 'admin', got {v!r}")
        return v


# ---------------------------------------------------------------------------
# S4.0.c: Encrypted API key vault schemas
# ---------------------------------------------------------------------------


class CredentialCreate(BaseModel):
    provider: str
    label: str
    plaintext_key: str
    activate: bool = False  # immediately activate after creation


class CredentialRotate(BaseModel):
    plaintext_key: str
