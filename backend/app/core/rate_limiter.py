"""
rate_limiter.py
──────────────────────────────────────────────────────────────────────────────
Phase 4: Enterprise Rate Limiting

Pure-Python, in-process sliding-window rate limiter. No external dependencies
(no Redis, no slowapi). Suitable for single-process deployments.

For multi-process / Kubernetes deployments, replace _SlidingWindowStore with
a Redis-backed implementation — the interface is the same.

Usage
─────
    from app.core.rate_limiter import rate_limit_middleware, check_rate_limit

    # As a FastAPI dependency (inline):
    @app.post("/chat")
    def chat(request: Request, ...):
        check_rate_limit(request, limit_key="chat")

    # As an ASGI middleware (applied globally):
    app.add_middleware(RateLimitMiddleware, rules=[...])

Configuration (env vars)
────────────────────────
    RATE_LIMIT_CHAT        — max requests per window (default 30)
    RATE_LIMIT_CHAT_WINDOW — window in seconds (default 60)
    RATE_LIMIT_LOGIN       — max requests per window (default 10)
    RATE_LIMIT_LOGIN_WINDOW— window in seconds (default 60)
    RATE_LIMIT_UPLOAD      — max requests per window (default 5)
    RATE_LIMIT_UPLOAD_WINDOW — window in seconds (default 60)
    RATE_LIMIT_ENABLED     — set to "false" to disable all rate limiting (tests)
"""

from __future__ import annotations

import logging
import os
import threading
import time
from collections import defaultdict, deque
from typing import Dict, Optional

from fastapi import HTTPException, Request

logger = logging.getLogger("it-agent-backend")

_ENABLED: bool = os.getenv("RATE_LIMIT_ENABLED", "true").lower() not in ("0", "false", "no")

# ──────────────────────────────────────────────────────────────────────────────
# Sliding Window Store
# ──────────────────────────────────────────────────────────────────────────────

class _SlidingWindowStore:
    """
    Thread-safe in-memory sliding window counter.
    Each key maps to a deque of timestamps of past requests.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        # key → deque of float (unix timestamps)
        self._windows: Dict[str, deque] = defaultdict(deque)

    def is_allowed(self, key: str, max_calls: int, window_seconds: int) -> tuple[bool, int]:
        """
        Check whether the key is within rate limit.

        Returns (allowed: bool, remaining: int).
        """
        if not _ENABLED:
            return True, max_calls

        now = time.monotonic()
        cutoff = now - window_seconds

        with self._lock:
            dq = self._windows[key]
            # Evict timestamps outside the window
            while dq and dq[0] < cutoff:
                dq.popleft()

            count = len(dq)
            if count >= max_calls:
                return False, 0

            dq.append(now)
            return True, max_calls - count - 1

    def reset(self, key: str) -> None:
        """Clear all timestamps for a key (for testing)."""
        with self._lock:
            self._windows.pop(key, None)

    def clear_all(self) -> None:
        """Clear all state (for testing)."""
        with self._lock:
            self._windows.clear()


# Process-wide singleton store
_store = _SlidingWindowStore()


# ──────────────────────────────────────────────────────────────────────────────
# Limit configuration
# ──────────────────────────────────────────────────────────────────────────────

def _int_env(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


LIMITS = {
    "chat": {
        "max_calls": _int_env("RATE_LIMIT_CHAT", 30),
        "window_seconds": _int_env("RATE_LIMIT_CHAT_WINDOW", 60),
    },
    "login": {
        "max_calls": _int_env("RATE_LIMIT_LOGIN", 10),
        "window_seconds": _int_env("RATE_LIMIT_LOGIN_WINDOW", 60),
    },
    "upload": {
        "max_calls": _int_env("RATE_LIMIT_UPLOAD", 5),
        "window_seconds": _int_env("RATE_LIMIT_UPLOAD_WINDOW", 60),
    },
}


# ──────────────────────────────────────────────────────────────────────────────
# Key extraction
# ──────────────────────────────────────────────────────────────────────────────

def _get_client_key(request: Request, limit_key: str) -> str:
    """
    Build a rate-limit bucket key from:
      1. Authenticated username (preferred — user-level limiting)
      2. X-Forwarded-For or client host (IP-level fallback)
    """
    # Try to extract username from JWT without full DB round-trip
    auth_header = request.headers.get("authorization", "")
    username: Optional[str] = None
    if auth_header.startswith("Bearer "):
        try:
            from app.core.security import decode_token
            payload = decode_token(auth_header.split(" ", 1)[1])
            username = payload.get("sub")
        except Exception:
            pass

    if username:
        return f"rl:{limit_key}:user:{username}"

    # IP-based fallback
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        ip = forwarded_for.split(",")[0].strip()
    else:
        ip = getattr(request.client, "host", "unknown")
    return f"rl:{limit_key}:ip:{ip}"


# ──────────────────────────────────────────────────────────────────────────────
# Public API — FastAPI dependency
# ──────────────────────────────────────────────────────────────────────────────

def check_rate_limit(request: Request, limit_key: str) -> None:
    """
    Raise HTTP 429 if the caller has exceeded the rate limit for `limit_key`.

    Usage in a route:
        @app.post("/chat")
        def chat(request: Request, ...):
            check_rate_limit(request, "chat")
    """
    if not _ENABLED:
        return

    cfg = LIMITS.get(limit_key)
    if not cfg:
        logger.warning("rate_limiter: unknown limit_key '%s' — skipping", limit_key)
        return

    key = _get_client_key(request, limit_key)
    allowed, remaining = _store.is_allowed(key, cfg["max_calls"], cfg["window_seconds"])

    if not allowed:
        logger.warning(
            "rate_limiter: LIMIT EXCEEDED key=%s limit_key=%s max_calls=%s window=%ss",
            key, limit_key, cfg["max_calls"], cfg["window_seconds"],
        )
        raise HTTPException(
            status_code=429,
            detail={
                "error": "Rate limit exceeded. Please slow down and try again.",
                "error_code": "RATE_LIMIT_EXCEEDED",
                "retry_after_seconds": cfg["window_seconds"],
            },
            headers={"Retry-After": str(cfg["window_seconds"])},
        )


# ──────────────────────────────────────────────────────────────────────────────
# Test helpers
# ──────────────────────────────────────────────────────────────────────────────

def reset_rate_limit_store() -> None:
    """Clear all rate limit state. Call from tests only."""
    _store.clear_all()


def get_store() -> _SlidingWindowStore:
    """Return the internal store for inspection in tests."""
    return _store
