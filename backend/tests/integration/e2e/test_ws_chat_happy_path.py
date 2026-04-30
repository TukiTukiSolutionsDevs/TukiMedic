"""
E2E — Test 1: WebSocket happy-path chat flow.

Full WS protocol exercise end-to-end:
  connect → auth → send message → receive streamed events → done frame

Assertions:
  ✓ auth_ok received with correct user_id
  ✓ done frame contains disclaimer string
  ✓ triage_decision audit log written to DB
  ✓ response_synthesized audit log written to DB
  ✓ exchange persisted in Redis L1 buffer (user + assistant messages)
"""
from __future__ import annotations

import json

import pytest
import websockets
from sqlalchemy import select

from app.models.audit_log import AuditLog
from tests.integration.e2e._helpers import ws_auth, ws_message


@pytest.mark.integration
async def test_ws_chat_happy_path(
    ws_url,
    seed_user,
    e2e_session_factory,
    e2e_redis_client,
):
    user, token = await seed_user()
    user_id = str(user.id)

    async with websockets.connect(ws_url + "/api/v1/chat/ws") as ws:
        # ── Auth phase ────────────────────────────────────────────────
        auth_resp = await ws_auth(ws, token)
        assert auth_resp["type"] == "auth_ok", (
            f"Expected auth_ok, got: {auth_resp}"
        )
        assert auth_resp["user_id"] == user_id, (
            f"auth_ok carries wrong user_id: {auth_resp}"
        )

        # ── Message phase ─────────────────────────────────────────────
        frames = await ws_message(ws, "Tengo dolor de cabeza desde hace 3 días")

    # ── done frame assertions ─────────────────────────────────────────
    done_frames = [f for f in frames if f["type"] == "done"]
    assert done_frames, f"No 'done' frame received. All frames: {frames}"
    done = done_frames[0]

    assert done["response"], "done frame has empty response"
    assert "AVISO MÉDICO" in done["response"] or "orientativa" in done["response"], (
        f"Response is missing the medical disclaimer.\nGot: {done['response'][:300]}"
    )

    case_id = done["case_id"]
    assert case_id, "done frame is missing case_id"

    # ── Audit log: triage_decision ────────────────────────────────────
    async with e2e_session_factory() as db:
        result = await db.execute(
            select(AuditLog).where(
                AuditLog.user_id == user.id,
                AuditLog.action == "triage_decision",
            )
        )
        triage_logs = result.scalars().all()

    assert triage_logs, (
        "No triage_decision audit log found in DB. "
        "The graph audit wrapper must write this entry."
    )
    assert triage_logs[0].details["urgency_level"] in ("green", "yellow", "red"), (
        f"Unexpected triage level in audit details: {triage_logs[0].details}"
    )

    # ── Audit log: response_synthesized ──────────────────────────────
    async with e2e_session_factory() as db:
        result = await db.execute(
            select(AuditLog).where(
                AuditLog.user_id == user.id,
                AuditLog.action == "response_synthesized",
            )
        )
        synth_logs = result.scalars().all()

    assert synth_logs, (
        "No response_synthesized audit log found in DB. "
        "The synthesizer audit wrapper must write this entry."
    )

    # ── Redis L1 buffer ───────────────────────────────────────────────
    redis_key = f"medagent:memory:{user_id}:{case_id}"
    raw_messages = await e2e_redis_client.lrange(redis_key, 0, -1)
    assert raw_messages, (
        f"No messages found in Redis L1 buffer. "
        f"Key: {redis_key} — append_messages must write after graph completes."
    )
    messages = [json.loads(m) for m in raw_messages]
    roles = {m["role"] for m in messages}
    assert "user" in roles, f"No user message in L1 buffer: {messages}"
    assert "assistant" in roles, f"No assistant message in L1 buffer: {messages}"
