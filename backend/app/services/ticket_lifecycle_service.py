"""
Ticket Lifecycle Service
========================
Manages the full state machine for tickets:

    OPEN → ASSIGNED → IN_PROGRESS → WAITING_FOR_USER → RESOLVED → CLOSED

Each transition is recorded in a history log and triggers a notification via
notification_service. The service uses an in-memory store as primary storage
(the DB ticket.status column is updated when available).

Valid state transitions
-----------------------
OPEN            → ASSIGNED
ASSIGNED        → IN_PROGRESS
IN_PROGRESS     → WAITING_FOR_USER | RESOLVED
WAITING_FOR_USER→ IN_PROGRESS | RESOLVED
RESOLVED        → CLOSED

Attempting an invalid transition is a no-op (the current state is returned
unchanged and a warning is logged).
"""

import datetime
import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger("it-agent-backend")

# ── Valid state machine ───────────────────────────────────────────────────────
VALID_TRANSITIONS: Dict[str, List[str]] = {
    "OPEN":              ["ASSIGNED"],
    "ASSIGNED":          ["IN_PROGRESS"],
    "IN_PROGRESS":       ["WAITING_FOR_USER", "RESOLVED"],
    "WAITING_FOR_USER":  ["IN_PROGRESS", "RESOLVED"],
    "RESOLVED":          ["CLOSED"],
    "CLOSED":            [],
}

ALL_STATES = list(VALID_TRANSITIONS.keys())

# Notification message templates per transition
TRANSITION_MESSAGES: Dict[str, str] = {
    "OPEN":             "Ticket {ticket_id} has been opened and is awaiting assignment.",
    "ASSIGNED":         "Ticket {ticket_id} has been assigned to the support team and is queued for review.",
    "IN_PROGRESS":      "Ticket {ticket_id} is now being actively worked on by the assigned team.",
    "WAITING_FOR_USER": "Ticket {ticket_id} is waiting for your response. Please reply to continue.",
    "RESOLVED":         "Ticket {ticket_id} has been resolved. Please confirm if the issue is fixed.",
    "CLOSED":           "Ticket {ticket_id} is now closed. Thank you for using IT Support.",
}

# In-memory lifecycle store: ticket_id → lifecycle dict
_lifecycle_store: Dict[str, Dict[str, Any]] = {}


# ── Public API ────────────────────────────────────────────────────────────────

def init_lifecycle(ticket_id: str, initial_state: str = "OPEN") -> Dict[str, Any]:
    """
    Initialise the lifecycle record for a newly created ticket.
    Returns the lifecycle dict. Idempotent — calling twice is safe.
    """
    if ticket_id in _lifecycle_store:
        logger.info(
            "Lifecycle Service: Lifecycle already exists for ticket=%s, state=%s",
            ticket_id, _lifecycle_store[ticket_id]["state"],
        )
        return _lifecycle_store[ticket_id]

    now = _now()
    lifecycle = {
        "ticket_id":  ticket_id,
        "state":      initial_state,
        "history":    [{"state": initial_state, "timestamp": now, "note": "Ticket created"}],
        "created_at": now,
        "updated_at": now,
    }
    _lifecycle_store[ticket_id] = lifecycle
    logger.info(
        "Lifecycle Service: Initialized lifecycle for ticket=%s state=%s",
        ticket_id, initial_state,
    )
    # Send opening notification
    _notify(ticket_id, initial_state)
    return lifecycle


def transition(
    ticket_id: str,
    new_state: str,
    note: str = "",
    session_id: str = "",
) -> Dict[str, Any]:
    """
    Transitions a ticket to new_state if the move is valid.
    Emits a notification and audits the transition.
    Returns the updated lifecycle dict.
    """
    new_state = new_state.upper().strip()

    if ticket_id not in _lifecycle_store:
        # Auto-initialise so we can transition immediately
        init_lifecycle(ticket_id)

    lifecycle = _lifecycle_store[ticket_id]
    current = lifecycle["state"]

    if new_state not in VALID_TRANSITIONS.get(current, []):
        logger.warning(
            "Lifecycle Service: Invalid transition %s → %s for ticket=%s. Ignoring.",
            current, new_state, ticket_id,
        )
        return lifecycle

    now = _now()
    history_entry = {
        "from_state":  current,
        "to_state":    new_state,
        "timestamp":   now,
        "note":        note or f"Transitioned from {current} to {new_state}",
    }
    lifecycle["history"].append(history_entry)
    lifecycle["state"]      = new_state
    lifecycle["updated_at"] = now

    logger.info(
        "Lifecycle Service: Ticket %s transitioned %s → %s",
        ticket_id, current, new_state,
    )

    # ── Update DB ticket status if possible ──────────────────────────────────
    _update_db_status(ticket_id, new_state)

    # ── Emit notification ────────────────────────────────────────────────────
    _notify(ticket_id, new_state)

    # ── Audit ────────────────────────────────────────────────────────────────
    _audit_transition(session_id, ticket_id, current, new_state, note)

    return lifecycle


