"""
Approval Service
================
Handles detection of privileged actions, creation and storage of approval
entries, status updates, and audit logging. All functions use defensive
fallbacks — if the database is unavailable, an in-memory dict is used so
the graph never crashes.
"""
import datetime
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger("it-agent-backend")

# ── Privileged action keyword list ────────────────────────────────────────────
# Any recommended_action that contains one of these keywords (case-insensitive)
# will be treated as privileged and routed through the approval gate.
PRIVILEGED_KEYWORDS = [
    "restart",
    "reset_password",
    "password_reset",
    "change_configuration",
    "delete",
    "disable_account",
    "enable_account",
    "unlock_account",
    "force_logout",
    "revoke_access",
    "grant_access",
    "escalate",
    "modify_permissions",
    "clear_cache",
    "reboot",
]

# Volatile in-memory fallback (session_id -> approval dict)
_approval_store: Dict[str, Dict[str, Any]] = {}


def detect_privileged(state: Dict[str, Any]) -> bool:
    """
    Returns True if the recommended_action in state matches any privileged keyword.
    Also checks if `approval_required` was explicitly set True by an upstream node.
    """
    # Explicit upstream flag takes priority
    if state.get("approval_required"):
        return True

    recommended = (state.get("recommended_action") or "").lower()
    decision = (state.get("decision") or "").upper()

    # EXECUTE_ACTION decisions with a privileged keyword in recommended_action
    if decision == "EXECUTE_ACTION" and any(kw in recommended for kw in PRIVILEGED_KEYWORDS):
        return True

    return False


def create_approval_entry(session_id: str, action: str) -> Dict[str, Any]:
    """
    Persists a PENDING approval entry for the given session and action.
    Returns the stored record.
    """
    entry = {
        "session_id": session_id,
        "recommended_action": action,
        "approval_status": "PENDING",
        "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
    }
    _approval_store[session_id] = entry

    # Try to persist to DB via existing log_approval
    try:
        from app.services.audit_service import log_approval
        log_approval(
            session_id=session_id,
            recommended_action=action,
            approval_status="PENDING",
        )
    except Exception as e:
        logger.warning("Approval Service: DB persist failed, using in-memory: %s", e)

    logger.info(
        "Approval Service: Created PENDING entry for session=%s action=%s",
        session_id, action,
    )
    return entry


def update_approval(session_id: str, status: str) -> Dict[str, Any]:
    """
    Updates approval status (APPROVED / REJECTED) for a session.
    Returns the updated record.
    """
    status = status.upper().strip()
    existing = _approval_store.get(session_id, {})
    action = existing.get("recommended_action", "")
    entry = {
        "session_id": session_id,
        "recommended_action": action,
        "approval_status": status,
        "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
    }
    _approval_store[session_id] = entry

    try:
        from app.services.audit_service import log_approval
        log_approval(
            session_id=session_id,
            recommended_action=action,
            approval_status=status,
        )
    except Exception as e:
        logger.warning("Approval Service: DB update failed, using in-memory: %s", e)

    logger.info(
        "Approval Service: Updated approval status=%s for session=%s",
        status, session_id,
    )
    return entry


def audit_approval(session_id: str, action: str, status: str) -> None:
    """
    Writes a dedicated approval audit trace via audit_service.log_agent_trace.
    Non-fatal: exceptions are caught and logged.
    """
    try:
        from app.services.audit_service import log_agent_trace
        log_agent_trace(
            session_id=session_id,
            agent_name="Approval Agent",
            output={
                "recommended_action": action,
                "approval_status": status,
                "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
            },
        )
    except Exception as e:
        logger.error("Approval Service: Failed to write audit trace: %s", e)


def get_approval(session_id: str) -> Optional[Dict[str, Any]]:
    """Returns the latest approval record for a session (in-memory)."""
    return _approval_store.get(session_id)
