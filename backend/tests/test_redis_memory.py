"""
TDD tests for Redis sliding window memory — T1 RED phase.

Run: cd backend && poetry run pytest tests/test_redis_memory.py -v
All tests MUST fail before T2/T3 implementation.
"""

import asyncio
import json
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import fakeredis.aioredis
import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_fake_redis() -> fakeredis.aioredis.FakeRedis:
    """Return a fakeredis async client with decode_responses=True (matches production)."""
    return fakeredis.aioredis.FakeRedis(decode_responses=True)


def _make_mock_user():
    user = MagicMock()
    user.id = uuid.UUID("00000000-0000-0000-0000-000000000001")
    user.is_active = True
    return user


def _make_mock_graph(events: list):
    """Return a mock graph whose astream_events yields the given event dicts."""

    async def _astream(state, config, version):
        for e in events:
            yield e

    graph = MagicMock()
    graph.astream_events = _astream
    return graph


def _done_event(case_id: str = "case1", response: str = "Respuesta de prueba"):
    return {
        "event": "on_chain_end",
        "name": "synthesizer",
        "data": {"output": {"synthesized_response": response}},
    }


class _FakeWebSocket:
    """Minimal WebSocket stub for testing the chat handler end-to-end."""

    def __init__(self, receive_messages: list[str]):
        self._queue = list(receive_messages)
        self.sent: list[dict] = []
        self.closed = False
        self.close_code: int | None = None

    async def accept(self) -> None:
        pass

    async def receive_text(self) -> str:
        if not self._queue:
            from starlette.websockets import WebSocketDisconnect
            raise WebSocketDisconnect()
        return self._queue.pop(0)

    async def send_json(self, data: dict) -> None:
        self.sent.append(data)

    async def close(self, code: int = 1000) -> None:
        self.closed = True
        self.close_code = code

    @property
    def headers(self) -> dict:
        # Empty → origin guard skipped (origin == "" → falsy)
        return {}


async def _run_ws_one_message(
    content: str,
    case_id: str,
    mock_graph,
    load_mock: AsyncMock,
    append_mock: AsyncMock,
) -> _FakeWebSocket:
    """
    Drive the websocket_chat handler through:
      auth → one message → disconnect.
    Heavy deps are mocked; load_messages / append_messages are injected.
    """
    from app.api.v1 import chat as chat_module

    mock_user = _make_mock_user()
    auth_msg = json.dumps({"type": "auth", "token": "tok"})
    chat_msg = json.dumps({"type": "message", "content": content, "case_id": case_id})
    fake_ws = _FakeWebSocket([auth_msg, chat_msg])

    mock_db = AsyncMock()

    # db.get(model, pk) — return User for User lookup, None for Case lookup
    # so the T2.3 ownership check treats this as a new case.
    async def _smart_get(model, pk):
        from app.models.user import User as UserModel

        if model is UserModel:
            return mock_user
        return None

    mock_db.get = AsyncMock(side_effect=_smart_get)

    mock_session = MagicMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_db)
    mock_session.__aexit__ = AsyncMock(return_value=None)

    fake_redis = AsyncMock()
    fake_redis.incr = AsyncMock(return_value=1)
    fake_redis.expire = AsyncMock()

    with (
        patch("app.api.v1.chat.HEARTBEAT_INTERVAL", 0.001),
        patch("app.api.v1.chat.AUTH_TIMEOUT", 5.0),
        patch("app.api.v1.chat.GRAPH_TIMEOUT", 5.0),
        patch("app.api.v1.chat.decode_token", return_value={"type": "access", "sub": str(mock_user.id)}),
        patch("app.api.v1.chat.async_session", return_value=mock_session),
        patch("app.api.v1.chat.get_or_build_graph", new=AsyncMock(return_value=mock_graph)),
        patch("app.api.v1.chat.create_initial_state", return_value={"messages": [], "case_id": case_id}),
        patch("app.api.v1.chat.redis_client", fake_redis),
        patch("app.api.v1.chat.load_messages", load_mock),
        patch("app.api.v1.chat.append_messages", append_mock),
    ):
        await chat_module.websocket_chat(fake_ws)

    return fake_ws


