"""fix subscription_tier CHECK constraint: narrow to free/paid

Revision ID: h8i9j0k1l2m3
Revises: g7h8i9j0k1l2
Create Date: 2026-04-30 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = "h8i9j0k1l2m3"
down_revision = "g7h8i9j0k1l2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Migrate existing non-free values (pro, enterprise) to 'paid'
    op.execute(
        "UPDATE users SET subscription_tier = 'paid' "
        "WHERE subscription_tier NOT IN ('free', 'paid')"
    )
    # Replace the old constraint
    op.drop_constraint("ck_users_subscription_tier", "users", type_="check")
    op.create_check_constraint(
        "ck_users_subscription_tier",
        "users",
        "subscription_tier IN ('free', 'paid')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_users_subscription_tier", "users", type_="check")
    # Map paid → pro for rollback (pro was the lower paid tier)
    op.execute(
        "UPDATE users SET subscription_tier = 'pro' "
        "WHERE subscription_tier = 'paid'"
    )
    op.create_check_constraint(
        "ck_users_subscription_tier",
        "users",
        "subscription_tier IN ('free', 'pro', 'enterprise')",
    )
