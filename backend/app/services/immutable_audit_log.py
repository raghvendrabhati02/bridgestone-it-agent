"""
immutable_audit_log.py
──────────────────────────────────────────────────────────────────────────────
Append-only immutable audit log for enterprise compliance.

Design contracts
----------------
  ✓  Append-only: the only write operation exposed is ``record()``.
  ✓  No update() or delete() methods exist on this class — immutability is
     enforced at the API level, not just at runtime.
  ✓  Thread-safe: a module-level lock protects the in-process write path.
  ✓  Every record emits a structured JSON log line that includes:
       - correlation_id   (propagated from logging context)
       - timestamp        (UTC ISO-8601)
       - actor            (username or service name)
       - event_type       (caller-defined)
       - payload_hash     (SHA-256 of the JSON payload for integrity verification)
  ✓  Persists to the database via audit_service.log_audit() when a db session
     or the audit_service is available; degrades gracefully to JSON-log-only.
  ✓  Never raises — any persistence failure is caught and logged.

Usage
-----
    log = ImmutableAuditLog.get_instance()
    log.record(
        event_type="TICKET_CREATED",
        actor="john.doe",
        session_id="sess-abc123",
        payload={
            "ticket_id": "INC0071633",
            "category": "network",
            "subcategory": "VPN-Global Protect",
        },
    )
"""

from __future__ import annotations

import hashlib
import json
import logging
import threading
from datetime import datetime, timezone
from typing import Any, Dict, Optional

logger = logging.getLogger("it-agent-backend")

# ── Module-level singleton guard ──────────────────────────────────────────────
_instance: Optional["ImmutableAuditLog"] = None
_singleton_lock: threading.Lock = threading.Lock()


class ImmutableAuditLog:
    """
    Append-only audit log.

    Only ``record()`` is exposed. There are no ``update()`` or ``delete()``
    methods — immutability is guaranteed at the API design level.
    """

    # ── Thread-safety ─────────────────────────────────────────────────────────
    _write_lock: threading.Lock = threading.Lock()

    # ── Singleton factory ─────────────────────────────────────────────────────

    @classmethod
    def get_instance(cls) -> "ImmutableAuditLog":
        """Return (or create) the process-wide singleton."""
        global _instance
        if _instance is None:
            with _singleton_lock:
                if _instance is None:
                    _instance = cls()
        return _instance

    @classmethod
    def reset_instance(cls) -> None:
        """Reset singleton — **test-only**."""
        global _instance
        with _singleton_lock:
            _instance = None

    # ── Core append operation ─────────────────────────────────────────────────

    def record(
        self,
        event_type: str,
        actor: str,
        payload: Dict[str, Any],
        session_id: Optional[str] = None,
        correlation_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Append an immutable audit record.

        Parameters
        ----------
        event_type:     Caller-defined event label (e.g. ``"TICKET_CREATED"``).
        actor:          Username or service name responsible for the event.
        payload:        Arbitrary dict describing the event (will be JSON-serialised).
        session_id:     Optional conversation / session ID for cross-reference.
        correlation_id: Optional correlation ID; auto-resolved from context if omitted.

        Returns
        -------
        dict
            The complete audit record as stored (timestamp, hash, …).
        """
        # Resolve correlation_id from context if not explicitly provided
        if not correlation_id:
            try:
                from app.core.logging_context import correlation_id_ctx
                correlation_id = correlation_id_ctx.get() or ""
            except Exception:
                correlation_id = ""

        ts = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        payload_json = json.dumps(payload, sort_keys=True, default=str)
        payload_hash = hashlib.sha256(payload_json.encode()).hexdigest()

        record: Dict[str, Any] = {
            "timestamp":      ts,
            "event_type":     event_type,
            "actor":          actor,
            "session_id":     session_id or "",
            "correlation_id": correlation_id,
            "payload":        payload,
            "payload_hash":   payload_hash,
        }

        # Emit structured JSON log (always — even if DB persistence fails)
        logger.info(
            "[ImmutableAuditLog] event_type=%s actor=%s correlation_id=%s "
            "session_id=%s payload_hash=%s",
            event_type, actor, correlation_id, session_id or "", payload_hash,
            extra={
                "audit_event_type":     event_type,
                "audit_actor":          actor,
                "audit_session_id":     session_id or "",
                "audit_correlation_id": correlation_id,
                "audit_payload_hash":   payload_hash,
                "audit_timestamp":      ts,
            },
        )

        # Best-effort DB persistence via audit_service — never raises
        try:
            with self._write_lock:
                self._persist(record, session_id, event_type, actor, payload)
        except Exception as exc:
            logger.warning(
                "[ImmutableAuditLog] _persist raised unexpectedly for event_type=%s: %s",
                event_type, exc,
            )

        return record

    # ── Persistence (best-effort) ─────────────────────────────────────────────

    def _persist(
        self,
        record: Dict[str, Any],
        session_id: Optional[str],
        event_type: str,
        actor: str,
        payload: Dict[str, Any],
    ) -> None:
        """Write to the database via audit_service. Silently degrades on failure."""
        try:
            from app.services.audit_service import log_audit
            log_audit(
                session_id=session_id or "",
                user_message=event_type,
                category=payload.get("category", ""),
                decision=event_type,
                approval_status="N/A",
                recommended_action="",
                action_result=payload,
                ticket_id=str(payload.get("ticket_id", "")),
                servicenow_id=str(payload.get("servicenow_id", "")),
            )
        except Exception as exc:
            logger.warning(
                "[ImmutableAuditLog] DB persistence failed for event_type=%s: %s — "
                "structured JSON log was still emitted.",
                event_type, exc,
            )


# ── Module-level convenience function ────────────────────────────────────────

def record_audit_event(
    event_type: str,
    actor: str,
    payload: Dict[str, Any],
    session_id: Optional[str] = None,
    correlation_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Module-level convenience wrapper around ImmutableAuditLog.record()."""
    return ImmutableAuditLog.get_instance().record(
        event_type=event_type,
        actor=actor,
        payload=payload,
        session_id=session_id,
        correlation_id=correlation_id,
    )
