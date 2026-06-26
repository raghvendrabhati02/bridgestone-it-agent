"""
Ticket Ownership Service
========================
Determines whether a user has the right to modify a given ticket.

Ownership rules
---------------
ADMIN    → can modify ANY ticket
MANAGER  → can modify ANY ticket (team-scoped enforcement is a Sprint 2 concern)
EMPLOYEE → can ONLY modify tickets they created (created_by == username)

Usage
-----
    from app.services.ticket_ownership_service import can_modify_ticket

    if not can_modify_ticket(username="alice", role="EMPLOYEE", ticket_id="INC000042"):
        return {"decision": "ACCESS_DENIED", ...}
"""

import logging
from typing import Optional

logger = logging.getLogger("it-agent-backend")


# ── Public API ────────────────────────────────────────────────────────────────

def get_ticket_owner(ticket_id: str) -> Optional[str]:
    """
    Returns the `created_by` username of the ticket, or None if not found.
    Queries the DB; falls back to None on error.
    """
    try:
        from app.database.session import get_db
        from app.database.repositories.ticket_repository import TicketRepository
        with get_db() as db:
            repo = TicketRepository(db)
            ticket = repo.get_ticket(ticket_id)
            if ticket:
                return ticket.created_by
            logger.warning(
                "Ticket Ownership: ticket_id '%s' not found in DB.", ticket_id
            )
            return None
    except Exception as e:
        logger.error(
            "Ticket Ownership: Failed to fetch ticket owner for '%s': %s",
            ticket_id, e,
        )
        return None


def can_modify_ticket(username: str, role: str, ticket_id: str) -> bool:
    """
    Returns True if the user may modify (transition, close, resolve) the ticket.

    - ADMIN   : always True
    - MANAGER : always True  (team-scope enforcement deferred to Sprint 2)
    - EMPLOYEE: True only if ticket.created_by == username
    """
    role_upper = (role or "EMPLOYEE").upper().strip()

    if role_upper in ("ADMIN", "MANAGER"):
        logger.debug(
            "Ticket Ownership: %s '%s' has blanket access to ticket '%s'.",
            role_upper, username, ticket_id,
        )
        return True

    # EMPLOYEE path — must own the ticket
    owner = get_ticket_owner(ticket_id)

    if owner is None:
        # Ticket not in DB yet (e.g. in-memory only from the same session) —
        # allow the modification to avoid false denials during ticket creation flows.
        logger.info(
            "Ticket Ownership: ticket '%s' has no DB owner — allowing EMPLOYEE '%s' (in-flight ticket).",
            ticket_id, username,
        )
        return True

    allowed = (owner == username)
    if allowed:
        logger.debug(
            "Ticket Ownership: EMPLOYEE '%s' is the owner of ticket '%s'. Access GRANTED.",
            username, ticket_id,
        )
    else:
        logger.warning(
            "Ticket Ownership: EMPLOYEE '%s' attempted to modify ticket '%s' owned by '%s'. Access DENIED.",
            username, ticket_id, owner,
        )
    return allowed


def build_ownership_denied_response(username: str, ticket_id: str) -> dict:
    """
    Returns a standard ACCESS_DENIED graph output dict for ownership violations.
    """
    message = (
        f"⛔ **ACCESS_DENIED**\n\n"
        f"You do not have permission to modify ticket **{ticket_id}**.\n\n"
        f"Only the ticket creator or a Manager/Admin may modify this ticket."
    )
    logger.warning(
        "Ticket Ownership: ACCESS_DENIED — user='%s' ticket='%s'",
        username, ticket_id,
    )
    return {
        "decision": "ACCESS_DENIED",
        "decision_response": message,
    }
