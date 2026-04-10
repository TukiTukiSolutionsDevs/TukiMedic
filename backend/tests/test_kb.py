"""
TDD tests for Knowledge Base — kb_indexer (chunking) + kb_retriever (RAG).

Run: cd backend && poetry run pytest tests/test_kb.py -v
Mock strategy: AsyncSession via AsyncMock, get_embedding patched. No real DB/OpenAI/HTTP.
"""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

FAKE_EMBEDDING = [0.2] * 1536


def _make_db_with_rows(rows):
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = rows
    mock_result = MagicMock()
    mock_result.scalars.return_value = mock_scalars
    db = AsyncMock()
    db.execute = AsyncMock(return_value=mock_result)
    return db


def _make_kb_chunk(source="medlineplus", title="Hypertension", content="some content",
                   chunk_index=0, specialty_tags=None):
    row = MagicMock()
    row.source = source
    row.title = title
    row.content = content
    row.chunk_index = chunk_index
    row.specialty_tags = specialty_tags or []
    return row


# ---------------------------------------------------------------------------
# T1 — test_chunk_text
# ---------------------------------------------------------------------------


class TestChunkText:
    def test_chunk_text(self):
        """chunk_text splits text longer than chunk_size into multiple chunks."""
        from app.services.kb_indexer import chunk_text

        words = ["word"] * 600
        text = " ".join(words)
        chunks = chunk_text(text, chunk_size=512, overlap=50)

        assert len(chunks) > 1
        for chunk in chunks:
            assert len(chunk.split()) <= 512

    # ---------------------------------------------------------------------------
    # T2 — test_chunk_text_overlap
    # ---------------------------------------------------------------------------

    def test_chunk_text_overlap(self):
        """Consecutive chunks share 'overlap' words at the boundary."""
        from app.services.kb_indexer import chunk_text

        words = [f"w{i}" for i in range(600)]
        text = " ".join(words)
        chunks = chunk_text(text, chunk_size=512, overlap=50)

        assert len(chunks) >= 2
        first_words = chunks[0].split()
        second_words = chunks[1].split()
        # Last 50 words of chunk[0] == first 50 words of chunk[1]
        assert first_words[-50:] == second_words[:50]

    # ---------------------------------------------------------------------------
    # T3 — test_chunk_text_short
    # ---------------------------------------------------------------------------

    def test_chunk_text_short(self):
        """Text shorter than chunk_size is returned as a single chunk."""
        from app.services.kb_indexer import chunk_text

        text = "This is a short medical text about hypertension."
        chunks = chunk_text(text)

        assert len(chunks) == 1
        assert chunks[0] == text


# ---------------------------------------------------------------------------
# T4 — test_retrieve_kb_context
# ---------------------------------------------------------------------------


class TestRetrieveKbContext:
    @pytest.mark.asyncio
    async def test_retrieve_kb_context(self):
        """retrieve_kb_context returns formatted string with source and title headers."""
        from app.memory.kb_retriever import retrieve_kb_context

        chunks = [
            _make_kb_chunk("medlineplus", "Diabetes", "Diabetes is a chronic disease.", 0),
            _make_kb_chunk("medlineplus", "Hypertension", "High blood pressure affects millions.", 0),
        ]
        db = _make_db_with_rows(chunks)

        with patch("app.memory.kb_retriever.get_embedding", AsyncMock(return_value=FAKE_EMBEDDING)):
            result = await retrieve_kb_context(db, "diabetes symptoms", "test-key")

        assert "medlineplus" in result
        assert "Diabetes" in result
        assert "Hypertension" in result

    # ---------------------------------------------------------------------------
    # T5 — test_retrieve_kb_context_empty
    # ---------------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_retrieve_kb_context_empty(self):
        """retrieve_kb_context returns empty string when no chunks match."""
        from app.memory.kb_retriever import retrieve_kb_context

        db = _make_db_with_rows([])

        with patch("app.memory.kb_retriever.get_embedding", AsyncMock(return_value=FAKE_EMBEDDING)):
            result = await retrieve_kb_context(db, "diabetes", "test-key")

        assert result == ""

    # ---------------------------------------------------------------------------
    # T6 — test_retrieve_kb_context_token_limit
    # ---------------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_retrieve_kb_context_token_limit(self):
        """retrieve_kb_context stops adding chunks when MAX_KB_CONTEXT_TOKENS is reached."""
        from app.memory.kb_retriever import retrieve_kb_context, MAX_KB_CONTEXT_TOKENS

        big_content = " ".join(["word"] * 1000)
        chunks = [_make_kb_chunk("medlineplus", f"Topic {i}", big_content, i) for i in range(5)]
        db = _make_db_with_rows(chunks)

        with patch("app.memory.kb_retriever.get_embedding", AsyncMock(return_value=FAKE_EMBEDDING)):
            result = await retrieve_kb_context(db, "any query", "test-key")

        result_words = len(result.split())
        # 5 * 1000 words would be 5000 — result must be well below that
        assert result_words < 5 * 1000
        # And must respect the declared limit (with some slack for headers)
        assert result_words < MAX_KB_CONTEXT_TOKENS + 200

    # ---------------------------------------------------------------------------
    # T7 — test_retrieve_kb_context_specialty_filter
    # ---------------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_retrieve_kb_context_specialty_filter(self):
        """retrieve_kb_context applies specialty filter to the DB query when provided."""
        from app.memory.kb_retriever import retrieve_kb_context

        db = _make_db_with_rows([])

        with patch("app.memory.kb_retriever.get_embedding", AsyncMock(return_value=FAKE_EMBEDDING)):
            await retrieve_kb_context(db, "diabetes", "test-key", specialty="cardiology")

        db.execute.assert_called_once()
        compiled_query = str(db.execute.call_args[0][0])
        assert "specialty_tags" in compiled_query


# ---------------------------------------------------------------------------
# T8 — test_index_topic
# ---------------------------------------------------------------------------


class TestIndexTopic:
    @pytest.mark.asyncio
    async def test_index_topic(self):
        """index_topic chunks content, embeds each chunk, and stores KnowledgeBaseChunk rows."""
        from app.services.kb_indexer import index_topic

        db = AsyncMock()
        content = " ".join(["word"] * 600)  # 600 words → multiple chunks

        with patch(
            "app.services.kb_indexer.get_embedding",
            AsyncMock(return_value=FAKE_EMBEDDING),
        ) as mock_embed:
            await index_topic(
                db,
                title="Hypertension",
                content=content,
                source="medlineplus",
                specialty_tags=["cardiology"],
                api_key="test-key",
            )

        assert db.add.call_count >= 2
        db.flush.assert_called_once()
        assert mock_embed.call_count >= 2
