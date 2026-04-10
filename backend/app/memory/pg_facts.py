"""
PostgreSQL vector memory — Level 2 persistent clinical facts.

Stores and retrieves ClinicalFact records with semantic embeddings via pgvector.
All functions accept an AsyncSession and an OpenAI api_key (BYOK pattern).
"""

from openai import AsyncOpenAI
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.clinical_fact import ClinicalFactModel

CONFIDENCE_THRESHOLD = 0.7
EMBEDDING_MODEL = "text-embedding-3-small"
DEFAULT_K = 10


async def get_embedding(text: str, api_key: str) -> list[float]:
    """Call OpenAI text-embedding-3-small and return the embedding vector."""
    client = AsyncOpenAI(api_key=api_key)
    response = await client.embeddings.create(model=EMBEDDING_MODEL, input=text)
    return response.data[0].embedding


async def store_facts(
    db: AsyncSession,
    user_id: str,
    case_id: str,
    facts: list[dict],
    api_key: str,
) -> list:
    """
    Filter facts by confidence >= CONFIDENCE_THRESHOLD, embed each one,
    and bulk-insert into clinical_facts.

    Returns the list of inserted ClinicalFactModel instances (empty if none qualified).
    """
    qualified = [f for f in facts if f.get("confidence", 0) >= CONFIDENCE_THRESHOLD]
    if not qualified:
        return []

    # Generate embeddings for each qualifying fact (mutates a copy)
    to_insert = []
    for fact in qualified:
        text = f"{fact['fact_type']}: {fact['value']}"
        embedding = await get_embedding(text, api_key)
        to_insert.append({**fact, "embedding": embedding})

    models = [
        ClinicalFactModel(user_id=user_id, case_id=case_id, **f)
        for f in to_insert
    ]
    db.add_all(models)
    await db.flush()
    return models


async def retrieve_relevant_facts(
    db: AsyncSession,
    user_id: str,
    query: str,
    api_key: str,
    k: int = DEFAULT_K,
) -> list[dict]:
    """
    Embed the query text, run cosine similarity search against clinical_facts
    filtered by user_id, and return the top-k results as plain dicts.
    """
    query_embedding = await get_embedding(query, api_key)

    result = await db.execute(
        select(ClinicalFactModel)
        .where(ClinicalFactModel.user_id == user_id)
        .order_by(ClinicalFactModel.embedding.cosine_distance(query_embedding))
        .limit(k)
    )
    rows = result.scalars().all()
    return [
        {
            "fact_type": r.fact_type,
            "value": r.value,
            "confidence": r.confidence,
            "source_agent": r.source_agent,
        }
        for r in rows
    ]
