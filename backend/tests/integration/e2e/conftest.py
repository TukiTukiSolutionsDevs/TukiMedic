"""
E2E WebSocket integration fixtures.

Spins up a real FastAPI/uvicorn server backed by testcontainers
(PostgreSQL + Redis inherited from tests/integration/conftest.py).
LLM calls are replaced by a configurable MockGraph that implements the
same astream_events interface as the compiled LangGraph StateGraph.

All module-level DB/Redis references inside the running app are
monkey-patched BEFORE uvicorn starts (session-scoped _patch_app fixture).
The mock graph is swapped per test via _patch_graph (function-scoped autouse).

Run:
    RUN_INTEGRATION=1 poetry run pytest tests/integration/e2e/ -m integration -v
"""
from __future__ import annotations

import socket
import threading
import time
import uuid

import httpx
import pytest
import redis.asyncio as redis_aio
import uvicorn
from sqlalchemy.pool import NullPool
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.security import create_access_token, get_password_hash
from app.models.case import Case
from app.models.user import User

from tests.integration.e2e._helpers import MockGraph  # noqa: F401 — re-exported for tests


# ---------------------------------------------------------------------------
# Redis
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def e2e_redis_url(redis_container) -> str:
    """Redis URL pointing to the testcontainer — DB 2 to isolate from other tests."""
    host = redis_container.get_container_host_ip()
    port = redis_container.get_exposed_port(6379)
    return f"redis://{host}:{port}/2"


@pytest.fixture
async def e2e_redis_client(e2e_redis_url) -> redis_aio.Redis:
    """
    Fresh Redis client per test — safe in the test's own event loop.

    Session-scoped clients bind their connection pool to the first event loop
    that calls them. pytest-asyncio creates a NEW loop per test, so a
    session-scoped client raises 'Future attached to a different loop' from
    the second test onward. A function-scoped client avoids this entirely.
    """
    client = redis_aio.from_url(e2e_redis_url, decode_responses=True)
    yield client
    await client.aclose()


@pytest.fixture(autouse=True)
def mock_memory_redis_client():
    """
    No-op override of the root conftest's autouse mock_memory_redis_client.

    Root conftest replaces app.memory.redis_window.redis_client with a
    MagicMock. For E2E tests we do NOT want that — _patch_app already
    points rw.redis_client at the testcontainer Redis client that uvicorn
    uses (in uvicorn's own event loop). We only need to prevent the root
    fixture from clobbering that patch.

    pytest resolves the fixture from the closest conftest, so this wins.
    """
    yield


# ---------------------------------------------------------------------------
# Session factory — NullPool avoids asyncpg event-loop binding
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def e2e_session_factory(pg_async_url, run_migrations) -> async_sessionmaker:
    """
    Session-scoped async session factory for the testcontainer DB.

    NullPool: each ``async with factory() as db:`` creates a fresh connection
    in whatever event loop calls it, making it safe to use from both the
    uvicorn event loop and per-test event loops.
    """
    engine = create_async_engine(pg_async_url, poolclass=NullPool, echo=False)
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


# ---------------------------------------------------------------------------
# Module-level monkey-patching (must run BEFORE uvicorn starts)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def _patch_app(e2e_session_factory, e2e_redis_url, run_migrations):
    """
    Replace all module-level DB/Redis references in the running FastAPI app
    with testcontainer-backed equivalents.

    chat.py does ``from app.core.database import async_session`` at import
    time, so ``app.api.v1.chat.async_session`` is a local name binding.
    Replacing that name in the module namespace is enough — Python resolves
    attribute lookups at runtime, so the running handler sees the new value.

    A dedicated ``uvicorn_redis`` client is created here (not shared with
    tests) so that uvicorn's event loop owns its connection pool. Per-test
    assertions use a separate function-scoped ``e2e_redis_client`` that is
    created fresh in each test's event loop, avoiding cross-loop errors.

    Must be session-scoped and listed as a dependency of ``app_server`` to
    guarantee patches are applied before uvicorn handles any request.
    """
    import app.api.v1.chat as chat_mod
    import app.core.redis as core_redis_mod
    import app.memory.redis_window as rw_mod
    import app.orchestrator.graph as graph_mod

    # Redis client that uvicorn's event loop will own
    uvicorn_redis = redis_aio.from_url(e2e_redis_url, decode_responses=True)

    # -- DB session factories --
    orig_chat_session = chat_mod.async_session
    orig_graph_session = graph_mod.async_session

    chat_mod.async_session = e2e_session_factory
    graph_mod.async_session = e2e_session_factory

    # -- Redis clients: rate limiting, health-check ping, L1 memory --
    orig_core_redis = core_redis_mod.redis_client
    orig_chat_redis = chat_mod.redis_client
    orig_rw_redis = rw_mod.redis_client

    core_redis_mod.redis_client = uvicorn_redis
    chat_mod.redis_client = uvicorn_redis
    rw_mod.redis_client = uvicorn_redis  # L1 sliding-window memory

    yield

    # Restore after the session so other integration tests are unaffected
    chat_mod.async_session = orig_chat_session
    graph_mod.async_session = orig_graph_session
    core_redis_mod.redis_client = orig_core_redis
    chat_mod.redis_client = orig_chat_redis
    rw_mod.redis_client = orig_rw_redis


