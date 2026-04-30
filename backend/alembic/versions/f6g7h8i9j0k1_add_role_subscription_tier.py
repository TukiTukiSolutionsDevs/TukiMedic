"""add role and subscription_tier to users, drop is_admin

Revision ID: f6g7h8i9j0k1
Revises: d4e5f6g7h8i9
Create Date: 2026-04-30 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = "f6g7h8i9j0k1"
down_revision = "d4e5f6g7h8i9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Add new columns (nullable first for backfill)
    op.add_column("users", sa.Column("role", sa.String(50), nullable=True))
    op.add_column(
        "users", sa.Column("subscription_tier", sa.String(50), nullable=True)
    )

    # 2. Backfill from is_admin
    op.execute("UPDATE users SET role = 'admin' WHERE is_admin = true")
    op.execute(
        "UPDATE users SET role = 'customer' WHERE is_admin = false OR is_admin IS NULL"
    )
    op.execute("UPDATE users SET subscription_tier = 'free'")

    # 3. Set NOT NULL with server defaults
    op.alter_column(
        "users", "role", nullable=False, server_default=sa.text("'customer'")
    )
    op.alter_column(
        "users",
        "subscription_tier",
        nullable=False,
        server_default=sa.text("'free'"),
    )

    # 4. Add CHECK constraints
    op.create_check_constraint(
        "ck_users_role", "users", "role IN ('admin', 'customer')"
    )
    op.create_check_constraint(
        "ck_users_subscription_tier",
        "users",
        "subscription_tier IN ('free', 'pro', 'enterprise')",
    )

    # 5. Drop is_admin
    op.drop_column("users", "is_admin")


def downgrade() -> None:
    # 1. Re-add is_admin (nullable for backfill)
    op.add_column(
        "users", sa.Column("is_admin", sa.Boolean(), nullable=True)
    )

    # 2. Backfill from role
    op.execute("UPDATE users SET is_admin = (role = 'admin')")

    # 3. Set NOT NULL with server default
    op.alter_column(
        "users", "is_admin", nullable=False, server_default=sa.text("false")
    )

    # 4. Drop constraints
    op.drop_constraint("ck_users_role", "users", type_="check")
    op.drop_constraint("ck_users_subscription_tier", "users", type_="check")

    # 5. Drop new columns
    op.drop_column("users", "subscription_tier")
    op.drop_column("users", "role")
