"""
Process-wide rate limiter for HTTP endpoints.

Uses slowapi (a Starlette/FastAPI port of flask-limiter). The limiter is
keyed on the client IP (`get_remote_address`) and backed by Redis so that
counters are shared across all replicas (multi-worker safe).

Usage
-----
1. Decorate the endpoint::

    from app.core.rate_limit import limiter

    @router.post("/login")
    @limiter.limit("5/minute")
    async def login(request: Request, ...):  # `request: Request` is REQUIRED
        ...

2. Register middleware + handler in `app.main` (already done).
"""
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.config import settings

# Shared limiter backed by Redis — counters survive across workers and replicas.
# Tests swap _storage and _limiter.storage to MemoryStorage via conftest so no
# live Redis connection is required during the test suite.
limiter: Limiter = Limiter(key_func=get_remote_address, storage_uri=settings.REDIS_URL)
