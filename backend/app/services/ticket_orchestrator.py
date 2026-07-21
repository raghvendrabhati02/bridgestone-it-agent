"""
ticket_orchestrator.py
─────────────────────────────────────────────────────────────────────────────
Single responsibility: create a ticket from a conversation session.

FIXED: Now delegates to ticket_service.create_ticket() which handles:
  • Sequential INC/REQ ID generation
  • ITSM classification (INCIDENT vs SERVICE_REQUEST)
  • Database persistence
  • WAITING_MANAGER status for service requests
  • SLA calculation and assignment
  • Notifications to employee and manager
  • RBAC audit log

Design contract:
  • Retrieves issue description from conversation history (first user turn).
  • Delegates to ticket_service.create_ticket().
  • Never raises — returns an empty dict on failure so callers can handle gracefully.
"""

from __future__ import annotations

import logging
import traceback
from typing import TYPE_CHECKING, Optional

import app.services.conversation_memory as memory

if TYPE_CHECKING:
    from app.services.conversation_service import SessionState

logger = logging.getLogger("it-agent-backend")


class TicketOrchestrator:
    """Orchestrates ticket creation from a conversation session."""

    def create(
        self, state: "SessionState", username: Optional[str] = None
    ) -> dict:
        """
        Create a ticket for the current session's issue.

        Delegates to ticket_service.create_ticket() to ensure:
          - Database persistence
          - Correct INC/REQ ID generation
          - ITSM classification (INCIDENT vs SERVICE_REQUEST)
          - WAITING_MANAGER status for service requests
          - SLA and notification handling

        Returns the full ticket details dict, or {"error": True} on failure.
        """
        from app.services.ticket_service import create_ticket

        logger.info(
            ">>> ENTRY [TicketOrchestrator.create]: session_id=%s, username=%s, "
            "category=%s, phase=%s",
            state.session_id,
            username,
            state.category,
            getattr(state.phase, 'value', str(state.phase)),
        )

        # Build issue description from conversation history
        hist = memory.get_history(state.session_id)
        if hist:
            # Use the first user message as the canonical description
            user_msgs = [m["text"] for m in hist if m.get("sender") == "user"]
            issue_desc = user_msgs[0] if user_msgs else hist[0].get("text", "IT Support Issue")
            logger.info(
                "[TicketOrchestrator.create] History has %d entries, %d user messages. "
                "Using issue_desc='%.120s'",
                len(hist),
                len(user_msgs),
                issue_desc,
            )
        else:
            issue_desc = state.active_issue or "IT Support Issue"
            logger.info(
                "[TicketOrchestrator.create] No conversation history found — "
                "using active_issue='%.120s'",
                issue_desc,
            )

        category = state.category or "GENERAL"

        logger.info(
            "[TicketOrchestrator.create] Calling ticket_service.create_ticket with "
            "category=%s, created_by=%s, description='%.120s'",
            category,
            username,
            issue_desc,
        )

        try:
            ticket = create_ticket(
                category=category,
                issue_description=issue_desc,
                created_by=username,
            )

            logger.info(
                "<<< EXIT [TicketOrchestrator.create]: ticket_id=%s, request_type=%s, "
                "status=%s, servicenow_number=%s, servicenow_id=%s, error=%s",
                ticket.get("ticket_id"),
                ticket.get("request_type"),
                ticket.get("status"),
                ticket.get("servicenow_number"),
                ticket.get("servicenow_id"),
                ticket.get("error"),
            )
            return ticket

        except Exception as exc:
            logger.error(
                "!!! EXCEPTION [TicketOrchestrator.create]: %s\n%s",
                exc,
                traceback.format_exc(),
            )
            return {
                "error": True,
                "message": (
                    "I am sorry, but the ticketing system is currently unavailable. "
                    "Please try again later, or contact the IT Helpdesk directly."
                ),
            }
