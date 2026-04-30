"""
Unit tests for the /auth REST API.

Covers:
- happy-path login (200 + tokens)
- wrong-password rejection (401)
- per-IP rate limiting on /login (6th attempt within window -> 429)
- registration password-strength validation (422)
- refresh-token validation (401 on garbage token)

DB is fully mocked. We override `get_db` and the `User` lookup, and we drive
slowapi's storage from a dedicated fresh limiter so test isolation holds.
"""
import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.database import get_db
from app.core.rate_limit import limiter
from app.core.security import get_password_hash
from app.main import app

BASE_URL = "http://testserver"
USER_ID = uuid.uuid4()


def _make_user(password: str = "Correct-Horse-Battery-Staple-9"):
    user = MagicMock()
    user.id = USER_ID
    user.email = "doc@example.com"
    user.password_hash = get_password_hash(password)
    user.is_active = True
    user.display_name = "Dr Test"
    return user


def _make_db_returning(scalar_result):
    """
    Build an AsyncSession-shaped mock whose execute() returns a result whose
    scalar_one_or_none() yields `scalar_result`.
    """
    db = AsyncMock()
    db.add = MagicMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()

    res = MagicMock()
    res.scalar_one_or_none.return_value = scalar_result
    db.execute = AsyncMock(return_value=res)
    return db


@pytest.fixture(autouse=True)
def _reset_limiter_between_tests():
    """slowapi keeps in-process counters; reset before AND after each test."""
    limiter.reset()
    yield
    limiter.reset()


@pytest.fixture
def client_with_user():
    """Override get_db so /login finds a known user with a known password."""
    user = _make_user()
    db = _make_db_returning(user)

    async def _get_db():
        yield db

    app.dependency_overrides[get_db] = _get_db
    yield AsyncClient(transport=ASGITransport(app=app), base_url=BASE_URL), user
    app.dependency_overrides.clear()


@pytest.fixture
def client_no_user():
    db = _make_db_returning(None)

    async def _get_db():
        yield db

    app.dependency_overrides[get_db] = _get_db
    yield AsyncClient(transport=ASGITransport(app=app), base_url=BASE_URL)
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------

async def test_login_endpoint_works(client_with_user):
    client, user = client_with_user
    async with client as c:
        resp = await c.post(
            "/api/v1/auth/login",
            json={"email": user.email, "password": "Correct-Horse-Battery-Staple-9"},
        )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["access_token"]
    assert body["refresh_token"]
    assert body["token_type"] == "bearer"


async def test_login_wrong_password_returns_401(client_with_user):
    client, user = client_with_user
    async with client as c:
        resp = await c.post(
            "/api/v1/auth/login",
            json={"email": user.email, "password": "wrong-password-attempt"},
        )
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Rate limiting — login
# ---------------------------------------------------------------------------

async def test_login_rate_limited_after_5_attempts(client_no_user):
    """
    /auth/login is decorated with `5/minute`. From a single IP, the 6th
    attempt within a minute MUST be rejected with 429.
    """
    async with client_no_user as c:
        for _ in range(5):
            r = await c.post(
                "/api/v1/auth/login",
                json={"email": "nobody@example.com", "password": "whatever-is-fine"},
            )
            # First 5 must reach the handler — user not found -> 401
            assert r.status_code == 401, r.text

        sixth = await c.post(
            "/api/v1/auth/login",
            json={"email": "nobody@example.com", "password": "whatever-is-fine"},
        )
        assert sixth.status_code == 429, sixth.text


# ---------------------------------------------------------------------------
# Registration password strength
# ---------------------------------------------------------------------------

async def test_register_validates_password_strength(client_no_user):
    """A 4-char password is too weak — pydantic must reject with 422."""
    async with client_no_user as c:
        resp = await c.post(
            "/api/v1/auth/register",
            json={
                "email": "newuser@example.com",
                "password": "1234",
                "display_name": "Tester",
            },
        )
    assert resp.status_code == 422, resp.text
    body = resp.json()
    # Pydantic v2 returns {"detail":[{"loc":[...,"password"], ...}]}
    flat = str(body).lower()
    assert "password" in flat


# ---------------------------------------------------------------------------
# Refresh token validation
# ---------------------------------------------------------------------------

async def test_refresh_with_invalid_token_returns_401(client_no_user):
    async with client_no_user as c:
        resp = await c.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": "not-a-real-jwt"},
        )
    assert resp.status_code == 401
