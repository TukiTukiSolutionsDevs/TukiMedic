"""merge subscription tier and pgvector branches

Revision ID: 823a2873289a
Revises: e5f6g7h8i9j0, h8i9j0k1l2m3
Create Date: 2026-04-30 13:43:25.847587

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '823a2873289a'
down_revision: Union[str, Sequence[str], None] = ('e5f6g7h8i9j0', 'h8i9j0k1l2m3')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
