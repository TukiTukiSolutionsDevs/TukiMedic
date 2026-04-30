"""
WebSocket chat endpoint — /api/v1/chat/ws

Protocol:
  1. Client connects (origin check)
  2. Client sends first message: {"type":"auth","token":"<JWT access token>"}
  3. Server validates JWT → sends auth_ok or error+close(1008)
  4. Heartbeat background task sends {"type":"pong"} every HEARTBEAT_INTERVAL seconds
  5. Client sends {"type":"message","content":"...","case_id":"<uuid|null>"}
  6. Server rate-limits, builds/fetches graph, streams events as WS frames
  7. On disconnect or error, cleanup and exit

Event → frame mapping (LangGraph astream_events v2):
  on_chain_start  (not internal)  → {"type":"agent_start","agent":"<name>"}
  on_chat_model_stream            → {"type":"token","content":"<chunk>"}

The `done` frame is NOT emitted from event handler — it is emitted at the
end of the graph stream so the response is post-guardrail (clinical safety
fix A.5). Tokens streamed during synthesizer ARE seen by the user, but the
authoritative final response carried by the `done` frame reflects any
guardrail rewrites (severity=modify) and disclaimer concatenation.
"""

import asyncio
import json
import uuid

from fastapi import APIRouter
from starlette.websockets import WebSocket, WebSocketDisconnect

from app.core.config import settings
from app.core.database import async_session
from app.core.graph_cache import get_or_build_graph
from app.core.redis import redis_client
from app.core.security import decode_token
from app.memory import append_messages, load_messages, retrieve_relevant_facts, store_facts
from app.memory.pg_timeline import get_patient_timeline, get_or_create_profile, store_timeline_event
from app.memory.kb_retriever import retrieve_kb_context
from app.services.document_context import get_document_context, message_references_documents
from app.models.case import Case
from app.models.user import User
from app.orchestrator.graph import create_initial_state

chat_router = APIRouter(prefix="/chat", tags=["chat"])

# ---------------------------------------------------------------------------
# Module-level constants — patchable in tests
# ---------------------------------------------------------------------------

AUTH_TIMEOUT: float = 10.0        # seconds to wait for first auth message
GRAPH_TIMEOUT: float = 120.0      # max seconds for graph execution per message
HEARTBEAT_INTERVAL: float = 30.0  # seconds between server-initiated pongs
RATE_LIMIT_MAX: int = 10          # max messages per RATE_LIMIT_WINDOW
RATE_LIMIT_WINDOW: int = 60       # rate limit window in seconds

# ---------------------------------------------------------------------------
# LangGraph internal node names — filtered from agent_start events
# ---------------------------------------------------------------------------

_SKIP_NODES = frozenset({"LangGraph", "__start__", "ChannelWrite", "ChannelRead", "__end__"})


# ---------------------------------------------------------------------------
# Heartbeat background task
# ---------------------------------------------------------------------------

async def _heartbeat(ws: WebSocket, stop: asyncio.Event) -> None:
    """Send {'type':'pong'} every HEARTBEAT_INTERVAL seconds until stop is set."""
    while not stop.is_set():
        try:
            await asyncio.sleep(HEARTBEAT_INTERVAL)
            await ws.send_json({"type": "pong"})
        except Exception:
            break


# ---------------------------------------------------------------------------
# LangGraph event → WebSocket frame mapper
# ---------------------------------------------------------------------------

# Nodes whose `synthesized_response` output is considered the authoritative
# final response for the `done` frame. Order matters: later wins.
# - synthesizer: produces the candidate response
# - guardrail:   may rewrite it (severity=modify) or interrupt
# - escalation:  emits the urgent-care fallback when triage flags red
_FINAL_RESPONSE_NODES = ("synthesizer", "guardrail", "escalation")


async def _handle_event(ws: WebSocket, event: dict, case_id: str) -> None:
    """Map one LangGraph astream_events v2 event to a WebSocket frame, or no-op.

    NOTE: the `done` frame is intentionally NOT emitted here. It is sent
    after the graph stream terminates so the response is post-guardrail.
    See clinical safety fix A.5.
    """
    kind: str = event.get("event", "")
    name: str = event.get("name", "")

    if kind == "on_chain_start" and name not in _SKIP_NODES:
        await ws.send_json({"type": "agent_start", "agent": name})

    elif kind == "on_chat_model_stream":
        chunk = event.get("data", {}).get("chunk")
        content = getattr(chunk, "content", "") or ""
        if content:
            await ws.send_json({"type": "token", "content": content})


