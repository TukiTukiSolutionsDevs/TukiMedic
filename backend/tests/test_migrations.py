"""
TDD — S4.0.a-1: Verify reversible users role/subscription_tier migration.

Runs alembic upgrade head then downgrade -1 on an isolated test DB and verifies:
  - After upgrade: users.role and users.subscription_tier exist; is_admin is gone;
    former is_admin=True users are backfilled to role='admin'.
  - After downgrade -1: role/subscription_tier gone; is_admin restored.

Requires a running PostgreSQL instance with a dedicated test DB.
Create it once with:
    createdb -h localhost -p 5433 -U medagent medagent_test

Skipped automatically when the test DB is unreachable.
"""
from __future__ import annotations

import os
import uuid

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

_ASYNC_DB = os.environ.get(
    "DATABASE_URL",
    "postgresql+asyncpg://medagent:medagent@localhost:5433/medagent",
)
_SYNC_BASE = _ASYNC_DB.replace("+asyncpg", "")
# Swap DB name → medagent_test for isolation
_host_part, _, _ = _SYNC_BASE.rpartition("/")
_DEFAULT_TEST_URL = f"{_host_part}/medagent_test"
TEST_DATABASE_URL: str = os.environ.get("TEST_DATABASE_URL", _DEFAULT_TEST_URL)

_ALEMBIC_INI = os.path.join(os.path.dirname(__file__), "..", "alembic.ini")

# Last revision before the migration under test.
_PREV_REVISION = "d4e5f6g7h8i9"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _alembic_cfg(url: str) -> Config:
    cfg = Config(_ALEMBIC_INI)
    cfg.set_main_option("sqlalchemy.url", url)
    return cfg


def _has_column(conn: sa.engine.Connection, table: str, column: str) -> bool:
    insp = sa.inspect(conn)
    return column in {c["name"] for c in insp.get_columns(table)}


# ---------------------------------------------------------------------------
# Module-scoped engine (skip entire module if DB unavailable)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def sync_engine():
    engine = sa.create_engine(TEST_DATABASE_URL, poolclass=sa.pool.NullPool)
    try:
        with engine.connect() as conn:
            conn.execute(sa.text("SELECT 1"))
    except Exception as exc:
        engine.dispose()
        pytest.skip(
            f"Migration test DB not reachable ({TEST_DATABASE_URL}).\n"
            f"Create it with: createdb -h localhost -p 5433 -U medagent medagent_test\n"
            f"Error: {exc}"
        )

    cfg = _alembic_cfg(TEST_DATABASE_URL)
    command.downgrade(cfg, "base")
    command.upgrade(cfg, _PREV_REVISION)

    yield engine

    command.downgrade(cfg, "base")
    engine.dispose()


# ---------------------------------------------------------------------------
# Test
# ---------------------------------------------------------------------------

def test_role_migration_is_reversible(sync_engine):
    """
    Full upgrade → assert → downgrade → assert cycle.

    Acceptance (S4.0.a-1):
      - upgrade head: role/subscription_tier added; is_admin dropped;
        former is_admin=True users → role='admin', is_admin=False → role='customer'.
      - downgrade -1: role/subscription_tier dropped; is_admin restored with
        former admin user having is_admin=True.
    """
    cfg = _alembic_cfg(TEST_DATABASE_URL)

    # --- Arrange: seed users at state d4e5f6g7h8i9 ---
    admin_id = str(uuid.uuid4())
    regular_id = str(uuid.uuid4())

    with sync_engine.begin() as conn:
        conn.execute(
            sa.text(
                "INSERT INTO users "
                "(id, email, password_hash, is_active, is_verified, is_admin, "
                " created_at, updated_at, preferences) VALUES "
                "(:id1, :e1, '!', true, false, true,  now(), now(), '{}'), "
                "(:id2, :e2, '!', true, false, false, now(), now(), '{}')"
            ),
            {
                "id1": admin_id, "e1": f"adm_{admin_id[:8]}@t.x",
                "id2": regular_id, "e2": f"usr_{regular_id[:8]}@t.x",
            },
        )

    # --- Act: upgrade to head ---
    command.upgrade(cfg, "head")

    # --- Assert: post-upgrade schema ---
    with sync_engine.connect() as conn:
        assert _has_column(conn, "users", "role"), \
            "users.role must exist after upgrade"
        assert _has_column(conn, "users", "subscription_tier"), \
            "users.subscription_tier must exist after upgrade"
        assert not _has_column(conn, "users", "is_admin"), \
            "users.is_admin must be dropped after upgrade"

        row_admin = conn.execute(
            sa.text("SELECT role, subscription_tier FROM users WHERE id = :id"),
            {"id": admin_id},
        ).fetchone()
        assert row_admin is not None
        assert row_admin.role == "admin", \
            f"Former admin must have role='admin' after backfill, got '{row_admin.role}'"
        assert row_admin.subscription_tier == "free", \
            f"subscription_tier must default to 'free', got '{row_admin.subscription_tier}'"

        row_user = conn.execute(
            sa.text("SELECT role FROM users WHERE id = :id"),
            {"id": regular_id},
        ).fetchone()
        assert row_user is not None
        assert row_user.role == "customer", \
            f"Regular user must have role='customer' after backfill, got '{row_user.role}'"

    # --- Act: downgrade -1 ---
    command.downgrade(cfg, "-1")

    # --- Assert: post-downgrade schema ---
    with sync_engine.connect() as conn:
        assert not _has_column(conn, "users", "role"), \
            "users.role must be removed after downgrade"
        assert not _has_column(conn, "users", "subscription_tier"), \
            "users.subscription_tier must be removed after downgrade"
        assert _has_column(conn, "users", "is_admin"), \
            "users.is_admin must be restored after downgrade"

        row_admin = conn.execute(
            sa.text("SELECT is_admin FROM users WHERE id = :id"),
            {"id": admin_id},
        ).fetchone()
        assert row_admin is not None
        assert row_admin.is_admin is True, \
            f"Former admin must have is_admin=True after downgrade, got {row_admin.is_admin}"
