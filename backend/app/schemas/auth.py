import uuid

from pydantic import BaseModel, EmailStr, Field

# Hard floor for password length. 8 is the OWASP minimum baseline; the form
# ALSO needs to enforce complexity client-side, but server is authoritative.
MIN_PASSWORD_LEN = 8
MAX_PASSWORD_LEN = 128  # bcrypt's 72-byte limit + small headroom for unicode


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=MIN_PASSWORD_LEN, max_length=MAX_PASSWORD_LEN)
    display_name: str | None = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=MAX_PASSWORD_LEN)


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


class UserResponse(BaseModel):
    id: uuid.UUID
    email: str
    display_name: str | None
    is_verified: bool

    # Pydantic v2 serialises UUID -> str in JSON output automatically.
    model_config = {"from_attributes": True}
