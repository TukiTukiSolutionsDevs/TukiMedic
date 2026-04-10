"""
TDD tests for PostgreSQL vector memory (pg_facts) — T2 RED phase.

Run: cd backend && poetry run pytest tests/test_pg_facts.py -v
All tests MUST fail before T3-T5 implementation.

Mock strategy:
- openai.AsyncOpenAI patched at app.memory.pg_facts.AsyncOpenAI
- AsyncSession mocked via AsyncMock (execute, add_all, flush)
- No real DB, no real OpenAI
"""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch, call

import pytest


# ---------------------------------------------------------------------------
# Constants / helpers
# ---------------------------------------------------------------------------

USER_ID = str(uuid.UUID("00000000-0000-0000-0000-000000000001"))
CASE_ID = str(uuid.UUID("00000000-0000-0000-0000-000000000002"))
FAKE_EMBEDDING = [0.1] * 1536


def _make_fact(
    fact_type: str = "symptom",
    value: str = "dolor de pecho",
    confidence: float = 0.9,
    source_agent: str = "anamnesis",
) -> dict:
    return {
        "fact_type": fact_type,
        "value": value,
        "confidence": confidence,
        "source_agent": source_agent,
    }


def _make_db_row(
    fact_type: str = "symptom",
    value: str = "dolor de pecho",
    confidence: float = 0.9,
    source_agent: str = "anamnesis",
) -> MagicMock:
    """Simulate a ClinicalFactModel ORM row returned by scalars().all()."""
    row = MagicMock()
    row.fact_type = fact_type
    row.value = value
    row.confidence = confidence
    row.source_agent = source_agent
    return row


def _mock_openai_client(embedding: list | None = None) -> MagicMock:
    """Return a mock AsyncOpenAI client that returns a fake embedding response."""
    emb = embedding if embedding is not None else FAKE_EMBEDDING
    mock_response = MagicMock()
    mock_response.data = [MagicMock(embedding=emb)]

    mock_client = AsyncMock()
    mock_client.embeddings.create = AsyncMock(return_value=mock_response)
    return mock_client


def _make_db_with_rows(rows: list) -> AsyncMock:
    """Return a mock AsyncSession whose execute() returns the given rows."""
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = rows
    mock_result = MagicMock()
    mock_result.scalars.return_value = mock_scalars

    db = AsyncMock()
    db.execute = AsyncMock(return_value=mock_result)
    return db


# ---------------------------------------------------------------------------
# T2.1 — test_store_facts_filters_low_confidence
# ---------------------------------------------------------------------------


class TestStoreFactsFiltersLowConfidence:
    @pytest.mark.asyncio
    async def test_store_facts_filters_low_confidence(self):
        """Facts with confidence < 0.7 must NOT be stored — add_all never called."""
        from app.memory.pg_facts import store_facts

        db = AsyncMock()
        facts = [
            _make_fact(confidence=0.6),
            _make_fact(confidence=0.5, value="cansancio"),
            _make_fact(confidence=0.69, value="mareos"),
        ]

        with patch("app.memory.pg_facts.AsyncOpenAI", return_value=_mock_openai_client()):
            result = await store_facts(db, USER_ID, CASE_ID, facts, "test-key")

        db.add_all.assert_not_called()
        assert result == []


# ---------------------------------------------------------------------------
# T2.2 — test_store_facts_saves_high_confidence
# ---------------------------------------------------------------------------


class TestStoreFactsSavesHighConfidence:
    @pytest.mark.asyncio
    async def test_store_facts_saves_high_confidence(self):
        """Facts with confidence >= 0.7 must be bulk-inserted and flushed."""
        from app.memory.pg_facts import store_facts

        db = AsyncMock()
        db.flush = AsyncMock()
        facts = [
            _make_fact(confidence=0.7),
            _make_fact(confidence=0.9, value="tos seca"),
        ]

        with patch("app.memory.pg_facts.AsyncOpenAI", return_value=_mock_openai_client()):
            result = await store_facts(db, USER_ID, CASE_ID, facts, "test-key")

        db.add_all.assert_called_once()
        added = db.add_all.call_args[0][0]
        assert len(added) == 2
        db.flush.assert_called_once()
        assert len(result) == 2


# ---------------------------------------------------------------------------
# T2.3 — test_store_facts_generates_embeddings
# ---------------------------------------------------------------------------


