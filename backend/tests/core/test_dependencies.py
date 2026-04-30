"""
Tests for app/core/dependencies.py — get_current_user.

This dependency guards EVERY authenticated endpoint, so the audit flagged
its lack of direct test coverage as a Tier-2 gap. We exercise the four
classes of failure a malicious or buggy client can present plus the
happy path.
"""
from __future__ import annotations

import uuid
from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from app.core.dependencies import get_current_user
from app.core.security import create_access_token, create_refresh_token


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_db_returning(user_obj):
    """AsyncMock db.execute(...) returning a result whose scalar_one_or_none gives user_obj."""
    db = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none = MagicMock(return_value=user_obj)
    db.execute = AsyncMock(return_value=result)
    return db


def _make_creds(token: str) -> HTTPAuthorizationCredentials:
    return HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_returns_user_with_valid_access_token():
    user_id = uuid.uuid4()
    token = create_access_token({"sub": str(user_id)})

    user = MagicMock()
    user.id = user_id
    user.is_active = True

    db = _make_db_returning(user)
    result = await get_current_user(credentials=_make_creds(token), db=db)
    assert result is user


# ---------------------------------------------------------------------------
# Token type guard
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_rejects_refresh_token():
    user_id = uuid.uuid4()
    refresh = create_refresh_token({"sub": str(user_id)})

    db = _make_db_returning(MagicMock(is_active=True))
    with pytest.raises(HTTPException) as exc:
        await get_current_user(credentials=_make_creds(refresh), db=db)
    assert exc.value.status_code == 401


# ---------------------------------------------------------------------------
# Token validity
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_rejects_garbage_token():
    db = _make_db_returning(MagicMock())
    with pytest.raises(HTTPException) as exc:
        await get_current_user(credentials=_make_creds("not-a-jwt"), db=db)
    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_rejects_expired_token():
    user_id = uuid.uuid4()
    expired = create_access_token(
        {"sub": str(user_id)}, expires_delta=timedelta(seconds=-3600)
    )
    db = _make_db_returning(MagicMock(is_active=True))
    with pytest.raises(HTTPException) as exc:
        await get_current_user(credentials=_make_creds(expired), db=db)
    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_rejects_token_without_sub():
    """A token signed by us but missing the subject claim must be rejected."""
    token = create_access_token({})  # no sub
    db = _make_db_returning(MagicMock())
    with pytest.raises(HTTPException) as exc:
        await get_current_user(credentials=_make_creds(token), db=db)
    assert exc.value.status_code == 401


# ---------------------------------------------------------------------------
# DB / user state
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_rejects_when_user_not_found():
    user_id = uuid.uuid4()
    token = create_access_token({"sub": str(user_id)})
    db = _make_db_returning(None)
    with pytest.raises(HTTPException) as exc:
        await get_current_user(credentials=_make_creds(token), db=db)
    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_rejects_inactive_user():
    user_id = uuid.uuid4()
    token = create_access_token({"sub": str(user_id)})
    inactive = MagicMock()
    inactive.id = user_id
    inactive.is_active = False
    db = _make_db_returning(inactive)
    with pytest.raises(HTTPException) as exc:
        await get_current_user(credentials=_make_creds(token), db=db)
    assert exc.value.status_code == 401
