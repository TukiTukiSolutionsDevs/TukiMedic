"""add clinical facts

Revision ID: a1b2c3d4e5f6
Revises: 3dba84be1375
Create Date: 2026-04-10 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = '3dba84be1375'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add pgvector extension and clinical_facts table."""
    # Enable pgvector extension — must use raw SQL, not autogenerate
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        'clinical_facts',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('case_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('fact_type', sa.String(length=100), nullable=False),
        sa.Column('value', sa.Text(), nullable=False),
        sa.Column('source_agent', sa.String(length=100), nullable=False),
        sa.Column('confidence', sa.Float(), nullable=False),
        # Vector(1536) — hand-written because Alembic autogenerate ignores pgvector columns
        sa.Column('embedding', sa.Text().with_variant(
            sa.Text(), 'postgresql'
        ), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['case_id'], ['cases.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    # Override the embedding column with actual vector type (raw DDL)
    op.execute("ALTER TABLE clinical_facts ALTER COLUMN embedding TYPE vector(1536) USING embedding::vector(1536)")
    op.create_index('ix_clinical_facts_user_id', 'clinical_facts', ['user_id'])


def downgrade() -> None:
    """Drop clinical_facts table (extension stays — may be used by other tables)."""
    op.drop_index('ix_clinical_facts_user_id', table_name='clinical_facts')
    op.drop_table('clinical_facts')
