"""
E2E test helpers — MockGraph and WebSocket protocol utilities.

Importable from test files directly (not pytest fixtures).
"""
from __future__ import annotations

import asyncio
import json
import uuid


# ---------------------------------------------------------------------------
# Deterministic mock for the compiled LangGraph StateGraph
# ---------------------------------------------------------------------------


class MockGraph:
    """
    Stand-in for the compiled LangGraph.  Yields astream_events compatible
    with what chat.py expects and optionally writes audit log entries so
    DB assertions in tests work without a real LLM.

    Configure via constructor kwargs; override the `mock_graph` fixture per
    test to inject different scenarios.
    """

    DISCLAIMER = (
        "AVISO MÉDICO: Esta información es orientativa y no reemplaza "
        "la consulta médica profesional."
    )

    def __init__(
        self,
        *,
        response: str | None = None,
        triage_level: str = "yellow",
        red_flags: list[str] | None = None,
        escalate: bool = False,
        # Sleep BEFORE yielding anything → triggers asyncio.timeout in chat.py
        sleep_seconds: float = 0.0,
        write_audit: bool = True,
    ) -> None:
        if response is None:
            response = f"Consulta procesada correctamente. {self.DISCLAIMER}"
        self.response = response
        self.triage_level = triage_level
        self.red_flags = red_flags or []
        self.escalate = escalate
        self.sleep_seconds = sleep_seconds
        self.write_audit = write_audit

    # ------------------------------------------------------------------
    # Audit helper — uses the patched async_session (testcontainer DB)
    # ------------------------------------------------------------------

    async def _maybe_audit(
        self, state: dict, action: str, details: dict
    ) -> None:
        if not self.write_audit:
            return
        try:
            # Import at call-time so we get the PATCHED module attribute
            from app.orchestrator.graph import async_session  # type: ignore[attr-defined]
            from app.services.audit import log_clinical_decision

            case_raw = state.get("case_id", "")
            case_id = uuid.UUID(case_raw) if case_raw else uuid.uuid4()
            user_raw = state.get("user_id", "")
            user_id = uuid.UUID(user_raw) if user_raw else None

            async with async_session() as db:
                await log_clinical_decision(
                    db,
                    case_id=case_id,
                    action=action,
                    details=details,
                    model_version="mock@e2e-test-v1",
                    user_id=user_id,
                )
                await db.commit()
        except Exception:
            pass  # audit failure must never block the flow

    # ------------------------------------------------------------------
    # astream_events — the interface chat.py drives
    # ------------------------------------------------------------------

    async def astream_events(  # noqa: C901
        self, state: dict, config: dict, version: str = "v2"
    ):
        # Simulate slow graph — BEFORE yielding so asyncio.timeout fires cleanly
        if self.sleep_seconds > 0:
            await asyncio.sleep(self.sleep_seconds)

        # ── Triage ──────────────────────────────────────────────────────
        yield {"event": "on_chain_start", "name": "triage", "data": {}}
        yield {
            "event": "on_chain_end",
            "name": "triage",
            "data": {
                "output": {
                    "triage_level": self.triage_level,
                    "triage_confidence": 0.85,
                    "red_flags": self.red_flags,
                }
            },
        }
        await self._maybe_audit(
            state,
            "triage_decision",
            {
                "urgency_level": self.triage_level,
                "red_flags_detected": self.red_flags,
                "confidence": 0.85,
            },
        )

        if self.escalate:
            # ── Escalation path (red triage) ────────────────────────────
            flags_str = (
                ", ".join(self.red_flags) if self.red_flags else "señales de alarma"
            )
            escalation_msg = (
                "⚠️ ATENCIÓN: Se detectaron señales que requieren atención "
                "médica inmediata.\n\n"
                f"Señales detectadas: {flags_str}\n\n"
                "Por favor, acude a urgencias o llama a servicios de emergencia "
                "lo antes posible.\n\n"
                "escalation_required=True\n\n"
                f"{self.DISCLAIMER}"
            )
            yield {"event": "on_chain_start", "name": "escalation", "data": {}}
            yield {
                "event": "on_chain_end",
                "name": "escalation",
                "data": {"output": {"synthesized_response": escalation_msg}},
            }
            await self._maybe_audit(
                state,
                "guardrail_violation",
                {
                    "violations": [{"type": "red_flag", "flags": self.red_flags}],
                    "interrupt": True,
                },
            )
        else:
            # ── Normal path: synthesizer → guardrail ────────────────────
            yield {"event": "on_chain_start", "name": "synthesizer", "data": {}}
            yield {
                "event": "on_chain_end",
                "name": "synthesizer",
                "data": {"output": {"synthesized_response": self.response}},
            }
            await self._maybe_audit(
                state,
                "response_synthesized",
                {
                    "attention_level": "moderate",
                    "response_length": len(self.response),
                },
            )

            yield {"event": "on_chain_start", "name": "guardrail", "data": {}}
            yield {
                "event": "on_chain_end",
                "name": "guardrail",
                "data": {
                    "output": {
                        "synthesized_response": self.response,
                        "guardrail_interrupt": False,
                    }
                },
            }


# ---------------------------------------------------------------------------
# WebSocket protocol helpers
# ---------------------------------------------------------------------------


async def ws_auth(ws, token: str) -> dict:
    """Send the auth frame and return the server's response dict."""
    await ws.send(json.dumps({"type": "auth", "token": token}))
    return json.loads(await ws.recv())


async def ws_message(
    ws,
    content: str,
    case_id: str | None = None,
    recv_timeout: float = 25.0,
) -> list[dict]:
    """
    Send one chat message and collect ALL frames until ``done`` or ``error``.

    Returns the collected frames (may include agent_start, token, done, error).
    Stops on ConnectionClosed as well (graceful handling for timeout tests).
    """
    import websockets.exceptions  # local import — not a fixture dep

    payload: dict = {"type": "message", "content": content}
    if case_id is not None:
        payload["case_id"] = case_id
    await ws.send(json.dumps(payload))

    frames: list[dict] = []
    while True:
        try:
            raw = await asyncio.wait_for(ws.recv(), timeout=recv_timeout)
        except (asyncio.TimeoutError, websockets.exceptions.ConnectionClosed):
            break
        frame = json.loads(raw)
        frames.append(frame)
        if frame.get("type") in ("done", "error"):
            break
    return frames
