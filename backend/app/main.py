import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from sqlalchemy import text

from app.api.v1.admin import router as admin_router
from app.api.v1.auth import router as auth_router
from app.api.v1.chat import chat_router
from app.api.v1.documents import router as documents_router
from app.api.v1.export import router as export_router
from app.core.config import settings
from app.core.database import async_session
from app.core.logging_setup import configure_logging
from app.core.rate_limit import limiter
from app.core.redis import redis_client
from app.core.storage import storage_client

configure_logging()
log = logging.getLogger(__name__)

# NOTE: OPENAI_API_KEY is no longer injected into os.environ at boot (S4.0.d).
# The LLM router fetches the active credential from the encrypted vault and
# passes api_key + base_url explicitly to each agent via ChatOpenAI kwargs.
# OPENAI_API_BASE is still propagated for memory/embedding services that have
# not yet been migrated to the vault.
if settings.OPENAI_API_BASE:
    import os
    os.environ.setdefault("OPENAI_API_BASE", settings.OPENAI_API_BASE)
    os.environ.setdefault("OPENAI_BASE_URL", settings.OPENAI_API_BASE)

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="MedAgent — Plataforma Conversacional Clínica Orquestada",
)

# Rate limiting — must be wired before routers so middleware sees every request.
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(auth_router, prefix=settings.API_V1_PREFIX)
app.include_router(chat_router, prefix=settings.API_V1_PREFIX)
app.include_router(documents_router, prefix=settings.API_V1_PREFIX)
app.include_router(admin_router, prefix=settings.API_V1_PREFIX)
app.include_router(export_router, prefix=settings.API_V1_PREFIX)


# ---------------------------------------------------------------------------
# Health checks (T3.9)
# ---------------------------------------------------------------------------
# /health   — liveness: process is up. NEVER hits dependencies. Cheap.
# /health/ready — readiness: every backing store is reachable. Used by
#               orchestrators (k8s, docker compose, etc.) to gate traffic.

@app.get("/health")
async def health_check() -> dict[str, str]:
    return {
        "status": "healthy",
        "service": settings.PROJECT_NAME,
        "version": settings.VERSION,
    }


@app.get("/health/ready")
async def readiness_check() -> dict[str, object]:
    components: dict[str, str] = {}
    overall_ok = True

    # Postgres — `SELECT 1` round-trip
    try:
        async with async_session() as db:
            await db.execute(text("SELECT 1"))
        components["postgres"] = "ok"
    except Exception as exc:  # noqa: BLE001
        log.warning("readiness: postgres failed", extra={"err": repr(exc)})
        components["postgres"] = "fail"
        overall_ok = False

    # Redis — PING
    try:
        pong = await redis_client.ping()
        components["redis"] = "ok" if pong else "fail"
        if not pong:
            overall_ok = False
    except Exception as exc:  # noqa: BLE001
        log.warning("readiness: redis failed", extra={"err": repr(exc)})
        components["redis"] = "fail"
        overall_ok = False

    # Storage (MinIO/S3) — best-effort; the helper exposes a healthcheck if
    # it has one, otherwise we just call list_buckets via the underlying
    # boto3 client. Wrapped in try so a startup race doesn't fail readiness.
    try:
        client = getattr(storage_client, "_client", None)
        if client is not None:
            client.list_buckets()
            components["storage"] = "ok"
        else:
            components["storage"] = "skipped"
    except Exception as exc:  # noqa: BLE001
        log.warning("readiness: storage failed", extra={"err": repr(exc)})
        components["storage"] = "fail"
        overall_ok = False

    return {
        "status": "ready" if overall_ok else "degraded",
        "components": components,
        "version": settings.VERSION,
    }
