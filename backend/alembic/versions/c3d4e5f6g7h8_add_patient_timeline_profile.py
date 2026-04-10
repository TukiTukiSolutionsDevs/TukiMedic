"""add patient_timeline, patient_profiles, and knowledge_base tables

Revision ID: c3d4e5f6g7h8
Revises: b2c3d4e5f6g7
Create Date: 2026-04-10 15:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "c3d4e5f6g7h8"
down_revision: Union[str, Sequence[str], None] = "b2c3d4e5f6g7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create patient_timeline, patient_profiles, and knowledge_base tables."""

    # patient_timeline — Level-3 clinical event history per patient
    op.create_table(
        "patient_timeline",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("case_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("event_type", sa.String(length=50), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("details", postgresql.JSONB(), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["case_id"], ["cases.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_patient_timeline_user_id", "patient_timeline", ["user_id"])
    # pgvector column added via raw SQL (pgvector extension must be installed)
    op.execute("ALTER TABLE patient_timeline ADD COLUMN embedding vector(1536)")

    # patient_profiles — active patient profile (one per user)
    op.create_table(
        "patient_profiles",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("allergies", postgresql.JSONB(), nullable=True),
        sa.Column("active_medications", postgresql.JSONB(), nullable=True),
        sa.Column("chronic_conditions", postgresql.JSONB(), nullable=True),
        sa.Column("blood_type", sa.String(length=10), nullable=True),
        sa.Column("age", sa.Integer(), nullable=True),
        sa.Column("sex", sa.String(length=20), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id"),
    )
    op.create_index("ix_patient_profiles_user_id", "patient_profiles", ["user_id"])

    # knowledge_base — chunked medical articles for RAG
    op.create_table(
        "knowledge_base",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source", sa.String(length=100), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("specialty_tags", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.execute("ALTER TABLE knowledge_base ADD COLUMN embedding vector(1536)")


def downgrade() -> None:
    """Drop knowledge_base, patient_profiles, and patient_timeline tables."""
    op.drop_table("knowledge_base")
    op.drop_index("ix_patient_profiles_user_id", table_name="patient_profiles")
    op.drop_table("patient_profiles")
    op.drop_index("ix_patient_timeline_user_id", table_name="patient_timeline")
    op.drop_table("patient_timeline")