# ---------------------------------------------------------------------------
# T1.1 — test_load_empty
# ---------------------------------------------------------------------------


class TestLoadEmpty:
    def test_load_empty(self):
        """No key in Redis → load_messages returns []."""
        from app.memory.redis_window import load_messages

        fake = _make_fake_redis()
        with patch("app.memory.redis_window.redis_client", fake):
            result = asyncio.run(load_messages("user1", "case1"))

        assert result == []


# ---------------------------------------------------------------------------
# T1.2 — test_append_and_load
# ---------------------------------------------------------------------------


class TestAppendAndLoad:
    def test_append_and_load(self):
        """Append 1 exchange → load returns 2 messages in insertion order."""
        from app.memory.redis_window import append_messages, load_messages

        fake = _make_fake_redis()
        with patch("app.memory.redis_window.redis_client", fake):
            asyncio.run(append_messages("user1", "case1", "Me duele la cabeza", "¿Desde cuándo?"))
            result = asyncio.run(load_messages("user1", "case1"))

        assert len(result) == 2
        assert result[0] == {"role": "user", "content": "Me duele la cabeza"}
        assert result[1] == {"role": "assistant", "content": "¿Desde cuándo?"}


# ---------------------------------------------------------------------------
# T1.3 — test_sliding_window_trim
# ---------------------------------------------------------------------------


class TestSlidingWindowTrim:
    def test_sliding_window_trim(self):
        """Append > WINDOW_SIZE messages → only last WINDOW_SIZE remain."""
        from app.memory.redis_window import WINDOW_SIZE, append_messages, load_messages

        fake = _make_fake_redis()
        # WINDOW_SIZE=20 → need >10 exchanges (each = 2 msgs) to exceed limit
        num_exchanges = WINDOW_SIZE // 2 + 1  # 11 exchanges = 22 messages
        with patch("app.memory.redis_window.redis_client", fake):
            for i in range(num_exchanges):
                asyncio.run(append_messages("user1", "case1", f"msg {i}", f"resp {i}"))
            result = asyncio.run(load_messages("user1", "case1"))

        assert len(result) == WINDOW_SIZE


# ---------------------------------------------------------------------------
# T1.4 — test_ttl_set_on_append
# ---------------------------------------------------------------------------


class TestTTLSetOnAppend:
    def test_ttl_set_on_append(self):
        """After append, the Redis key has a positive TTL."""
        from app.memory.redis_window import _key, append_messages

        fake = _make_fake_redis()
        with patch("app.memory.redis_window.redis_client", fake):
            asyncio.run(append_messages("user1", "case1", "hola", "hola"))
            ttl = asyncio.run(fake.ttl(_key("user1", "case1")))

        assert ttl > 0


# ---------------------------------------------------------------------------
# T1.5 — test_clear_messages
# ---------------------------------------------------------------------------


class TestClearMessages:
    def test_clear_messages(self):
        """After clear_messages → load returns []."""
        from app.memory.redis_window import append_messages, clear_messages, load_messages

        fake = _make_fake_redis()
        with patch("app.memory.redis_window.redis_client", fake):
            asyncio.run(append_messages("user1", "case1", "hola", "resp"))
            asyncio.run(clear_messages("user1", "case1"))
            result = asyncio.run(load_messages("user1", "case1"))

        assert result == []


# ---------------------------------------------------------------------------
# T1.6 — test_message_format
# ---------------------------------------------------------------------------


class TestMessageFormat:
    def test_message_format(self):
        """Stored messages have correct role and content fields."""
        from app.memory.redis_window import append_messages, load_messages

        fake = _make_fake_redis()
        with patch("app.memory.redis_window.redis_client", fake):
            asyncio.run(append_messages("u1", "c1", "pregunta del usuario", "respuesta del asistente"))
            msgs = asyncio.run(load_messages("u1", "c1"))

        assert set(msgs[0].keys()) == {"role", "content"}
        assert msgs[0]["role"] == "user"
        assert msgs[0]["content"] == "pregunta del usuario"
        assert msgs[1]["role"] == "assistant"
        assert msgs[1]["content"] == "respuesta del asistente"


