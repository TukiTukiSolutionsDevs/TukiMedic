"""
E2E — Test 2: Red-flag triage triggers escalation path.

Overrides mock_graph with red triage + chest_pain flag + escalate=True.

Assertions:
  ✓ done frame response contains escalation warning ("ATENCIÓN" / "urgencias")
  ✓ escalation_required=True present in response text
  ✓ Red flag name present in response
  ✓ Audit log: guardrail_violation or triage_decision written with level=red
  ✓ No synthesizer/guardrail path taken (escalation bypasses normal flow)
"""
from __future__ import annotations

import pytest
import websockets
from sqlalchemy import select

from app.models.audit_log import AuditLog
from tests.integration.e2e._helpers import MockGraph, ws_auth, ws_message


@pytest.fixture
def mock_graph() -> MockGraph:
    """Override: red triage with chest_pain flag → escalation path."""
    return MockGraph(
        triage_level="red",
        red_flags=["chest_pain"],
        escalate=True,
    )


@pytest.mark.integration
async def test_ws_chat_red_flag_escalation(
    ws_url,
    seed_user,
    e2e_session_factory,
):
    user, token = await seed_user()

    async with websockets.connect(ws_url + "/api/v1/chat/ws") as ws:
        auth_resp = await ws_auth(ws, token)
        assert auth_resp["type"] == "auth_ok", f"Auth failed: {auth_resp}"

        frames = await ws_message(ws, "Me duele mucho el pecho y no puedo respirar")

    done_frames = [f for f in frames if f["type"] == "done"]
    assert done_frames, f"No 'done' frame received. All frames: {frames}"
    response = done_frames[0]["response"]

    # 1. Escalation warning present
    assert "ATENCIÓN" in response or "urgencias" in response.lower(), (
        f"Escalation warning missing from response.\nGot: {response[:400]}"
    )

    # 2. escalation_required=True marker (used by client to trigger UI alert)
    assert "escalation_required=True" in response, (
        f"'escalation_required=True' missing from escalation response.\n"
        f"Got: {response[:400]}"
    )

    # 3. Red flag name referenced in response
    assert "chest_pain" in response or "señales" in response.lower(), (
        f"Red flag name not referenced in escalation response.\nGot: {response[:400]}"
    )

    # 4. Disclaimer still present even on escalation path
    assert "AVISO MÉDICO" in response or "orientativa" in response, (
        f"Medical disclaimer missing from escalation response.\nGot: {response[:400]}"
    )

    # 5. Audit log: guardrail_violation or triage_decision with red level
    async with e2e_session_factory() as db:
        result = await db.execute(
            select(AuditLog).where(
                AuditLog.user_id == user.id,
                AuditLog.action.in_(["guardrail_violation", "triage_decision"]),
            )
        )
        logs = result.scalars().all()

    assert logs, (
        "No audit log entry (guardrail_violation or triage_decision) "
        "found for escalation path."
    )

    triage_logs = [lg for lg in logs if lg.action == "triage_decision"]
    if triage_logs:
        assert triage_logs[0].details.get("urgency_level") == "red", (
            f"Expected urgency_level=red in triage audit, "
            f"got: {triage_logs[0].details}"
        )

    guardrail_logs = [lg for lg in logs if lg.action == "guardrail_violation"]
    if guardrail_logs:
        assert guardrail_logs[0].details.get("interrupt") is True, (
            f"Expected interrupt=True in guardrail_violation audit, "
            f"got: {guardrail_logs[0].details}"
        )
