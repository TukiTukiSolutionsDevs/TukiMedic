"""Admin-facing schemas."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel


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
