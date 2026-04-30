"""
Integration: alembic migration full cycle on an isolated PostgreSQL container.

Spins its own container (separate from the session-scoped one) so it can run
`downgrade base` without destroying the shared test DB.

Replaces / supplements the skipped test_migrations.py test which requires a
pre-existing test DB at localhost:5433.
"""
from __future__ import annotations

import sqlalchemy as sa
import pytest
from alembic import command
from alembic.config import Config

from tests.integration.conftest import ALEMBIC_INI, make_sync_url

# Tables that must exist after `upgrade head` and be gone after `downgrade base`.
_EXPECTED_TABLES = frozenset(
    {
        "users",
        "cases",
        "messages",
        "clinical_facts",
        "documents",
        "lab_values",
        "patient_timeline",
        "patient_profiles",
        "knowledge_base_chunks",
        "audit_logs",
        "provider_credentials",
    }
)


def _run_alembic(sync_url: str, direction: str, target: str) -> None:
    """Run alembic upgrade/downgrade against *sync_url*, patching settings."""
    from app.core.config import settings as app_settings

    original = app_settings.DATABASE_URL
    try:
        app_settings.DATABASE_URL = sync_url
        cfg = Config(ALEMBIC_INI)
        if direction == "upgrade":
            # Use "heads" (plural) — the DAG has two leaf revisions.
            # "head" (singular) raises MultipleHeads. Follow-up: merge branches.
            command.upgrade(cfg, "heads" if target == "head" else target)
        else:
            command.downgrade(cfg, target)
    finally:
        app_settings.DATABASE_URL = original


def _get_tables(sync_url: str) -> set[str]:
    eng = sa.create_engine(sync_url, poolclass=sa.pool.NullPool)
    try:
        with eng.connect() as conn:
            return set(sa.inspect(conn).get_table_names())
    finally:
        eng.dispose()


@pytest.mark.integration
def test_upgrade_head_creates_all_expected_tables():
    """alembic upgrade head must create every expected application table."""
    try:
        from testcontainers.postgres import PostgresContainer
    except ImportError:
        pytest.skip("testcontainers not installed")

    try:
        pg = PostgresContainer("pgvector/pgvector:pg16")
        pg.start()
    except Exception as exc:
        if any(k in str(exc).lower() for k in ("docker", "connection", "socket")):
            pytest.skip(f"Docker not available: {exc}")
        raise

    try:
        sync_url = make_sync_url(pg.get_connection_url())
        _run_alembic(sync_url, "upgrade", "head")
        tables = _get_tables(sync_url)
    finally:
        pg.stop()

    missing = _EXPECTED_TABLES - tables
    assert not missing, (
        f"Tables missing after `alembic upgrade head`: {sorted(missing)}\n"
        "Check that all migration files are present and migrations run cleanly."
    )


@pytest.mark.integration
def test_downgrade_base_removes_all_app_tables():
    """alembic downgrade base must remove every application table (reversible)."""
    try:
        from testcontainers.postgres import PostgresContainer
    except ImportError:
        pytest.skip("testcontainers not installed")

    try:
        pg = PostgresContainer("pgvector/pgvector:pg16")
        pg.start()
    except Exception as exc:
        if any(k in str(exc).lower() for k in ("docker", "connection", "socket")):
            pytest.skip(f"Docker not available: {exc}")
        raise

    try:
        sync_url = make_sync_url(pg.get_connection_url())
        _run_alembic(sync_url, "upgrade", "head")
        _run_alembic(sync_url, "downgrade", "base")
        tables = _get_tables(sync_url)
    finally:
        pg.stop()

    leftover = _EXPECTED_TABLES.intersection(tables)
    assert not leftover, (
        f"Tables still present after `alembic downgrade base`: {sorted(leftover)}\n"
        "Migrations are not fully reversible — fix the downgrade() steps."
    )
