"""
Knowledge Base Indexer — fetch, chunk, embed, and store medical articles.

MVP source: MedlinePlus REST API (no scraping required, public health topics).
Chunking: word-based sliding window (chunk_size=512, overlap=50).
Embedding: text-embedding-3-small via get_embedding (BYOK pattern).
"""

import httpx

from app.memory.pg_facts import get_embedding
from app.models.patient import KnowledgeBaseChunk

MEDLINEPLUS_API = "https://wsearch.nlm.nih.gov/ws/query"
CHUNK_SIZE = 512   # approximate token count (words)
CHUNK_OVERLAP = 50


def chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """Split text into overlapping word-based chunks.

    Args:
        text: Input text to split.
        chunk_size: Max words per chunk.
        overlap: Number of words shared between consecutive chunks.

    Returns:
        List of chunk strings. Short text (< chunk_size) returns a single-item list.
    """
    words = text.split()
    if not words:
        return []

    chunks: list[str] = []
    step = chunk_size - overlap
    for i in range(0, len(words), step):
        chunk_words = words[i : i + chunk_size]
        if chunk_words:
            chunks.append(" ".join(chunk_words))
        # Stop if last chunk fits entirely — avoids tiny tail chunks
        if i + chunk_size >= len(words):
            break

    return chunks if chunks else [text]


async def fetch_medlineplus(query: str, max_results: int = 5) -> list[dict]:
    """Fetch health topic summaries from the MedlinePlus web service.

    Returns a list of {title, content, url} dicts.
    Returns [] on any HTTP or parse error (graceful degradation).
    """
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                MEDLINEPLUS_API,
                params={"db": "healthTopics", "term": query, "retmax": max_results},
            )
            response.raise_for_status()

        # MedlinePlus returns XML — parse summaries
        import xml.etree.ElementTree as ET
        root = ET.fromstring(response.text)
        results = []
        for doc in root.findall(".//document"):
            title_el = doc.find(".//content[@name='title']")
            summary_el = doc.find(".//content[@name='FullSummary']")
            url = doc.get("url", "")
            if title_el is not None and summary_el is not None:
                results.append({
                    "title": title_el.text or "",
                    "content": summary_el.text or "",
                    "url": url,
                })
        return results
    except Exception:
        return []


async def index_topic(
    db,
    title: str,
    content: str,
    source: str,
    specialty_tags: list,
    api_key: str,
) -> None:
    """Chunk, embed, and persist a knowledge base article.

    Each chunk becomes one KnowledgeBaseChunk row with a vector embedding.
    Calls db.flush() once after all chunks are added.
    """
    chunks = chunk_text(content)
    for i, chunk in enumerate(chunks):
        embedding = await get_embedding(chunk[:2000], api_key)
        kb = KnowledgeBaseChunk(
            source=source,
            title=title,
            content=chunk,
            chunk_index=i,
            specialty_tags=specialty_tags,
            embedding=embedding,
        )
        db.add(kb)
    await db.flush()


# ---------------------------------------------------------------------------
# Background indexer — called by POST /admin/kb/ingest
# ---------------------------------------------------------------------------

HEALTH_TOPICS = [
    "hypertension",
    "diabetes mellitus",
    "asthma",
    "heart failure",
    "liver disease",
]


async def run_indexer() -> dict[str, int]:
    """Background task: fetch MedlinePlus health topics and index them into the KB.

    Creates its own DB session — background tasks do not receive FastAPI DI.
    Graceful no-op per topic when fetch returns no articles (e.g. network down).

    Returns:
        {"indexed": N, "skipped": M} where N = chunks stored, M = topics with
        no articles returned.
    """
    from app.core.config import settings
    from app.core.database import async_session

    api_key = settings.OPENAI_API_KEY
    indexed = 0
    skipped = 0

    async with async_session() as db:
        for topic in HEALTH_TOPICS:
            articles = await fetch_medlineplus(topic)
            if not articles:
                skipped += 1
                continue
            for article in articles:
                if article.get("content"):
                    await index_topic(
                        db,
                        title=article["title"],
                        content=article["content"],
                        source="medlineplus",
                        specialty_tags=[topic],
                        api_key=api_key,
                    )
                    indexed += 1
        await db.commit()

    return {"indexed": indexed, "skipped": skipped}
