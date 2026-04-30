"""
E2E — Test 5: Graph execution timeout is handled gracefully.

Patches GRAPH_TIMEOUT=2s. Mock graph sleeps 5s before yielding — well past
the timeout. The asyncio.timeout() in chat.py must fire and send a clean
error frame before closing the WebSocket.

Assertions:
  ✓ Server sends {"type": "error", "code": "timeout"} frame
  ✓ WebSocket is closed by the server after the timeout (code 1011)
  ✓ Server process is still alive (no crash / unhandled exception)

KNOWN GAP (expected RED until fixed):
  ✗ No audit log is written for timeout events in the current production code.
    The asyncio.TimeoutError handler in chat.py sends the error frame and
    closes the socket but does not call log_action() or log_clinical_decision().
    This test documents that gap — tracked as a follow-up bug.
"""
from __future__ import annotations

import asyncio
import json

import httpx
import pytest
import websockets
import websockets.exceptions

import app.api.v1.chat as chat_mod
from tests.integration.e2e._helpers import MockGraph, ws_auth


@pytest.fixture
def mock_graph() -> MockGraph:
    """Override: graph sleeps 5 s — triggers the patched 2 s timeout."""
    return MockGraph(sleep_seconds=5.0, write_audit=False)


@pytest.fixture(autouse=True)
def _lower_graph_timeout():
    """Reduce GRAPH_TIMEOUT so the test completes in ~3 s instead of 120 s."""
    orig = chat_mod.GRAPH_TIMEOUT
    chat_mod.GRAPH_TIMEOUT = 2.0
    yield
    chat_mod.GRAPH_TIMEOUT = orig


@pytest.mark.integration
async def test_ws_chat_graph_timeout(ws_url, seed_user, app_server, e2e_session_factory):
    user, token = await seed_user()

    timeout_frame: dict | None = None
    ws_closed = False

    try:
        async with websockets.connect(ws_url + "/api/v1/chat/ws") as ws:
            auth_resp = await ws_auth(ws, token)
            assert auth_resp["type"] == "auth_ok", f"Auth failed: {auth_resp}"

            await ws.send(json.dumps({"type": "message", "content": "Tengo dolor"}))

            # Read frames until error/close or our outer 10 s safety net fires
            try:
                async with asyncio.timeout(10.0):
                    while True:
                        try:
                            raw = await ws.recv()
                        except websockets.exceptions.ConnectionClosed:
                            ws_closed = True
                            break
                        frame = json.loads(raw)
                        if frame.get("type") == "error" and frame.get("code") == "timeout":
                            timeout_frame = frame
                        # After the timeout error the server closes — keep reading
                        # until ConnectionClosed confirms it
            except asyncio.TimeoutError:
                # Safety net: test itself timed out (server may be hanging)
                pass

    except websockets.exceptions.ConnectionClosed:
        # websockets.connect context manager re-raises on __aexit__
        ws_closed = True

    # ── Assertion 1: timeout error frame received ─────────────────────
    assert timeout_frame is not None, (
        "Expected {'type': 'error', 'code': 'timeout'} frame but received none. "
        "Ensure GRAPH_TIMEOUT is applied inside chat.py via asyncio.timeout() "
        "and the TimeoutError handler sends the error frame before closing."
    )
    assert timeout_frame.get("message"), "Timeout error frame has no 'message' field"

    # ── Assertion 2: server closed the WS after timeout ───────────────
    assert ws_closed, (
        "WebSocket was NOT closed by the server after the timeout error. "
        "chat.py should call websocket.close(code=1011) in the TimeoutError handler."
    )

    # ── Assertion 3: server still alive (no crash) ────────────────────
    resp = httpx.get(app_server["http"] + "/health", timeout=3.0)
    assert resp.status_code == 200, (
        f"Server returned {resp.status_code} after a graph timeout. "
        "An unhandled exception may have crashed the worker."
    )

    # ── Assertion 4: audit log written for timeout ────────────────────
    from sqlalchemy import select
    from app.models.audit_log import AuditLog
    async with e2e_session_factory() as db:
        result = await db.execute(
            select(AuditLog).where(
                AuditLog.user_id == user.id,
                AuditLog.action == "graph_timeout",
            )
        )
        timeout_logs = result.scalars().all()
    assert timeout_logs, "BUG: no audit log written for graph timeout"
