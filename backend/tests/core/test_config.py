"""
Tests for app.core.config.Settings — SECRET_KEY validation guards.

These tests pin down the security contract:
- The default placeholder MUST be rejected when ENVIRONMENT="production".
- Anything shorter than 32 chars MUST be rejected globally.
- A strong random secret MUST be accepted.
"""
import os
import secrets

import pytest
from pydantic import ValidationError


def _build_settings(monkeypatch, **overrides):
    """
    Instantiate Settings with isolated env. Avoids leaking the real .env.
    """
    from app.core.config import Settings

    # Disable the .env file loading so monkeypatched vars are authoritative.
    monkeypatch.delenv("SECRET_KEY", raising=False)
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    for k, v in overrides.items():
        monkeypatch.setenv(k, v)

    return Settings(_env_file=None)


def test_secret_key_default_rejected_in_production(monkeypatch):
    """
    Catastrophic deploy guard: if ENVIRONMENT=production and SECRET_KEY is the
    documented placeholder, refuse to boot.
    """
    with pytest.raises((ValueError, ValidationError)):
        _build_settings(
            monkeypatch,
            ENVIRONMENT="production",
            SECRET_KEY="change-me-in-production",
        )


def test_secret_key_too_short_rejected(monkeypatch):
    """
    Reject anything below the 32-char floor, regardless of environment.
    """
    with pytest.raises((ValueError, ValidationError)):
        _build_settings(
            monkeypatch,
            ENVIRONMENT="development",
            SECRET_KEY="short",
        )


def test_secret_key_valid_accepted(monkeypatch):
    """
    A high-entropy random secret of >=32 chars is accepted, in both envs.
    """
    strong = secrets.token_urlsafe(48)  # > 32 chars

    s_dev = _build_settings(
        monkeypatch, ENVIRONMENT="development", SECRET_KEY=strong
    )
    assert s_dev.SECRET_KEY == strong

    s_prod = _build_settings(
        monkeypatch, ENVIRONMENT="production", SECRET_KEY=strong
    )
    assert s_prod.SECRET_KEY == strong


def test_secret_key_with_default_token_rejected(monkeypatch):
    """
    Even in dev, refuse obvious sentinel substrings to prevent copy-paste of
    placeholders into real environments.
    """
    with pytest.raises((ValueError, ValidationError)):
        _build_settings(
            monkeypatch,
            ENVIRONMENT="development",
            SECRET_KEY="changeme-changeme-changeme-changeme",  # 35 chars but contains 'changeme'
        )


# ---------------------------------------------------------------------------
# S4.0.c-5: VAULT_MASTER_KEY validation
# ---------------------------------------------------------------------------


def test_vault_master_key_empty_rejected(monkeypatch):
    """Empty VAULT_MASTER_KEY must be rejected — app must not boot without it."""
    import secrets as _secrets

    with pytest.raises((ValueError, ValidationError)):
        _build_settings(
            monkeypatch,
            ENVIRONMENT="test",
            SECRET_KEY=_secrets.token_urlsafe(48),
            VAULT_MASTER_KEY="",
        )


def test_vault_master_key_invalid_base64_rejected(monkeypatch):
    """Non-base64 VAULT_MASTER_KEY must be rejected."""
    import secrets as _secrets

    with pytest.raises((ValueError, ValidationError)):
        _build_settings(
            monkeypatch,
            ENVIRONMENT="test",
            SECRET_KEY=_secrets.token_urlsafe(48),
            VAULT_MASTER_KEY="not-valid-base64!!!",
        )


def test_vault_master_key_wrong_length_rejected(monkeypatch):
    """Base64 key that decodes to != 32 bytes must be rejected."""
    import base64
    import secrets as _secrets

    short = base64.b64encode(b"only16bytesshort").decode()  # 16 bytes, not 32
    with pytest.raises((ValueError, ValidationError)):
        _build_settings(
            monkeypatch,
            ENVIRONMENT="test",
            SECRET_KEY=_secrets.token_urlsafe(48),
            VAULT_MASTER_KEY=short,
        )


def test_vault_master_key_valid_accepted(monkeypatch):
    """A valid base64-encoded 32-byte VAULT_MASTER_KEY is accepted."""
    import base64
    import secrets as _secrets

    strong_secret = _secrets.token_urlsafe(48)
    valid_key = base64.b64encode(os.urandom(32)).decode()
    s = _build_settings(
        monkeypatch,
        ENVIRONMENT="test",
        SECRET_KEY=strong_secret,
        VAULT_MASTER_KEY=valid_key,
    )
    assert s.VAULT_MASTER_KEY == valid_key
