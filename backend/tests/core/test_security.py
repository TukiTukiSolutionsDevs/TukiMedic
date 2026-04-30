"""
Tests for app.core.security — JWT (PyJWT) and password hashing.

These pin down the security contract after the python-jose -> PyJWT migration:
- HS256 only; alg confusion ('none', 'RS256') must be refused.
- Token type ('access' / 'refresh') survives roundtrip.
- Wrong secret, expired tokens, and tampered tokens are rejected.
- bcrypt password hash + verify roundtrip works.
"""
from datetime import timedelta

import jwt
import pytest

from app.core.config import settings
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    get_password_hash,
    verify_password,
)


def test_create_and_decode_access_token():
    token = create_access_token({"sub": "user-123"})
    payload = decode_token(token)
    assert payload["sub"] == "user-123"
    assert payload["type"] == "access"
    assert "exp" in payload


def test_create_and_decode_refresh_token():
    token = create_refresh_token({"sub": "user-abc"})
    payload = decode_token(token)
    assert payload["sub"] == "user-abc"
    assert payload["type"] == "refresh"


def test_decode_token_with_alg_none_rejected():
    """
    Algorithm confusion attack: a token forged with alg=none MUST be refused.
    PyJWT requires algorithms=[...] explicitly; this guards against the CVE
    that affected python-jose.
    """
    forged = jwt.encode({"sub": "attacker"}, "", algorithm="none")
    with pytest.raises(jwt.InvalidTokenError):
        decode_token(forged)


def test_decode_token_with_wrong_algorithm_rejected():
    """
    A token signed with an algorithm not in the allow-list must be refused.
    """
    forged = jwt.encode({"sub": "attacker"}, "x" * 64, algorithm="HS512")
    with pytest.raises(jwt.InvalidTokenError):
        decode_token(forged)


def test_decode_expired_token_rejected():
    expired = create_access_token({"sub": "u"}, expires_delta=timedelta(seconds=-10))
    with pytest.raises(jwt.InvalidTokenError):
        decode_token(expired)


def test_decode_token_with_wrong_secret_rejected():
    forged = jwt.encode(
        {"sub": "attacker", "type": "access"},
        "definitely-not-the-real-secret-key-but-long-enough",
        algorithm="HS256",
    )
    with pytest.raises(jwt.InvalidTokenError):
        decode_token(forged)


def test_decode_tampered_token_rejected():
    token = create_access_token({"sub": "user"})
    # Flip one char in the signature segment.
    head, payload, sig = token.split(".")
    bad_sig = ("A" if sig[0] != "A" else "B") + sig[1:]
    tampered = ".".join([head, payload, bad_sig])
    with pytest.raises(jwt.InvalidTokenError):
        decode_token(tampered)


def test_password_hash_and_verify():
    plain = "S3cret-Passw0rd!"
    hashed = get_password_hash(plain)
    assert hashed != plain
    assert verify_password(plain, hashed) is True
    assert verify_password("wrong-password", hashed) is False


def test_secret_key_is_not_placeholder():
    """Sanity: tests should never run with the placeholder secret."""
    assert "change-me" not in settings.SECRET_KEY.lower()
    assert len(settings.SECRET_KEY) >= 32