def get_lifecycle(ticket_id: str) -> Optional[Dict[str, Any]]:
    """Returns the lifecycle record for a ticket or None if not found."""
    return _lifecycle_store.get(ticket_id)


def get_state(ticket_id: str) -> Optional[str]:
    """Returns the current lifecycle state string for a ticket."""
    lc = _lifecycle_store.get(ticket_id)
    return lc["state"] if lc else None


def record_event(ticket_id: str, message: str, session_id: str = "") -> None:
    """
    Appends an informational event to the ticket history without changing
    the lifecycle state. Also fires a notification.
    """
    if ticket_id not in _lifecycle_store:
        init_lifecycle(ticket_id)

    lifecycle = _lifecycle_store[ticket_id]
    lifecycle["history"].append({
        "state":     lifecycle["state"],
        "timestamp": _now(),
        "note":      message,
    })
    _notify(ticket_id, lifecycle["state"], message=message)
    logger.info("Lifecycle Service: Event recorded for ticket=%s: %s", ticket_id, message)


def auto_transition_from_intent(
    ticket_id: str,
    user_message: str,
    session_id: str = "",
) -> Optional[str]:
    """
    Maps common user intents to lifecycle transitions.
    Returns the new state name if a transition occurred, else None.

    Keyword → transition triggered:
        assign / assigned            → ASSIGNED
        start / working / in_prog    → IN_PROGRESS
        wait / waiting / user_reply  → WAITING_FOR_USER
        resolve / fixed / done       → RESOLVED
        close / closed               → CLOSED
    """
    msg = user_message.lower()
    current = get_state(ticket_id)
    if current is None:
        return None

    mapping = [
        (["assign"], "ASSIGNED"),
        (["start work", "in progress", "working on", "in_progress"], "IN_PROGRESS"),
        (["waiting for user", "wait for user", "awaiting user", "waiting_for_user"], "WAITING_FOR_USER"),
        (["resolve", "fixed", "solution", "done", "completed"], "RESOLVED"),
        (["close", "closed", "complete"], "CLOSED"),
    ]

    for keywords, target_state in mapping:
        if any(kw in msg for kw in keywords):
            if target_state in VALID_TRANSITIONS.get(current, []):
                transition(ticket_id, target_state, session_id=session_id)
                return target_state

    return None


# ── Internal helpers ──────────────────────────────────────────────────────────

def _now() -> str:
    return datetime.datetime.utcnow().isoformat() + "Z"


def _notify(ticket_id: str, state: str, message: str = "") -> None:
    """Fire notification via notification_service. Non-fatal."""
    try:
        from app.services.notification_service import create_notification
        msg = message or TRANSITION_MESSAGES.get(state, f"Ticket {ticket_id} updated to {state}.").format(
            ticket_id=ticket_id
        )
        create_notification(
            ticket_id=ticket_id,
            recipient="Employee",
            message=msg,
        )
        logger.info(
            "Lifecycle Service: Notification sent for ticket=%s state=%s",
            ticket_id, state,
        )
    except Exception as e:
        logger.error("Lifecycle Service: Failed to send notification: %s", e)


def _update_db_status(ticket_id: str, new_state: str) -> None:
    """Attempt to update the DB ticket.status column. Non-fatal."""
    try:
        from app.database.session import get_db
        from app.database.repositories.ticket_repository import TicketRepository
        with get_db() as db:
            repo = TicketRepository(db)
            all_t = repo.get_all_tickets()
            for t in all_t:
                if t.ticket_id == ticket_id:
                    t.status = new_state
                    db.commit()
                    logger.info(
                        "Lifecycle Service: DB status updated for ticket=%s to %s",
                        ticket_id, new_state,
                    )
                    break
    except Exception as e:
        logger.warning(
            "Lifecycle Service: DB status update failed for ticket=%s: %s",
            ticket_id, e,
        )


def _audit_transition(
    session_id: str,
    ticket_id: str,
    from_state: str,
    to_state: str,
    note: str,
) -> None:
    """Write a trace record for the transition. Non-fatal."""
    try:
        from app.services.audit_service import log_agent_trace
        log_agent_trace(
            session_id=session_id or ticket_id,
            agent_name="Ticket Lifecycle Agent",
            output={
                "ticket_id":  ticket_id,
                "from_state": from_state,
                "to_state":   to_state,
                "note":       note,
                "timestamp":  _now(),
            },
        )
    except Exception as e:
        logger.error("Lifecycle Service: Failed to write audit trace: %s", e)
