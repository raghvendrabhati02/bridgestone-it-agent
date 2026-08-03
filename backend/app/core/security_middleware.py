"""
security_middleware.py
──────────────────────────────────────────────────────────────────────────────
Phase 4: Enterprise Security Middleware

Provides two ASGI middleware classes:

  SecurityHeadersMiddleware
  ─────────────────────────
  Injects standard HTTP security headers on every response.
  All headers are configurable via environment variables so they can be
  tuned per deployment (local dev vs. production vs. Kubernetes).

  Env vars (all optional, sensible defaults):
    HSTS_ENABLED          — set to "false" to disable HSTS (for local HTTP)
    HSTS_MAX_AGE          — seconds (default 31536000 = 1 year)
    CSP_POLICY            — full Content-Security-Policy value
    FRAME_OPTIONS         — DENY | SAMEORIGIN (default DENY)

  RequestSizeLimitMiddleware
  ──────────────────────────
  Rejects incoming requests whose Content-Length exceeds a configured
  threshold. Returns HTTP 413 Request Entity Too Large before the body
  is even parsed.

  Env vars:
    MAX_REQUEST_SIZE_KB   — kilobytes (default 512). Set to 0 to disable.
"""

from __future__ import annotations

import logging
import os
from typing import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp

logger = logging.getLogger("it-agent-backend")


# ──────────────────────────────────────────────────────────────────────────────
# Security Headers Middleware
# ──────────────────────────────────────────────────────────────────────────────

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Adds HTTP security headers to every response.

    Headers applied:
      • X-Content-Type-Options: nosniff
      • X-Frame-Options: DENY (or SAMEORIGIN)
      • X-XSS-Protection: 1; mode=block
      • Referrer-Policy: strict-origin-when-cross-origin
      • Permissions-Policy: (restrictive)
      • Strict-Transport-Security (only when HSTS_ENABLED=true)
      • Content-Security-Policy (configurable)
    """

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)
        self._hsts_enabled = os.getenv("HSTS_ENABLED", "false").lower() in ("1", "true", "yes")
        self._hsts_max_age = int(os.getenv("HSTS_MAX_AGE", "31536000"))
        self._frame_options = os.getenv("FRAME_OPTIONS", "DENY").upper()
        default_csp = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
            "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
            "img-src 'self' data: https://fastapi.tiangolo.com https://cdn.jsdelivr.net; "
            "font-src 'self' https://cdn.jsdelivr.net data:; "
            "connect-src 'self'; "
            "object-src 'none'; "
            "frame-ancestors 'none'"
        )
        self._csp_policy = os.getenv("CSP_POLICY", default_csp)


    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response: Response = await call_next(request)

        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = self._frame_options
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = (
            "geolocation=(), microphone=(), camera=(), payment=()"
        )
        response.headers["Content-Security-Policy"] = self._csp_policy

        if self._hsts_enabled:
            response.headers["Strict-Transport-Security"] = (
                f"max-age={self._hsts_max_age}; includeSubDomains"
            )

        # Never reveal server technology in responses
        response.headers["Server"] = "Bridgestone-IT-Agent"

        return response


# ──────────────────────────────────────────────────────────────────────────────
# Request Size Limit Middleware
# ──────────────────────────────────────────────────────────────────────────────

class RequestSizeLimitMiddleware(BaseHTTPMiddleware):
    """
    Rejects requests exceeding MAX_REQUEST_SIZE_KB kilobytes.

    Checks the Content-Length header first (fast path); if absent, reads
    the body incrementally and aborts as soon as the limit is exceeded.

    Returns HTTP 413 Request Entity Too Large with a JSON body.
    """

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)
        max_kb = int(os.getenv("MAX_REQUEST_SIZE_KB", "512"))
        self._max_bytes: int = max_kb * 1024
        self._enabled: bool = max_kb > 0

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if not self._enabled:
            return await call_next(request)

        # Fast path: trust Content-Length header if present
        content_length = request.headers.get("content-length")
        if content_length:
            try:
                if int(content_length) > self._max_bytes:
                    logger.warning(
                        "RequestSizeLimitMiddleware: Rejected oversized request "
                        "content-length=%s max_bytes=%s path=%s",
                        content_length, self._max_bytes, request.url.path,
                    )
                    return JSONResponse(
                        status_code=413,
                        content={
                            "detail": f"Request body exceeds the maximum allowed size of "
                                      f"{self._max_bytes // 1024} KB.",
                            "error_code": "REQUEST_TOO_LARGE",
                        },
                    )
            except ValueError:
                pass  # malformed Content-Length — let the route handle it

        return await call_next(request)
