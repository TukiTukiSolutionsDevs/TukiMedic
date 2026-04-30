"""
Process-wide rate limiter for HTTP endpoints.

Uses slowapi (a Starlette/FastAPI port of flask-limiter). The limiter is
keyed on the client IP (`get_remote_address`) and stored in-process — fine
for single-instance deployments. For multi-replica deployments, swap to
`storage_uri="redis://..."` via env config.

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

# Single shared limiter instance. Tests reset it via `limiter.reset()`.
limiter: Limiter = Limiter(key_func=get_remote_address)
