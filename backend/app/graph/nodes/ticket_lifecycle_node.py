"""
Ticket Lifecycle Node
=====================
Runs immediately after ticket_node (before assignment_node).

Responsibilities:
  1. Initialise the lifecycle record for the newly-created ticket.
  2. Attempt to auto-advance the state to ASSIGNED when a team is already
     known (ticket.assigned_team is set by ticket_node).
  3. Check whether the incoming user message contains a lifecycle intent
     (e.g. "resolve", "close") and apply the corresponding transition.
  4. Store the lifecycle data in state["ticket_lifecycle"].
  5. Update state["notifications"] with any lifecycle events.

The node NEVER raises an exception that would crash the graph.
"""
import logging
import time

from app.graph.state import AgentState

logger = logging.getLogger("it-agent-backend")


def ticket_lifecycle_node(state: AgentState) -> dict:
    logger.info("--- Ticket Lifecycle Node ---")
    start_time = time.time()

    try:
        session_id  = state.get("session_id", "")
        ticket      = state.get("ticket") or {}
        ticket_id   = ticket.get("ticket_id") or state.get("active_ticket", "")
        user_msg    = state.get("user_message", "")
        assigned_team = ticket.get("assigned_team", "")

        if not ticket_id:
            logger.warning("Lifecycle Node: No ticket_id found in state. Skipping.")
            return {}

        from app.services.ticket_lifecycle_service import (
            init_lifecycle,
            transition,
            auto_transition_from_intent,
            get_lifecycle,
        )

        # ── 1. Init (idempotent) ──────────────────────────────────────────────
        lifecycle = init_lifecycle(ticket_id, initial_state="OPEN")

        # ── 2. Auto-advance to ASSIGNED if team is known ──────────────────────
        if assigned_team and lifecycle["state"] == "OPEN":
            lifecycle = transition(
                ticket_id=ticket_id,
                new_state="ASSIGNED",
                note=f"Automatically assigned to {assigned_team}",
                session_id=session_id,
            )

        # ── 3. Check user message for explicit lifecycle intent ───────────────
        if user_msg:
            auto_transition_from_intent(
                ticket_id=ticket_id,
                user_message=user_msg,
                session_id=session_id,
            )
            # Re-read after possible transition
            lifecycle = get_lifecycle(ticket_id) or lifecycle

        # ── 4. Collect notifications generated for this ticket ────────────────
        notifications = _collect_notifications(ticket_id, state)

        # ── 5. Audit ──────────────────────────────────────────────────────────
        try:
            from app.services.audit_service import log_agent_trace
            log_agent_trace(
                session_id=session_id,
                agent_name="Ticket Lifecycle Agent",
                output={
                    "ticket_id": ticket_id,
                    "lifecycle": lifecycle,
                },
            )
        except Exception as e:
            logger.error("Lifecycle Node: Audit failed: %s", e)

        logger.info(
            "Lifecycle Node: ticket=%s current_state=%s history_entries=%d",
            ticket_id,
            lifecycle.get("state"),
            len(lifecycle.get("history", [])),
        )

        return {
            "ticket_lifecycle": lifecycle,
            "notifications":    notifications,
        }

    except Exception as e:
        logger.error("Lifecycle Node: Unexpected error — %s", e, exc_info=True)
        return {}

    finally:
        try:
            from app.core.metrics import AGENT_EXECUTION_TIME
            AGENT_EXECUTION_TIME.labels(agent_name="Ticket Lifecycle Agent").observe(
                time.time() - start_time
            )
        except Exception:
            pass


# ── helpers ───────────────────────────────────────────────────────────────────

def _collect_notifications(ticket_id: str, state: AgentState) -> list:
    """Merge existing state notifications with new ones for this ticket."""
    existing = list(state.get("notifications") or [])
    try:
        from app.services.notification_service import get_notifications
        all_notifs = get_notifications()
        ticket_notifs = [
            n for n in all_notifs if n.get("ticket_id") == ticket_id
        ]
        # Deduplicate by notification_id
        seen_ids = {n.get("notification_id") for n in existing}
        for n in ticket_notifs:
            if n.get("notification_id") not in seen_ids:
                existing.append(n)
                seen_ids.add(n.get("notification_id"))
    except Exception as e:
        logger.error("Lifecycle Node: Failed to collect notifications: %s", e)
    return existing
