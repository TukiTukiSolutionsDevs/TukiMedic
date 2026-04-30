"""
Tests for app.core.config.Settings — SECRET_KEY validation guards.

These tests pin down the security contract:
- The default placeholder MUST be rejected when ENVIRONMENT="production".
- Anything shorter than 32 chars MUST be rejected globally.
- A strong random secret MUST be accepted.
"""
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
