"""
Knowledge Base Retriever — semantic RAG over the knowledge_base table.

Uses cosine similarity on pgvector embeddings to find relevant medical
content chunks, then concatenates them up to a token budget.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.memory.pg_facts import get_embedding
from app.models.patient import KnowledgeBaseChunk

MAX_KB_CONTEXT_TOKENS = 1500  # approximate word budget


async def retrieve_kb_context(
    db: AsyncSession,
    query: str,
    api_key: str,
    k: int = 5,
    specialty: str | None = None,
) -> str:
    """Retrieve relevant KB chunks via cosine similarity and return as a single string.

    Args:
        db: Async SQLAlchemy session.
        query: User query or clinical context string.
        api_key: OpenAI API key (BYOK).
        k: Max chunks to retrieve before token-limit trimming.
        specialty: Optional specialty tag to filter results.

    Returns:
        Formatted string with source headers and content, or "" if no matches.
    """
    query_embedding = await get_embedding(query, api_key)

    stmt = (
        select(KnowledgeBaseChunk)
        .order_by(KnowledgeBaseChunk.embedding.cosine_distance(query_embedding))
        .limit(k)
    )

    if specialty:
        stmt = stmt.where(KnowledgeBaseChunk.specialty_tags.contains([specialty]))

    result = await db.execute(stmt)
    chunks = result.scalars().all()

    if not chunks:
        return ""

    context_parts: list[str] = []
    total_words = 0

    for chunk in chunks:
        words = chunk.content.split()
        if total_words + len(words) > MAX_KB_CONTEXT_TOKENS:
            break
        context_parts.append(f"[{chunk.source}: {chunk.title}]\n{chunk.content}")
        total_words += len(words)

    return "\n\n---\n\n".join(context_parts)
