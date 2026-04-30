"""
WebSocket chat endpoint — contract tests (TDD).

Written BEFORE implementation (T4). Tests FAIL until T5 + T6 are complete.
Test runner: cd backend && poetry run pytest tests/api/v1/test_chat_ws.py
"""

import asyncio
import time
import uuid
from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from starlette.testclient import TestClient

from app.core.security import create_access_token, create_refresh_token
from app.main import app

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_user():
    user = MagicMock()
    user.id = _USER_ID
    user.is_active = True
    return user


@pytest.fixture
def user_access_token():
    return create_access_token({"sub": str(_USER_ID)})


@pytest.fixture
def user_refresh_token():
    return create_refresh_token({"sub": str(_USER_ID)})


@pytest.fixture
def expired_access_token():
    return create_access_token(
        {"sub": str(_USER_ID)}, expires_delta=timedelta(seconds=-3600)
    )


@pytest.fixture
def client():
    return TestClient(app)


# ---------------------------------------------------------------------------
# Mock helpers  (return patch() context managers — combine with `with`)
# ---------------------------------------------------------------------------


def _session_patch(mock_user):
    """Patch async_session to return mock_user on db.get(User, ...)."""
    mock_db = AsyncMock()
    mock_db.get = AsyncMock(return_value=mock_user)
    mock_db.add = MagicMock()
    mock_db.flush = AsyncMock()
    mock_db.commit = AsyncMock()

    mock_cm = AsyncMock()
    mock_cm.__aenter__ = AsyncMock(return_value=mock_db)
    mock_cm.__aexit__ = AsyncMock(return_value=False)

    return patch("app.api.v1.chat.async_session", MagicMock(return_value=mock_cm))


def _redis_patch(incr_value: int = 1):
    """Patch redis_client with a given incr return value."""
    mock_r = AsyncMock()
    mock_r.incr = AsyncMock(return_value=incr_value)
    mock_r.expire = AsyncMock(return_value=True)
    return patch("app.api.v1.chat.redis_client", mock_r)


def _default_events():
    """Async generator factory: triage agent_start + 2 tokens + synthesizer done."""

    async def _gen(state, config, version="v2"):
        yield {"event": "on_chain_start", "name": "triage", "data": {}}
        yield {
            "event": "on_chat_model_stream",
            "name": "triage",
            "data": {"chunk": MagicMock(content="Bas")},
        }
        yield {
            "event": "on_chat_model_stream",
            "name": "triage",
            "data": {"chunk": MagicMock(content="ado")},
        }
        yield {
            "event": "on_chain_end",
            "name": "synthesizer",
            "data": {"output": {"synthesized_response": "Basado en sus síntomas..."}},
        }

    return _gen


def _graph_patch(gen=None):
    """Patch get_or_build_graph to return a mock graph with given event generator."""
    graph = MagicMock()
    graph.astream_events = gen or _default_events()
    return patch(
        "app.api.v1.chat.get_or_build_graph", AsyncMock(return_value=graph)
    )


def _do_auth(ws, token):
    """Helper: send auth frame and assert auth_ok."""
    ws.send_json({"type": "auth", "token": token})
    msg = ws.receive_json()
    assert msg["type"] == "auth_ok", f"Expected auth_ok, got: {msg}"
    return msg


def _drain_to_done(ws, max_frames: int = 20):
    """Receive frames until 'done', return all collected frames."""
    frames = []
    for _ in range(max_frames):
        f = ws.receive_json()
        frames.append(f)
        if f["type"] == "done":
            break
    return frames


# ---------------------------------------------------------------------------
# Auth tests (7)
# ---------------------------------------------------------------------------


