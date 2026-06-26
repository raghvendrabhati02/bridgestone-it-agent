"""
RBAC Audit Service
==================
Records enterprise-grade audit events for:
    • ticket creation
    • lifecycle transitions  (state changes)
    • approval decisions     (approved / rejected)
    • access denials         (ACCESS_DENIED)
    • ticket closure

All functions are non-fatal — exceptions are caught and logged so they
never disrupt the agent graph.

Usage
-----
    from app.services.rbac_audit_service import log_rbac_event, get_rbac_audit_logs

    log_rbac_event(
        user="alice",
        role="EMPLOYEE",
        action="create_ticket",
        ticket_id="INC000042",
        details={"category": "VPN"},
    )
"""

import json
import logging
import datetime
from typing import Optional, List, Dict, Any

logger = logging.getLogger("it-agent-backend")


# ── Public API ────────────────────────────────────────────────────────────────

def log_rbac_event(
    user: str,
    role: str,
    action: str,
    ticket_id: Optional[str] = None,
    old_state: Optional[str] = None,
    new_state: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Persists a single RBAC audit event to the `rbac_audit_logs` table.
    Returns a dict representation of the saved row.
    Falls back to an in-memory dict if the DB is unavailable.
    """
    try:
        from app.database.session import get_db
        from app.database.repositories.rbac_audit_repository import RbacAuditRepository

        with get_db() as db:
            repo = RbacAuditRepository(db)
            record = repo.save(
                user=user or "unknown",
                role=role or "UNKNOWN",
                action=action,
                ticket_id=ticket_id,
                old_state=old_state,
                new_state=new_state,
                details=details,
            )
            logger.info(
                "RBAC Audit: Logged event audit_id=%s user='%s' role='%s' action='%s' ticket='%s'",
                record.audit_id, user, role, action, ticket_id,
            )
            return _serialize(record)

    except Exception as e:
        logger.error(
            "RBAC Audit: Failed to persist event to DB (user='%s' action='%s'): %s",
            user, action, e,
        )
        # Volatile fallback — still useful for tests that don't run a DB
        return {
            "audit_id": None,
            "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
            "user": user,
            "role": role,
            "action": action,
            "ticket_id": ticket_id,
            "old_state": old_state,
            "new_state": new_state,
            "details": details,
        }


def get_rbac_audit_logs(ticket_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Returns all RBAC audit logs, optionally filtered by ticket_id.
    Returns [] on error.
    """
    try:
        from app.database.session import get_db
        from app.database.repositories.rbac_audit_repository import RbacAuditRepository

        with get_db() as db:
            repo = RbacAuditRepository(db)
            if ticket_id:
                rows = repo.get_by_ticket(ticket_id)
            else:
                rows = repo.get_all()
            return [_serialize(r) for r in rows]

    except Exception as e:
        logger.error("RBAC Audit: Failed to retrieve audit logs: %s", e)
        return []


# ── Serialiser ────────────────────────────────────────────────────────────────

def _serialize(record) -> Dict[str, Any]:
    details = record.details
    if details:
        try:
            details = json.loads(details)
        except Exception:
            pass  # leave as raw string if not valid JSON
    return {
        "audit_id":  record.audit_id,
        "timestamp": record.timestamp.isoformat() + "Z" if record.timestamp else None,
        "user":      record.user,
        "role":      record.role,
        "action":    record.action,
        "ticket_id": record.ticket_id,
        "old_state": record.old_state,
        "new_state": record.new_state,
        "details":   details,
    }
