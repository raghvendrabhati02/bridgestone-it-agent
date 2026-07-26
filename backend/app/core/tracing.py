"""
app/core/tracing.py
────────────────────────────────────────────────────────────────────────────
Lightweight, OpenTelemetry-compatible pipeline span tracing.

Design principles
-----------------
* The public API (trace_span) intentionally mirrors the OpenTelemetry Span
  interface so that adopting the full OTel SDK later is a drop-in replacement.
* Does NOT change any business logic — purely observability instrumentation.
* Works in both synchronous and asynchronous code paths.
* Structured span log output is consumed by the existing JSON logger.

Usage (sync)
------------
    from app.core.tracing import trace_span

    with trace_span(
        name="classification",
        attributes={"provider": "gemini", "model": "gemini-2.5-flash", "correlation_id": corr_id},
    ):
        result = classifier.classify(issue)

Usage (async)
-------------
    async with trace_span(
        name="servicenow_api",
        attributes={"operation": "create_incident", "correlation_id": corr_id},
    ):
        response = await client.post(...)
"""

from __future__ import annotations

import logging
import time
from contextlib import contextmanager, asynccontextmanager
from typing import Any, Dict, Optional

from app.core.logging_context import correlation_id_ctx, session_id_ctx

logger = logging.getLogger("it-agent-backend")

# ---------------------------------------------------------------------------
# Sentinel value used when provider / status are not applicable
# ---------------------------------------------------------------------------
_UNKNOWN = "unknown"


def _record_span(
    name: str,
    attributes: Dict[str, Any],
    duration_s: float,
    status: str,
) -> None:
    """
    Emit a structured log entry and record a Prometheus observation.

    Separated from the context managers so it is testable in isolation.
    """
    provider = attributes.get("provider", _UNKNOWN)
    corr_id = attributes.get("correlation_id") or correlation_id_ctx.get() or ""
    sess_id = session_id_ctx.get() or ""

    # ── Structured log ──────────────────────────────────────────────────────
    logger.info(
        "Pipeline span completed.",
        extra={
            "event": "pipeline_span",
            "service": name,
            "provider": provider,
            "status": status,
            "duration_ms": round(duration_s * 1000, 2),
            "correlation_id": corr_id,
            "session_id": sess_id,
            **{k: v for k, v in attributes.items() if k not in ("correlation_id",)},
        },
    )

    # ── Prometheus histogram ─────────────────────────────────────────────────
    try:
        from app.core.metrics import PIPELINE_SPAN_DURATION_SECONDS

        PIPELINE_SPAN_DURATION_SECONDS.labels(
            service=name,
            provider=provider,
            status=status,
        ).observe(duration_s)
    except Exception:
        # Never let observability instrumentation break the application
        pass


# ---------------------------------------------------------------------------
# Synchronous context manager
# ---------------------------------------------------------------------------
@contextmanager
def trace_span(
    name: str,
    attributes: Optional[Dict[str, Any]] = None,
):
    """
    Synchronous pipeline span context manager.

    Parameters
    ----------
    name        : Human-readable service/component label (e.g. "classification").
    attributes  : Optional key-value pairs attached to the span, e.g.
                  ``{"provider": "gemini", "model": "gemini-2.5-flash"}``.

    The following attribute keys have special meaning:
    - ``correlation_id``: overrides the value from logging context.
    - ``provider``      : recorded as a metric label.
    - ``status``        : set automatically to "success" or "error".
    """
    attrs: Dict[str, Any] = attributes or {}
    start = time.perf_counter()
    status = "success"
    try:
        yield
    except Exception:
        status = "error"
        raise
    finally:
        duration = time.perf_counter() - start
        _record_span(name, attrs, duration, status)


# ---------------------------------------------------------------------------
# Asynchronous context manager
# ---------------------------------------------------------------------------
@asynccontextmanager
async def async_trace_span(
    name: str,
    attributes: Optional[Dict[str, Any]] = None,
):
    """
    Asynchronous pipeline span context manager.

    Use this inside ``async def`` functions where ``trace_span`` cannot be used
    because the body contains ``await`` expressions.
    """
    attrs: Dict[str, Any] = attributes or {}
    start = time.perf_counter()
    status = "success"
    try:
        yield
    except Exception:
        status = "error"
        raise
    finally:
        duration = time.perf_counter() - start
        _record_span(name, attrs, duration, status)