class TestAuth:
    def test_auth_success(self, client, mock_user, user_access_token):
        with _session_patch(mock_user):
            with client.websocket_connect("/api/v1/chat/ws") as ws:
                ws.send_json({"type": "auth", "token": user_access_token})
                msg = ws.receive_json()
                assert msg["type"] == "auth_ok"
                assert "user_id" in msg
                assert msg["user_id"] == str(_USER_ID)

    def test_auth_invalid_token(self, client):
        with client.websocket_connect("/api/v1/chat/ws") as ws:
            ws.send_json({"type": "auth", "token": "not-a-jwt"})
            msg = ws.receive_json()
            assert msg["type"] == "error"
            assert msg["code"] == "unauthorized"

    def test_auth_expired_token(self, client, expired_access_token):
        with client.websocket_connect("/api/v1/chat/ws") as ws:
            ws.send_json({"type": "auth", "token": expired_access_token})
            msg = ws.receive_json()
            assert msg["type"] == "error"
            assert msg["code"] == "unauthorized"

    def test_auth_wrong_type_refresh_token(self, client, user_refresh_token):
        """A refresh token must be rejected — only access tokens allowed."""
        with client.websocket_connect("/api/v1/chat/ws") as ws:
            ws.send_json({"type": "auth", "token": user_refresh_token})
            msg = ws.receive_json()
            assert msg["type"] == "error"
            assert msg["code"] == "unauthorized"

    def test_auth_timeout(self, client):
        """No auth message within timeout → error + close."""
        with patch("app.api.v1.chat.AUTH_TIMEOUT", 0.1):
            with client.websocket_connect("/api/v1/chat/ws") as ws:
                time.sleep(0.3)  # server times out at 0.1s
                msg = ws.receive_json()
                assert msg["type"] == "error"
                assert msg["code"] == "unauthorized"

    def test_auth_missing_type_field(self, client):
        """Message without 'type' field is not a valid auth frame."""
        with client.websocket_connect("/api/v1/chat/ws") as ws:
            ws.send_json({"token": "some-token"})
            msg = ws.receive_json()
            assert msg["type"] == "error"
            assert msg["code"] == "unauthorized"

    def test_auth_missing_token_field(self, client):
        """Auth message without 'token' field is rejected."""
        with client.websocket_connect("/api/v1/chat/ws") as ws:
            ws.send_json({"type": "auth"})
            msg = ws.receive_json()
            assert msg["type"] == "error"
            assert msg["code"] == "unauthorized"

    def test_auth_wrong_first_message_type(self, client):
        """Sending a non-auth frame as the first message is rejected."""
        with client.websocket_connect("/api/v1/chat/ws") as ws:
            ws.send_json({"type": "message", "content": "hello"})
            msg = ws.receive_json()
            assert msg["type"] == "error"
            assert msg["code"] == "unauthorized"


# ---------------------------------------------------------------------------
# Message processing tests (6)
# ---------------------------------------------------------------------------


class TestMessageProcessing:
    def test_send_message_receives_agent_start(
        self, client, mock_user, user_access_token
    ):
        with _session_patch(mock_user), _redis_patch(), _graph_patch():
            with client.websocket_connect("/api/v1/chat/ws") as ws:
                _do_auth(ws, user_access_token)
                ws.send_json({"type": "message", "content": "Me duele la cabeza"})
                frames = _drain_to_done(ws)
                types = [f["type"] for f in frames]
                assert "agent_start" in types

    def test_send_message_receives_tokens(self, client, mock_user, user_access_token):
        with _session_patch(mock_user), _redis_patch(), _graph_patch():
            with client.websocket_connect("/api/v1/chat/ws") as ws:
                _do_auth(ws, user_access_token)
                ws.send_json({"type": "message", "content": "test"})
                frames = _drain_to_done(ws)
                types = [f["type"] for f in frames]
                assert "token" in types

    def test_send_message_receives_done(self, client, mock_user, user_access_token):
        with _session_patch(mock_user), _redis_patch(), _graph_patch():
            with client.websocket_connect("/api/v1/chat/ws") as ws:
                _do_auth(ws, user_access_token)
                ws.send_json({"type": "message", "content": "test"})
                frames = _drain_to_done(ws)
                done = frames[-1]
                assert done["type"] == "done"
                assert "response" in done
                assert "case_id" in done

    def test_send_message_empty_content(self, client, mock_user, user_access_token):
        with _session_patch(mock_user):
            with client.websocket_connect("/api/v1/chat/ws") as ws:
                _do_auth(ws, user_access_token)
                ws.send_json({"type": "message", "content": ""})
                msg = ws.receive_json()
                assert msg["type"] == "error"
                assert msg["code"] == "invalid_message"

    def test_send_message_missing_content(self, client, mock_user, user_access_token):
        with _session_patch(mock_user):
            with client.websocket_connect("/api/v1/chat/ws") as ws:
                _do_auth(ws, user_access_token)
                ws.send_json({"type": "message"})
                msg = ws.receive_json()
                assert msg["type"] == "error"
                assert msg["code"] == "invalid_message"

    def test_multiple_messages_sequential(self, client, mock_user, user_access_token):
        with _session_patch(mock_user), _redis_patch(), _graph_patch():
            with client.websocket_connect("/api/v1/chat/ws") as ws:
                _do_auth(ws, user_access_token)
                for i in range(2):
                    ws.send_json({"type": "message", "content": f"mensaje {i}"})
                    frames = _drain_to_done(ws)
                    assert frames[-1]["type"] == "done"