# ---------------------------------------------------------------------------
# Per-test graph mock (function-scoped, autouse)
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_graph() -> MockGraph:
    """Default mock graph: yellow triage, standard disclaimer, no escalation."""
    return MockGraph()


@pytest.fixture(autouse=True)
def _patch_graph(mock_graph, _patch_app):
    """
    Replace ``get_or_build_graph`` with a function that returns ``mock_graph``.

    Function-scoped so each test can inject a different MockGraph scenario
    by overriding the ``mock_graph`` fixture locally. The patch is reverted
    after each test.

    Because ``_patch_app`` is a dependency, this fixture also implicitly
    ensures module patches are active before _patch_graph runs.
    """
    import app.api.v1.chat as chat_mod

    original = chat_mod.get_or_build_graph

    async def _fake_get_or_build_graph(user_id: str):  # noqa: ARG001
        return mock_graph

    chat_mod.get_or_build_graph = _fake_get_or_build_graph
    yield
    chat_mod.get_or_build_graph = original


# ---------------------------------------------------------------------------
# Uvicorn server (session-scoped — one server for all E2E tests)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def app_server(_patch_app):
    """
    Start the FastAPI app on a free port via uvicorn in a daemon thread.

    Blocks up to 5 s waiting for /health to respond, then yields a dict
    with ``http`` and ``ws`` base URLs.  The ``_patch_app`` dependency
    guarantees all module-level patches are in place before any request.
    """
    from app.main import app as fastapi_app

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]

    config = uvicorn.Config(
        fastapi_app,
        host="127.0.0.1",
        port=port,
        log_level="error",
        loop="asyncio",
        access_log=False,
    )
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    deadline = time.monotonic() + 5.0
    while time.monotonic() < deadline:
        try:
            resp = httpx.get(f"http://127.0.0.1:{port}/health", timeout=0.3)
            if resp.status_code == 200:
                break
        except Exception:
            pass
        time.sleep(0.05)
    else:
        server.should_exit = True
        pytest.fail("E2E uvicorn server failed to start within 5 seconds")

    yield {
        "http": f"http://127.0.0.1:{port}",
        "ws": f"ws://127.0.0.1:{port}",
    }

    server.should_exit = True
    thread.join(timeout=5)


@pytest.fixture
def ws_url(app_server) -> str:
    """WS base URL for the running test server."""
    return app_server["ws"]


# ---------------------------------------------------------------------------
# User / case seeding helpers
# ---------------------------------------------------------------------------


@pytest.fixture
async def seed_user(e2e_session_factory):
    """
    Async factory fixture. Call ``await seed_user()`` to create a user and
    receive ``(user, jwt_token)``.  Cleans up created users after the test.

    Example::

        async def test_foo(seed_user):
            user, token = await seed_user()
    """
    created_ids: list[uuid.UUID] = []

    async def _make(
        email: str | None = None,
        role: str = "customer",
        password: str = "E2ETestPass123!",
    ) -> tuple[User, str]:
        if email is None:
            email = f"e2e-{uuid.uuid4().hex[:8]}@test.local"
        user = User(
            id=uuid.uuid4(),
            email=email,
            password_hash=get_password_hash(password),
            display_name="E2E Test User",
            role=role,
            is_active=True,
            is_verified=True,
        )
        async with e2e_session_factory() as db:
            db.add(user)
            await db.commit()
            await db.refresh(user)
        token = create_access_token({"sub": str(user.id), "role": role})
        created_ids.append(user.id)
        return user, token

    yield _make
    # No teardown — testcontainer is destroyed at session end.
    # Deleting users mid-session would violate FK constraints from
    # patient_profiles / cases / audit_logs that the running app creates.


@pytest.fixture
async def seed_case(e2e_session_factory, seed_user):
    """
    Async factory: creates a Case for a given user (or creates the user too).

    Returns ``(user, token, case)``.

    Example::

        async def test_foo(seed_case):
            user, token, case = await seed_case()
    """

    async def _make(
        user: User | None = None,
        token: str | None = None,
    ) -> tuple[User, str, Case]:
        if user is None:
            user, token = await seed_user()
        assert token is not None

        case = Case(
            id=uuid.uuid4(),
            user_id=user.id,
            title="E2E test case",
            status="active",
        )
        async with e2e_session_factory() as db:
            db.add(case)
            await db.commit()
            await db.refresh(case)
        return user, token, case

    yield _make
