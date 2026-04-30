"""
Integration: KnowledgeBaseChunk ORM insert/query — table name sanity check.

Verifies that the DB table name matches the ORM model (__tablename__).
After the rename migration (knowledge_base → knowledge_base_chunks), ORM
operations must NOT raise "relation does not exist".

Run with:
    RUN_INTEGRATION=1 poetry run pytest -m integration tests/integration/test_kb_table_name.py
"""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select

from app.models.patient import KnowledgeBaseChunk


@pytest.mark.integration
@pytest.mark.asyncio
async def test_kb_chunk_orm_insert_and_query(db_session):
    """Insert a KnowledgeBaseChunk via ORM and query it back.

    Fails with ProgrammingError ('relation knowledge_base_chunks does not exist')
    if the DB still has the old table name 'knowledge_base' but the model
    declares __tablename__ = 'knowledge_base_chunks'.

    Passes only after the rename migration runs successfully.
    """
    chunk = KnowledgeBaseChunk(
        id=uuid.uuid4(),
        source="test",
        title="KB Table Name Verification",
        content="Integration test: table must be knowledge_base_chunks.",
        chunk_index=0,
        specialty_tags=["test"],
    )
    db_session.add(chunk)
    await db_session.commit()

    result = await db_session.execute(
        select(KnowledgeBaseChunk).where(KnowledgeBaseChunk.id == chunk.id)
    )
    fetched = result.scalar_one()
    assert fetched.title == "KB Table Name Verification"
    assert fetched.source == "test"
    assert fetched.chunk_index == 0
