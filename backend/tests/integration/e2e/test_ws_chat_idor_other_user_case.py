"""
E2E — Test 4: IDOR prevention — user B cannot send messages on user A's case.

User A owns case_a. User B connects with a valid JWT but supplies case_a.id
in the message payload. The server must reject the attempt.

Assertions:
  ✓ Server returns error frame with code=forbidden
  ✓ WebSocket stays open after the rejection (WS is not closed)
  ✓ No data from case_a or user_a leaks in any response frame
  ✓ User B can still send a valid message (own case) after the rejection
"""
from __future__ import annotations

import pytest
import websockets

from tests.integration.e2e._helpers import ws_auth, ws_message


@pytest.mark.integration
async def test_ws_chat_idor_other_user_case(
    ws_url,
    seed_user,
    seed_case,
):
    # ── Setup: user A owns case_a ─────────────────────────────────────
    user_a, token_a = await seed_user()
    _, _, case_a = await seed_case(user=user_a, token=token_a)

    # ── User B gets a valid JWT but does NOT own case_a ───────────────
    user_b, token_b = await seed_user()

    async with websockets.connect(ws_url + "/api/v1/chat/ws") as ws:
        auth_resp = await ws_auth(ws, token_b)
        assert auth_resp["type"] == "auth_ok", (
            f"User B auth failed unexpectedly: {auth_resp}"
        )

        # ── IDOR attempt: message referencing user A's case ───────────
        idor_frames = await ws_message(
            ws,
            content="Dame información del caso",
            case_id=str(case_a.id),
        )

        # ── Assertion 1: forbidden error received ─────────────────────
        error_frames = [f for f in idor_frames if f.get("type") == "error"]
        assert error_frames, (
            f"Expected an error frame for IDOR attempt, got: {idor_frames}. "
            "Case ownership check may be missing or not enforced."
        )
        assert error_frames[0]["code"] == "forbidden", (
            f"Expected code=forbidden, got: {error_frames[0]}. "
            "Any other code is also acceptable but must not be 'done'."
        )

        # ── Assertion 2: WS stays open (server uses `continue`, not close)
        # We verify this by sending a valid own-case message successfully.
        own_frames = await ws_message(ws, content="¿Puedo hacer una consulta?")

    done_frames = [f for f in own_frames if f["type"] == "done"]
    assert done_frames, (
        "WebSocket was closed after the IDOR rejection — expected it to stay "
        "open so the user can retry. "
        f"Own-case frames received: {own_frames}"
    )

    # ── Assertion 3: no data from case_a or user_a leaked ────────────
    all_text = " ".join(
        " ".join([
            str(f.get("response", "")),
            str(f.get("content", "")),
            str(f.get("message", "")),
        ])
        for f in idor_frames
    )
    assert str(user_a.id) not in all_text, (
        f"User A's ID ({user_a.id}) leaked in user B's response frames."
    )
    assert "E2E test case" not in all_text, (
        "case_a title leaked in user B's error response frames."
    )
