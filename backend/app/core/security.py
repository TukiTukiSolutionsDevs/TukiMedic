"""
Security primitives: JWT encode/decode (PyJWT) and bcrypt password hashing.

Migrated from python-jose to PyJWT — python-jose is unmaintained and carries
two unpatched CVEs (CVE-2024-33663, CVE-2024-33664). PyJWT requires the
`algorithms` allow-list on every decode, which closes the algorithm-confusion
attack (e.g. forging a token with alg=none).
"""
from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt
from passlib.context import CryptContext

from app.core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Single source of truth for the JWT signing algorithm.
JWT_ALGORITHM = "HS256"
_ALLOWED_ALGORITHMS = [JWT_ALGORITHM]


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire, "type": "access"})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=JWT_ALGORITHM)


def create_refresh_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(
        days=settings.REFRESH_TOKEN_EXPIRE_DAYS
    )
    to_encode.update({"exp": expire, "type": "refresh"})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=JWT_ALGORITHM)


def decode_token(token: str) -> dict:
    """
    Decode and verify a JWT.

    Raises:
        jwt.InvalidTokenError (or any subclass: ExpiredSignatureError,
        InvalidAlgorithmError, InvalidSignatureError, DecodeError, ...)
        on any verification failure.
    """
    return jwt.decode(token, settings.SECRET_KEY, algorithms=_ALLOWED_ALGORITHMS)