# ---------------------------------------------------------------------------
# WebSocket endpoint
# ---------------------------------------------------------------------------

@chat_router.websocket("/ws")
async def websocket_chat(websocket: WebSocket) -> None:
    """Main WebSocket handler for the clinical AI chat stream."""
    # Origin guard — only reject if Origin header is present AND not in allowlist
    origin = websocket.headers.get("origin", "")
    if origin and origin not in set(settings.ALLOWED_ORIGINS):
        await websocket.close(code=1008)
        return

    await websocket.accept()

    stop_event = asyncio.Event()
    heartbeat_task = asyncio.create_task(_heartbeat(websocket, stop_event))

    try:
        # ── Auth phase ────────────────────────────────────────────────────────
        user = None
        try:
            raw = await asyncio.wait_for(
                websocket.receive_text(), timeout=AUTH_TIMEOUT
            )
            msg = json.loads(raw)
            if msg.get("type") != "auth" or "token" not in msg:
                raise ValueError("bad auth message")
            payload = decode_token(msg["token"])
            if payload.get("type") != "access":
                raise ValueError("not an access token")
            user_id = uuid.UUID(payload["sub"])
            async with async_session() as db:
                user = await db.get(User, user_id)
            if user is None or not user.is_active:
                raise ValueError("user not found or inactive")
        except Exception:
            try:
                await websocket.send_json(
                    {
                        "type": "error",
                        "code": "unauthorized",
                        "message": "Authentication failed",
                    }
                )
                await websocket.close(code=1008)
            except Exception:
                pass
            return

        await websocket.send_json({"type": "auth_ok", "user_id": str(user.id)})

        # ── Message loop ──────────────────────────────────────────────────────
        while True:
            try:
                raw = await websocket.receive_text()
            except WebSocketDisconnect:
                break

            # Parse JSON
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                await websocket.send_json(
                    {
                        "type": "error",
                        "code": "invalid_message",
                        "message": "Invalid JSON",
                    }
                )
                continue

            msg_type = msg.get("type")

            # Client ping → immediate pong (before any other processing)
            if msg_type == "ping":
                await websocket.send_json({"type": "pong"})
                continue

            # Silently ignore unknown frame types
            if msg_type != "message":
                continue

            # Validate content
            content = msg.get("content", "").strip()
            if not content:
                await websocket.send_json(
                    {
                        "type": "error",
                        "code": "invalid_message",
                        "message": "content required",
                    }
                )
                continue

            client_case_id = msg.get("case_id")
            case_id_str: str = client_case_id or str(uuid.uuid4())

            # ── Case ownership validation (T2.3) ──────────────────────────
            # If the client supplied a case_id (not auto-generated), check
            # that the case is owned by the authenticated user. A malicious
            # client could otherwise resume / poison another user's session.
            if client_case_id:
                try:
                    case_uuid = uuid.UUID(client_case_id)
                except (TypeError, ValueError):
                    await websocket.send_json(
                        {
                            "type": "error",
                            "code": "invalid_message",
                            "message": "case_id must be a UUID",
                        }
                    )
                    continue

                async with async_session() as db:
                    existing = await db.get(Case, case_uuid)
                if existing is not None and existing.user_id != user.id:
                    await websocket.send_json(
                        {
                            "type": "error",
                            "code": "forbidden",
                            "message": "Case does not belong to this user",
                        }
                    )
                    continue

            # Rate limiting — Redis INCR + EXPIRE pattern
            rate_key = f"ws:ratelimit:{user.id}"
            count = await redis_client.incr(rate_key)
            if count == 1:
                await redis_client.expire(rate_key, RATE_LIMIT_WINDOW)
            if count > RATE_LIMIT_MAX:
                await websocket.send_json(
                    {
                        "type": "error",
                        "code": "rate_limited",
                        "message": "Rate limit exceeded. Wait 60s.",
                    }
                )
                continue  # keep connection open

            # Graph execution
            history = await load_messages(str(user.id), case_id_str)
            graph = await get_or_build_graph(str(user.id))
            state = create_initial_state(case_id_str, str(user.id), content)
            state["messages"] = history  # inject conversation history

            # Level 2 — inject relevant clinical facts from PostgreSQL (graceful degradation)
            try:
                async with async_session() as db:
                    relevant_facts = await retrieve_relevant_facts(
                        db, str(user.id), content, settings.OPENAI_API_KEY
                    )
                    state["extracted_facts"] = relevant_facts
            except Exception:
                pass  # L2 failure must not block chat

            # Level 3 — inject patient timeline + profile (graceful degradation)
            try:
                async with async_session() as db:
                    state["patient_timeline"] = await get_patient_timeline(db, str(user.id))
                    state["patient_profile"] = await get_or_create_profile(db, str(user.id))
                    await db.commit()
            except Exception:
                pass  # L3 failure must not block chat

            # Level 3 — inject KB context via semantic search (graceful degradation)
            try:
                async with async_session() as db:
                    state["kb_context"] = await retrieve_kb_context(
                        db, content, settings.OPENAI_API_KEY
                    )
            except Exception:
                pass  # KB failure must not block chat

            # Level 3 — inject document context if message references docs (graceful degradation)
            if message_references_documents(content):
                try:
                    async with async_session() as doc_db:
                        doc_context = await get_document_context(
                            doc_db, str(user.id), case_id_str
                        )
                        state["document_context"] = doc_context
                except Exception:
                    pass  # Document context failure must not block chat

            config = {"configurable": {"thread_id": case_id_str}}

            response_text: str | None = None
            captured_facts: list = []
            try:
                async with asyncio.timeout(GRAPH_TIMEOUT):
                    async for event in graph.astream_events(state, config, version="v2"):
                        await _handle_event(websocket, event, case_id_str)
                        # Capture authoritative response from final-response
                        # nodes. Order in graph guarantees later overwrites:
                        # synthesizer → guardrail (may rewrite) → escalation.
                        if (
                            event.get("event") == "on_chain_end"
                            and event.get("name") in _FINAL_RESPONSE_NODES
                        ):
                            new_response = (
                                event.get("data", {})
                                .get("output", {})
                                .get("synthesized_response")
                            )
                            if new_response:
                                response_text = new_response
                        # Capture extracted clinical facts from anamnesis node
                        if (
                            event.get("event") == "on_chain_end"
                            and event.get("name") == "anamnesis"
                        ):
                            captured_facts = (
                                event.get("data", {})
                                .get("output", {})
                                .get("extracted_facts", [])
                            )
            except asyncio.TimeoutError:
                await websocket.send_json(
                    {
                        "type": "error",
                        "code": "timeout",
                        "message": "Graph execution timed out",
                    }
                )
                await websocket.close(code=1011)
                break
            except Exception:
                # T3.4 — never echo internal exceptions to the client. The
                # full traceback is logged server-side; the user sees a
                # bounded, generic error code so we don't leak provider
                # details / SQL / paths.
                import logging
                logging.getLogger(__name__).exception(
                    "graph execution failed for case=%s", case_id_str
                )
                await websocket.send_json(
                    {
                        "type": "error",
                        "code": "graph_error",
                        "message": "Hubo un error procesando tu consulta. Reintentá en unos minutos.",
                    }
                )
                await websocket.close(code=1011)
                break

            # ── Emit final `done` frame post-guardrail (clinical safety A.5) ──
            # response_text was captured from the LAST chain_end of synthesizer
            # / guardrail / escalation, so it reflects any guardrail rewrite or
            # the escalation message. If somehow none fired, we still emit a
            # done frame with empty response so the client knows the turn ended.
            await websocket.send_json(
                {
                    "type": "done",
                    "response": response_text or "",
                    "case_id": case_id_str,
                }
            )

            # Persist exchange to memory (only on successful graph completion)
            if response_text is not None:
                await append_messages(str(user.id), case_id_str, content, response_text)

            # Level 3 — store timeline event for completed consultation (graceful degradation)
            if response_text is not None:
                try:
                    async with async_session() as db:
                        await store_timeline_event(
                            db,
                            str(user.id),
                            case_id_str,
                            "consultation",
                            content[:500],  # brief summary from user message
                        )
                        await db.commit()
                except Exception:
                    pass  # timeline store failure must not block chat

            # Level 2 — persist extracted clinical facts to PostgreSQL (graceful degradation)
            try:
                if captured_facts:
                    facts_to_store = [
                        f.model_dump() if hasattr(f, "model_dump") else f
                        for f in captured_facts
                    ]
                    async with async_session() as db:
                        await store_facts(
                            db, str(user.id), case_id_str, facts_to_store, settings.OPENAI_API_KEY
                        )
                        await db.commit()
            except Exception:
                pass  # L2 failure must not block chat

    finally:
        stop_event.set()
        heartbeat_task.cancel()
        try:
            await heartbeat_task
        except asyncio.CancelledError:
            pass
