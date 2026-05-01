"""SecurityHeadersMiddleware — defensive HTTP response headers.

Adds the standard set of security headers required for clinical-data
applications (HIPAA-equivalents, Habeas Data argentino) on every response,
including error responses. Wired before SlowAPI / CORS in main.py so it
covers rate-limit denials and 4xx/5xx exceptions too.

Headers covered:
  - Strict-Transport-Security
  - Content-Security-Policy
  - X-Content-Type-Options
  - X-Frame-Options
  - Referrer-Policy
  - Permissions-Policy
  - Cross-Origin-Opener-Policy

The CSP is intentionally tight (no inline scripts, no eval). The frontend
is a separate origin and uses `nonce`/`hash`-based CSP at its layer.
This middleware governs only the API surface.
"""

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


# 1 year — chrome/firefox preload list minimum.
_HSTS_MAX_AGE = 31_536_000

# CSP for the JSON/WebSocket API. The API itself never serves HTML to a
# browser context; default-src 'none' is the safest baseline. We only need
# 'self' for the docs (Swagger/OpenAPI) which load static assets.
_CSP = (
    "default-src 'none'; "
    "script-src 'self'; "
    "style-src 'self'; "
    "img-src 'self' data:; "
    "font-src 'self'; "
    "connect-src 'self'; "
    "frame-ancestors 'none'; "
    "base-uri 'none'; "
    "form-action 'self'"
)

_PERMISSIONS_POLICY = (
    "geolocation=(), microphone=(), camera=(), "
    "fullscreen=(), payment=(), usb=()"
)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Attach defensive security headers to every HTTP response."""

    async def dispatch(self, request: Request, call_next) -> Response:
        response: Response = await call_next(request)
        headers = response.headers
        # Use setdefault so a downstream handler can override on purpose
        # (e.g. an embedded doc page setting a relaxed CSP).
        headers.setdefault(
            "Strict-Transport-Security",
            f"max-age={_HSTS_MAX_AGE}; includeSubDomains; preload",
        )
        headers.setdefault("Content-Security-Policy", _CSP)
        headers.setdefault("X-Content-Type-Options", "nosniff")
        headers.setdefault("X-Frame-Options", "DENY")
        headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        headers.setdefault("Permissions-Policy", _PERMISSIONS_POLICY)
        headers.setdefault("Cross-Origin-Opener-Policy", "same-origin")
        return response