class TestStoreFactsGeneratesEmbeddings:
    @pytest.mark.asyncio
    async def test_store_facts_generates_embeddings(self):
        """get_embedding must be called exactly once per qualifying fact."""
        from app.memory.pg_facts import store_facts

        db = AsyncMock()
        db.flush = AsyncMock()
        facts = [
            _make_fact(confidence=0.8, value="fiebre"),
            _make_fact(confidence=0.9, value="tos"),
            _make_fact(confidence=0.5, value="cansancio"),  # filtered out
        ]

        mock_client = _mock_openai_client()
        with patch("app.memory.pg_facts.AsyncOpenAI", return_value=mock_client):
            await store_facts(db, USER_ID, CASE_ID, facts, "test-key")

        # 2 qualifying facts → 2 embedding API calls
        assert mock_client.embeddings.create.call_count == 2


# ---------------------------------------------------------------------------
# T2.4 — test_retrieve_relevant_facts_returns_top_k
# ---------------------------------------------------------------------------


class TestRetrieveRelevantFactsReturnsTopK:
    @pytest.mark.asyncio
    async def test_retrieve_relevant_facts_returns_top_k(self):
        """Returns at most k facts as dicts with correct keys."""
        from app.memory.pg_facts import retrieve_relevant_facts

        rows = [_make_db_row(value=f"fact {i}") for i in range(3)]
        db = _make_db_with_rows(rows)

        with patch("app.memory.pg_facts.AsyncOpenAI", return_value=_mock_openai_client()):
            result = await retrieve_relevant_facts(db, USER_ID, "dolor de pecho", "test-key", k=3)

        assert len(result) == 3
        for item in result:
            assert set(item.keys()) == {"fact_type", "value", "confidence", "source_agent"}


# ---------------------------------------------------------------------------
# T2.5 — test_retrieve_relevant_facts_empty
# ---------------------------------------------------------------------------


class TestRetrieveRelevantFactsEmpty:
    @pytest.mark.asyncio
    async def test_retrieve_relevant_facts_empty(self):
        """No matching facts in DB → returns empty list."""
        from app.memory.pg_facts import retrieve_relevant_facts

        db = _make_db_with_rows([])

        with patch("app.memory.pg_facts.AsyncOpenAI", return_value=_mock_openai_client()):
            result = await retrieve_relevant_facts(db, USER_ID, "dolor", "test-key")

        assert result == []


# ---------------------------------------------------------------------------
# T2.6 — test_retrieve_relevant_facts_user_isolation
# ---------------------------------------------------------------------------


class TestRetrieveRelevantFactsUserIsolation:
    @pytest.mark.asyncio
    async def test_retrieve_relevant_facts_user_isolation(self):
        """The DB query must filter by user_id (WHERE clause contains user_id)."""
        from app.memory.pg_facts import retrieve_relevant_facts

        db = _make_db_with_rows([])

        with patch("app.memory.pg_facts.AsyncOpenAI", return_value=_mock_openai_client()):
            await retrieve_relevant_facts(db, USER_ID, "dolor", "test-key")

        db.execute.assert_called_once()
        # SQLAlchemy compiles the Select to SQL — user_id filter must appear
        compiled_query = str(db.execute.call_args[0][0])
        assert "user_id" in compiled_query


# ---------------------------------------------------------------------------
# T2.7 — test_get_embedding_calls_openai
# ---------------------------------------------------------------------------


class TestGetEmbeddingCallsOpenAI:
    @pytest.mark.asyncio
    async def test_get_embedding_calls_openai(self):
        """get_embedding must call OpenAI with the correct model and input text."""
        from app.memory.pg_facts import get_embedding, EMBEDDING_MODEL

        mock_client = _mock_openai_client(FAKE_EMBEDDING)
        with patch("app.memory.pg_facts.AsyncOpenAI", return_value=mock_client):
            result = await get_embedding("symptom: dolor de pecho", "test-key")

        mock_client.embeddings.create.assert_called_once_with(
            model=EMBEDDING_MODEL,
            input="symptom: dolor de pecho",
        )
        assert result == FAKE_EMBEDDING


# ---------------------------------------------------------------------------
# T2.8 — test_store_facts_empty_list
# ---------------------------------------------------------------------------


class TestStoreFactsEmptyList:
    @pytest.mark.asyncio
    async def test_store_facts_empty_list(self):
        """Empty input list is a complete no-op — no DB calls, no embedding calls."""
        from app.memory.pg_facts import store_facts

        db = AsyncMock()

        mock_client = _mock_openai_client()
        with patch("app.memory.pg_facts.AsyncOpenAI", return_value=mock_client):
            result = await store_facts(db, USER_ID, CASE_ID, [], "test-key")

        db.add_all.assert_not_called()
        db.flush.assert_not_called()
        mock_client.embeddings.create.assert_not_called()
        assert result == []