# ---------------------------------------------------------------------------
# Error handling tests (3)
# ---------------------------------------------------------------------------


class TestClinicalSafetyA5:
    """Regression tests for fix A.5 — done frame must reflect post-guardrail response."""

    def test_done_carries_guardrail_rewrite_when_present(
        self, client, mock_user, user_access_token
    ):
        """If guardrail emits a modified response, `done` must use the modified one."""

        async def _events_with_guardrail_rewrite(state, config, version="v2"):
            yield {"event": "on_chain_start", "name": "synthesizer", "data": {}}
            yield {
                "event": "on_chain_end",
                "name": "synthesizer",
                "data": {"output": {"synthesized_response": "UNSAFE: tomá amoxicilina 500mg"}},
            }
            yield {"event": "on_chain_start", "name": "guardrail", "data": {}}
            yield {
                "event": "on_chain_end",
                "name": "guardrail",
                "data": {"output": {"synthesized_response": "Te sugiero consultar a tu médico antes de tomar medicación."}},
            }

        with _session_patch(mock_user), _redis_patch(), _graph_patch(_events_with_guardrail_rewrite):
            with client.websocket_connect("/api/v1/chat/ws") as ws:
                _do_auth(ws, user_access_token)
                ws.send_json({"type": "message", "content": "tengo dolor de garganta"})
                frames = _drain_to_done(ws)
                done = frames[-1]
                assert done["type"] == "done"
                assert "amoxicilina" not in done["response"]
                assert "consultar a tu médico" in done["response"]

    def test_done_uses_escalation_response_when_red_flag(
        self, client, mock_user, user_access_token
    ):
        """Triage-red path: escalation emits the urgent message; done must carry it."""

        async def _events_escalation(state, config, version="v2"):
            yield {"event": "on_chain_start", "name": "triage", "data": {}}
            yield {
                "event": "on_chain_end",
                "name": "escalation",
                "data": {"output": {"synthesized_response": "⚠️ ATENCIÓN: acude a urgencias."}},
            }

        with _session_patch(mock_user), _redis_patch(), _graph_patch(_events_escalation):
            with client.websocket_connect("/api/v1/chat/ws") as ws:
                _do_auth(ws, user_access_token)
                ws.send_json({"type": "message", "content": "dolor en el pecho irradiado"})
                frames = _drain_to_done(ws)
                done = frames[-1]
                assert done["type"] == "done"
                assert "ATENCIÓN" in done["response"]


