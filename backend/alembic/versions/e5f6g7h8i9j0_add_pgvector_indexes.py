"""add ivfflat indexes on embedding columns and key foreign keys

Adds:
- ivfflat indexes on clinical_facts.embedding, patient_timeline.embedding,
  knowledge_base.embedding (cosine similarity, lists=100)
- B-tree index on cases.user_id (FK lookup)
- GIN index on knowledge_base.specialty_tags (array containment)

These indexes are critical for production performance — without them, all
semantic searches do a sequential scan of the entire table.

Note: ivfflat requires the table to have data to build a useful index. On
empty tables the planner may choose seq scan anyway. The indexes are still
created so they're populated automatically as data flows in.

Revision ID: e5f6g7h8i9j0
Revises: d4e5f6g7h8i9
Create Date: 2026-04-30 08:00:00.000000
"""
from alembic import op


# revision identifiers
revision = "e5f6g7h8i9j0"
down_revision = "d4e5f6g7h8i9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # pgvector extension is assumed to already be installed (created in
    # initial migration). If not, uncomment:
    # op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_clinical_facts_embedding "
        "ON clinical_facts USING ivfflat (embedding vector_cosine_ops) "
        "WITH (lists = 100)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_patient_timeline_embedding "
        "ON patient_timeline USING ivfflat (embedding vector_cosine_ops) "
        "WITH (lists = 100)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_knowledge_base_embedding "
        "ON knowledge_base USING ivfflat (embedding vector_cosine_ops) "
        "WITH (lists = 100)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_cases_user_id ON cases(user_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_kb_specialty_tags "
        "ON knowledge_base USING GIN (specialty_tags)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_kb_specialty_tags")
    op.execute("DROP INDEX IF EXISTS ix_cases_user_id")
    op.execute("DROP INDEX IF EXISTS ix_knowledge_base_embedding")
    op.execute("DROP INDEX IF EXISTS ix_patient_timeline_embedding")
    op.execute("DROP INDEX IF EXISTS ix_clinical_facts_embedding")
