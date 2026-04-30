"""
Integration test fixtures — real PostgreSQL, Redis, and MinIO containers.

Run with:
    RUN_INTEGRATION=1 poetry run pytest -m integration
    # or: poetry run pytest tests/integration/ --integration

Default suite (poetry run pytest) SKIPS these automatically — no Docker required.
"""
from __future__ import annotations

import base64
import os
import secrets

# Env vars MUST be set before any app.* import.
# Root conftest.py already does this; these setdefault calls are a safety net
# for direct invocation (e.g. pytest tests/integration/ without root conftest).
os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("SECRET_KEY", secrets.token_urlsafe(48))
os.environ.setdefault("VAULT_MASTER_KEY", base64.b64encode(os.urandom(32)).decode())

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
ALEMBIC_INI = os.path.join(_BACKEND_DIR, "alembic.ini")


# ---------------------------------------------------------------------------
# URL helpers (also used by test_migrations_real.py)
# ---------------------------------------------------------------------------


def make_sync_url(raw: str) -> str:
    """Normalize testcontainers URL to a psycopg2-compatible postgresql:// URL.

    testcontainers returns e.g. postgresql+psycopg2://user:pass@host:port/db.
    Alembic's env.py expects postgresql://... (bare scheme, no driver suffix).
    """
    if "+" in raw.split("://")[0]:
        scheme, rest = raw.split("://", 1)
        base = scheme.split("+")[0]
        return f"{base}://{rest}"
    return raw


def make_async_url(sync_url: str) -> str:
    """Convert postgresql://... to postgresql+asyncpg://... for SQLAlchemy async."""
    return sync_url.replace("postgresql://", "postgresql+asyncpg://", 1)


# ---------------------------------------------------------------------------
# Container fixtures (session-scoped — one container per test session)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def pg_container():
    """PostgreSQL 16 + pgvector.

    Uses pgvector/pgvector:pg16 so the vector extension is available for
    migrations that create HNSW/IVFFlat indexes on embedding columns.
    """
    try:
        from testcontainers.postgres import PostgresContainer
    except ImportError:
        pytest.skip("testcontainers not installed — pip install testcontainers[postgres]")

    try:
        with PostgresContainer("pgvector/pgvector:pg16") as pg:
            yield pg
    except Exception as exc:
        if any(k in str(exc).lower() for k in ("docker", "connection", "socket")):
            pytest.skip(f"Docker not available: {exc}")
        raise


@pytest.fixture(scope="session")
def redis_container():
    """Redis 7 container."""
    try:
        from testcontainers.redis import RedisContainer
    except ImportError:
        pytest.skip("testcontainers not installed — pip install testcontainers[redis]")

    try:
        with RedisContainer("redis:7-alpine") as redis:
            yield redis
    except Exception as exc:
        if any(k in str(exc).lower() for k in ("docker", "connection", "socket")):
            pytest.skip(f"Docker not available: {exc}")
        raise


@pytest.fixture(scope="session")
def minio_container():
    """MinIO container."""
    try:
        from testcontainers.minio import MinioContainer
    except ImportError:
        pytest.skip("testcontainers not installed — pip install testcontainers[minio]")

    try:
        with MinioContainer("minio/minio:latest") as minio:
            yield minio
    except Exception as exc:
        if any(k in str(exc).lower() for k in ("docker", "connection", "socket")):
            pytest.skip(f"Docker not available: {exc}")
        raise


# ---------------------------------------------------------------------------
# Database fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def pg_sync_url(pg_container) -> str:
    return make_sync_url(pg_container.get_connection_url())


@pytest.fixture(scope="session")
def pg_async_url(pg_sync_url) -> str:
    return make_async_url(pg_sync_url)


@pytest.fixture(scope="session")
def run_migrations(pg_sync_url):
    """Run alembic upgrade head once per session.

    Temporarily patches app.core.config.settings.DATABASE_URL so alembic's
    env.py picks up the container URL instead of the localhost default.
    """
    from app.core.config import settings as app_settings

    original = app_settings.DATABASE_URL
    try:
        app_settings.DATABASE_URL = pg_sync_url
        cfg = Config(ALEMBIC_INI)
        command.upgrade(cfg, "head")
    finally:
        app_settings.DATABASE_URL = original


@pytest.fixture(scope="session")
def engine(pg_async_url, run_migrations):
    """Session-scoped async SQLAlchemy engine pointing at the container DB."""
    eng = create_async_engine(pg_async_url, echo=False, pool_pre_ping=True)
    yield eng
    # Container handles DB teardown; engine GC is fine here.


@pytest.fixture(scope="session")
def session_factory(engine):
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


@pytest.fixture
async def db_session(session_factory):
    """Per-test async session.

    Integration tests commit real data and rely on UUID uniqueness for
    isolation — no rollback trickery needed. A fresh session is created per
    test function and closed on teardown.
    """
    async with session_factory() as session:
        yield session