class TestErrorHandling:
    def test_graph_error_sends_error_frame(
        self, client, mock_user, user_access_token
    ):
        async def _exploding(state, config, version="v2"):
            yield {"event": "on_chain_start", "name": "triage", "data": {}}
            raise RuntimeError("LLM API Error")

        with _session_patch(mock_user), _redis_patch(), _graph_patch(_exploding):
            with client.websocket_connect("/api/v1/chat/ws") as ws:
                _do_auth(ws, user_access_token)
                ws.send_json({"type": "message", "content": "test"})

                frames = []
                try:
                    for _ in range(10):
                        frames.append(ws.receive_json())
                except Exception:
                    pass

                error_frames = [f for f in frames if f["type"] == "error"]
                assert len(error_frames) >= 1
                assert error_frames[0]["code"] == "graph_error"

    def test_graph_timeout(self, client, mock_user, user_access_token):
        async def _slow(state, config, version="v2"):
            await asyncio.sleep(200)
            yield {}

        with patch("app.api.v1.chat.GRAPH_TIMEOUT", 0.1):
            with _session_patch(mock_user), _redis_patch(), _graph_patch(_slow):
                with client.websocket_connect("/api/v1/chat/ws") as ws:
                    _do_auth(ws, user_access_token)
                    ws.send_json({"type": "message", "content": "test"})

                    frames = []
                    try:
                        for _ in range(10):
                            frames.append(ws.receive_json())
                    except Exception:
                        pass

                    error_frames = [f for f in frames if f["type"] == "error"]
                    assert len(error_frames) >= 1
                    assert error_frames[0]["code"] == "timeout"

    def test_malformed_json(self, client, mock_user, user_access_token):
        with _session_patch(mock_user):
            with client.websocket_connect("/api/v1/chat/ws") as ws:
                _do_auth(ws, user_access_token)
                ws.send_text("not valid json {{{{{")
                msg = ws.receive_json()
                assert msg["type"] == "error"
                assert msg["code"] == "invalid_message"


# ---------------------------------------------------------------------------
# Rate limiting tests (2)
# ---------------------------------------------------------------------------


class TestRateLimiting:
    def test_rate_limit_allows_under_threshold(
        self, client, mock_user, user_access_token
    ):
        """Messages with count=1 (well under limit) all succeed."""
        with _session_patch(mock_user), _redis_patch(incr_value=1), _graph_patch():
            with client.websocket_connect("/api/v1/chat/ws") as ws:
                _do_auth(ws, user_access_token)
                for _ in range(3):
                    ws.send_json({"type": "message", "content": "test"})
                    frames = _drain_to_done(ws)
                    assert frames[-1]["type"] == "done"

    def test_rate_limit_blocks_over_threshold(
        self, client, mock_user, user_access_token
    ):
        """count=11 (> RATE_LIMIT_MAX=10) → rate_limited error, connection stays open."""
        with _session_patch(mock_user), _redis_patch(incr_value=11), _graph_patch():
            with client.websocket_connect("/api/v1/chat/ws") as ws:
                _do_auth(ws, user_access_token)
                ws.send_json({"type": "message", "content": "test"})
                msg = ws.receive_json()
                assert msg["type"] == "error"
                assert msg["code"] == "rate_limited"

                # Connection must stay open — ping still works
                ws.send_json({"type": "ping"})
                pong = ws.receive_json()
                assert pong["type"] == "pong"


# ---------------------------------------------------------------------------
# Heartbeat tests (2)
# ---------------------------------------------------------------------------


class TestHeartbeat:
    def test_heartbeat_ping(self, client, mock_user, user_access_token):
        """Client sends ping → server responds immediately with pong."""
        with _session_patch(mock_user):
            with client.websocket_connect("/api/v1/chat/ws") as ws:
                _do_auth(ws, user_access_token)
                ws.send_json({"type": "ping"})
                msg = ws.receive_json()
                assert msg == {"type": "pong"}

    def test_server_sends_heartbeat(self, client, mock_user, user_access_token):
        """Server proactively sends pong every HEARTBEAT_INTERVAL seconds."""
        with patch("app.api.v1.chat.HEARTBEAT_INTERVAL", 0.1):
            with _session_patch(mock_user):
                with client.websocket_connect("/api/v1/chat/ws") as ws:
                    _do_auth(ws, user_access_token)
                    time.sleep(0.35)  # wait > 3× the interval
                    msg = ws.receive_json()
                    assert msg["type"] == "pong"
