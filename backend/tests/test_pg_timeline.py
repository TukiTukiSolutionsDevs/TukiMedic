"""
TDD tests for Memory L3 — Patient Timeline + Profile (pg_timeline).

Run: cd backend && poetry run pytest tests/test_pg_timeline.py -v
Mock strategy: AsyncSession via AsyncMock, get_embedding patched. No real DB/OpenAI.
"""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

USER_ID = str(uuid.UUID("00000000-0000-0000-0000-000000000001"))
USER_ID_2 = str(uuid.UUID("00000000-0000-0000-0000-000000000002"))
CASE_ID = str(uuid.UUID("00000000-0000-0000-0000-000000000003"))
FAKE_EMBEDDING = [0.1] * 1536


def _make_db_with_scalar_one_or_none(value):
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = value
    db = AsyncMock()
    db.execute = AsyncMock(return_value=mock_result)
    return db


def _make_db_with_rows(rows):
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = rows
    mock_result = MagicMock()
    mock_result.scalars.return_value = mock_scalars
    db = AsyncMock()
    db.execute = AsyncMock(return_value=mock_result)
    return db


def _make_timeline_row(event_type="consultation", summary="Consulta general", details=None, occurred_at=None):
    row = MagicMock()
    row.event_type = event_type
    row.summary = summary
    row.details = details
    row.occurred_at = occurred_at or datetime.now(timezone.utc)
    return row


def _make_profile(allergies=None, active_medications=None, chronic_conditions=None,
                  blood_type=None, age=None, sex=None):
    row = MagicMock()
    row.allergies = allergies or []
    row.active_medications = active_medications or []
    row.chronic_conditions = chronic_conditions or []
    row.blood_type = blood_type
    row.age = age
    row.sex = sex
    return row


class TestStoreTimelineEvent:
    @pytest.mark.asyncio
    async def test_store_timeline_event(self):
        """store_timeline_event creates a PatientTimelineEvent, adds and flushes."""
        from app.memory.pg_timeline import store_timeline_event

        db = AsyncMock()
        result = await store_timeline_event(db, USER_ID, CASE_ID, "consultation", "Consulta por dolor de pecho")

        db.add.assert_called_once()
        db.flush.assert_called_once()
        assert result is not None


class TestGetPatientTimeline:
    @pytest.mark.asyncio
    async def test_get_patient_timeline(self):
        """get_patient_timeline returns events as list of dicts with required keys."""
        from app.memory.pg_timeline import get_patient_timeline

        rows = [
            _make_timeline_row("consultation", "Segunda consulta"),
            _make_timeline_row("diagnosis", "Primera consulta"),
        ]
        db = _make_db_with_rows(rows)
        result = await get_patient_timeline(db, USER_ID)

        assert len(result) == 2
        assert result[0]["event_type"] == "consultation"
        assert result[0]["summary"] == "Segunda consulta"
        assert "occurred_at" in result[0]

    @pytest.mark.asyncio
    async def test_get_patient_timeline_empty(self):
        """get_patient_timeline returns [] when no events exist for the user."""
        from app.memory.pg_timeline import get_patient_timeline

        db = _make_db_with_rows([])
        result = await get_patient_timeline(db, USER_ID)
        assert result == []


class TestGetOrCreateProfileNew:
    @pytest.mark.asyncio
    async def test_get_or_create_profile_new(self):
        """get_or_create_profile creates empty profile when none exists."""
        from app.memory.pg_timeline import get_or_create_profile

        db = _make_db_with_scalar_one_or_none(None)
        result = await get_or_create_profile(db, USER_ID)

        db.add.assert_called_once()
        db.flush.assert_called_once()
        assert result["allergies"] == []
        assert result["active_medications"] == []
        assert result["chronic_conditions"] == []
        assert result["blood_type"] is None


class TestGetOrCreateProfileExisting:
    @pytest.mark.asyncio
    async def test_get_or_create_profile_existing(self):
        """get_or_create_profile returns existing profile without creating a new one."""
        from app.memory.pg_timeline import get_or_create_profile

        mock_profile = _make_profile(
            allergies=["penicilina"],
            active_medications=["metformina 850mg"],
            chronic_conditions=["diabetes tipo 2"],
            blood_type="O+",
            age=45,
            sex="masculino",
        )
        db = _make_db_with_scalar_one_or_none(mock_profile)
        result = await get_or_create_profile(db, USER_ID)

        db.add.assert_not_called()
        assert result["allergies"] == ["penicilina"]
        assert result["active_medications"] == ["metformina 850mg"]
        assert result["blood_type"] == "O+"
        assert result["age"] == 45


class TestUpdateProfile:
    @pytest.mark.asyncio
    async def test_update_profile(self):
        """update_profile sets given fields on existing profile and flushes."""
        from app.memory.pg_timeline import update_profile

        mock_profile = _make_profile()
        db = _make_db_with_scalar_one_or_none(mock_profile)

        await update_profile(db, USER_ID, {"allergies": ["sulfas"], "age": 30})

        assert mock_profile.allergies == ["sulfas"]
        assert mock_profile.age == 30
        db.flush.assert_called_once()


class TestTimelineUserIsolation:
    @pytest.mark.asyncio
    async def test_timeline_user_isolation(self):
        """get_patient_timeline query must filter by user_id (WHERE clause)."""
        from app.memory.pg_timeline import get_patient_timeline

        db = _make_db_with_rows([])
        await get_patient_timeline(db, USER_ID)

        db.execute.assert_called_once()
        compiled_query = str(db.execute.call_args[0][0])
        assert "user_id" in compiled_query


class TestStoreEventWithEmbedding:
    @pytest.mark.asyncio
    async def test_store_event_with_embedding(self):
        """store_timeline_event generates embedding and sets it on the event when api_key given."""
        from app.memory.pg_timeline import store_timeline_event

        db = AsyncMock()

        with patch(
            "app.memory.pg_timeline.get_embedding",
            AsyncMock(return_value=FAKE_EMBEDDING),
        ) as mock_embed:
            result = await store_timeline_event(
                db, USER_ID, CASE_ID, "diagnosis", "Hipertension arterial", api_key="test-key"
            )

        mock_embed.assert_called_once()
        db.add.assert_called_once()
        added = db.add.call_args[0][0]
        assert added.embedding == FAKE_EMBEDDING
        assert result is not None