# ---------------------------------------------------------------------------
# T1.7 — test_multiple_cases_isolated
# ---------------------------------------------------------------------------


class TestMultipleCasesIsolated:
    def test_multiple_cases_isolated(self):
        """Different case_ids for the same user are stored independently."""
        from app.memory.redis_window import append_messages, load_messages

        fake = _make_fake_redis()
        with patch("app.memory.redis_window.redis_client", fake):
            asyncio.run(append_messages("user1", "caseA", "hola A", "resp A"))
            asyncio.run(append_messages("user1", "caseB", "hola B", "resp B"))
            result_a = asyncio.run(load_messages("user1", "caseA"))
            result_b = asyncio.run(load_messages("user1", "caseB"))

        assert len(result_a) == 2
        assert len(result_b) == 2
        assert result_a[0]["content"] == "hola A"
        assert result_b[0]["content"] == "hola B"


# ---------------------------------------------------------------------------
# T1.8 — test_user_isolation
# ---------------------------------------------------------------------------


class TestUserIsolation:
    def test_user_isolation(self):
        """Same case_id but different user_ids are stored independently."""
        from app.memory.redis_window import append_messages, load_messages

        fake = _make_fake_redis()
        with patch("app.memory.redis_window.redis_client", fake):
            asyncio.run(append_messages("userA", "case1", "msg A", "resp A"))
            asyncio.run(append_messages("userB", "case1", "msg B", "resp B"))
            result_a = asyncio.run(load_messages("userA", "case1"))
            result_b = asyncio.run(load_messages("userB", "case1"))

        assert len(result_a) == 2
        assert len(result_b) == 2
        assert result_a[0]["content"] == "msg A"
        assert result_b[0]["content"] == "msg B"


# ---------------------------------------------------------------------------
# T1.9 — test_ws_message_loads_history
# ---------------------------------------------------------------------------


# UUID-formatted case_id required since chat.py validates the field as UUID
# (T2.3 — case ownership check). The two redis-memory WS tests must use a
# real UUID so they don't get rejected with code=invalid_message.
_TEST_CASE_ID = "11111111-1111-1111-1111-111111111111"


class TestWsMessageLoadsHistory:
    def test_ws_message_loads_history(self):
        """load_messages is called with (user_id, case_id) before graph execution."""
        mock_graph = _make_mock_graph([_done_event(_TEST_CASE_ID)])
        load_mock = AsyncMock(return_value=[])
        append_mock = AsyncMock()

        asyncio.run(
            _run_ws_one_message(
                content="hola doctor",
                case_id=_TEST_CASE_ID,
                mock_graph=mock_graph,
                load_mock=load_mock,
                append_mock=append_mock,
            )
        )

        load_mock.assert_called_once_with(
            "00000000-0000-0000-0000-000000000001", _TEST_CASE_ID
        )


# ---------------------------------------------------------------------------
# T1.10 — test_ws_message_saves_after_done
# ---------------------------------------------------------------------------


class TestWsMessageSavesAfterDone:
    def test_ws_message_saves_after_done(self):
        """append_messages is called after graph completes with the synthesized response."""
        response_text = "Parece una cefalea tensional."
        mock_graph = _make_mock_graph([_done_event(_TEST_CASE_ID, response_text)])
        load_mock = AsyncMock(return_value=[])
        append_mock = AsyncMock()

        asyncio.run(
            _run_ws_one_message(
                content="me duele la cabeza",
                case_id=_TEST_CASE_ID,
                mock_graph=mock_graph,
                load_mock=load_mock,
                append_mock=append_mock,
            )
        )

        append_mock.assert_called_once_with(
            "00000000-0000-0000-0000-000000000001",
            _TEST_CASE_ID,
            "me duele la cabeza",
            response_text,
        )
