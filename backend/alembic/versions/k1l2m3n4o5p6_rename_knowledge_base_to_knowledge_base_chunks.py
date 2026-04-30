"""Rename knowledge_base table to knowledge_base_chunks to match ORM model.

The ORM model KnowledgeBaseChunk declares __tablename__ = "knowledge_base_chunks"
but migration c3d4e5f6g7h8 created the table as "knowledge_base". This mismatch
causes ProgrammingError ('relation does not exist') on any ORM query.

Existing indexes on the table (ix_knowledge_base_embedding, ix_kb_specialty_tags,
ix_patient_timeline_embedding, etc.) survive PostgreSQL table renames unchanged.

Revision ID: k1l2m3n4o5p6
Revises: 823a2873289a
Create Date: 2026-04-30 14:00:00.000000
"""
from alembic import op

revision = "k1l2m3n4o5p6"
down_revision = "823a2873289a"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.rename_table("knowledge_base", "knowledge_base_chunks")


def downgrade() -> None:
    op.rename_table("knowledge_base_chunks", "knowledge_base")
