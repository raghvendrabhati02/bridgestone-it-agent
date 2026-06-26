"""
Ticket Lifecycle Node  (Enterprise Edition)
=============================================
Runs in two modes:

  MODE A — Ticket Creation (called via ticket → ticket_lifecycle)
    • Initialises the lifecycle record for the newly-created ticket.
    • Auto-advances to ASSIGNED when a team is already known.
    • Checks the user message for an explicit lifecycle intent.

  MODE B — Standalone Lifecycle Command (called via context_router → ticket_lifecycle)
    • User has issued a command like "start work", "resolved", "close ticket INC000031".
    • Resolves the ticket ID from:
        1. state["ticket"]["ticket_id"]  (ticket creation path)
        2. state["active_ticket"]         (follow-up message path)
        3. An INC/TKT reference embedded in the user message itself
    • Performs RBAC permission check (role must be MANAGER or ADMIN for lifecycle ops).
    • Performs ticket ownership check (employees may only modify their own tickets).
    • Calls auto_transition_from_intent to apply the correct state transition.
    • Sets state["decision_response"] so the API layer returns a clear confirmation.

Enterprise additions
---------------------
  • RBAC check via rbac_service.has_permission()
  • Ownership check via ticket_ownership_service.can_modify_ticket()
  • Structured audit via rbac_audit_service.log_rbac_event()
  • ACCESS_DENIED decision returned on any policy violation

The node NEVER raises an exception that would crash the graph.
"""
import logging
import re
import time

from app.graph.state import AgentState

logger = logging.getLogger("it-agent-backend")

# Regex to pull explicit ticket IDs from user messages, e.g. "close ticket INC000031"
_TICKET_ID_RE = re.compile(r"\b(INC\d+|TKT[-\w]+)\b", re.IGNORECASE)


def ticket_lifecycle_node(state: AgentState) -> dict:
    logger.info("--- Ticket Lifecycle Node ---")
    start_time = time.time()

    try:
        session_id    = state.get("session_id", "")
        ticket        = state.get("ticket") or {}
        active_ticket = state.get("active_ticket", "")
        user_msg      = state.get("user_message", "")
        username      = state.get("username", "unknown")
        user_role     = (state.get("user_role") or "EMPLOYEE").upper().strip()

        # ── Resolve ticket_id (priority: ticket dict > active_ticket > message) ─
        ticket_id = ticket.get("ticket_id") or active_ticket or ""

        # If still not found, try to extract from the user message
        if not ticket_id and user_msg:
            m = _TICKET_ID_RE.search(user_msg)
            if m:
                ticket_id = m.group(0).upper()
                logger.info(
                    "Lifecycle Node: Extracted ticket_id '%s' from user message.", ticket_id
                )

        if not ticket_id:
            logger.warning("Lifecycle Node: No ticket_id found in state. Skipping.")
            return {
                "decision_response": (
                    "No active ticket found. Please specify a ticket ID "
                    "(e.g. 'close ticket INC000031')."
                )
            }

        from app.services.ticket_lifecycle_service import (
            init_lifecycle,
            transition,
            auto_transition_from_intent,
            get_lifecycle,
        )
        from app.services import rbac_service, ticket_ownership_service, rbac_audit_service

        assigned_team = ticket.get("assigned_team", "")
        is_creation_path = bool(ticket.get("ticket_id"))

        # ── 1. Init (idempotent) ──────────────────────────────────────────────
        lifecycle = init_lifecycle(ticket_id, initial_state="OPEN")

        # ── 2. For standalone lifecycle commands, enforce RBAC + ownership ────
        if not is_creation_path and user_msg:
            # Determine which RBAC action the user intent requires
            target_state = _resolve_target_state(user_msg)
            required_action = rbac_service.infer_lifecycle_action(target_state)

            # 2a. RBAC permission check
            if not rbac_service.has_permission(user_role, required_action):
                rbac_audit_service.log_rbac_event(
                    user=username,
                    role=user_role,
                    action="ACCESS_DENIED",
                    ticket_id=ticket_id,
                    old_state=lifecycle.get("state"),
                    new_state=None,
                    details={
                        "reason": "RBAC_DENIED",
                        "required_action": required_action,
                        "session_id": session_id,
                    },
                )
                return rbac_service.build_access_denied_response(
                    role=user_role,
                    action=required_action,
                    ticket_id=ticket_id,
                )

            # 2b. Ticket ownership check
            if not ticket_ownership_service.can_modify_ticket(
                username=username,
                role=user_role,
                ticket_id=ticket_id,
            ):
                rbac_audit_service.log_rbac_event(
                    user=username,
                    role=user_role,
                    action="ACCESS_DENIED",
                    ticket_id=ticket_id,
                    old_state=lifecycle.get("state"),
                    new_state=None,
                    details={
                        "reason": "OWNERSHIP_DENIED",
                        "session_id": session_id,
                    },
                )
                return ticket_ownership_service.build_ownership_denied_response(
                    username=username,
                    ticket_id=ticket_id,
                )

        # ── 3. Auto-advance to ASSIGNED if team is known (creation path only) ──
        if is_creation_path and assigned_team and lifecycle["state"] == "OPEN":
            old_state = lifecycle["state"]
            lifecycle = transition(
                ticket_id=ticket_id,
                new_state="ASSIGNED",
                note=f"Automatically assigned to {assigned_team}",
                session_id=session_id,
            )
            # Audit ticket creation + initial assignment
            rbac_audit_service.log_rbac_event(
                user=username,
                role=user_role,
                action="create_ticket",
                ticket_id=ticket_id,
                old_state=old_state,
                new_state=lifecycle["state"],
                details={"assigned_team": assigned_team, "session_id": session_id},
            )

        # ── 4. Apply lifecycle intent from user message ───────────────────────
        new_state = None
        if user_msg:
            old_state_before = lifecycle.get("state")
            new_state = auto_transition_from_intent(
                ticket_id=ticket_id,
                user_message=user_msg,
                session_id=session_id,
            )
            # Re-read after possible transition
            lifecycle = get_lifecycle(ticket_id) or lifecycle

            # Emit audit if a transition actually happened
            if new_state:
                rbac_audit_service.log_rbac_event(
                    user=username,
                    role=user_role,
                    action=rbac_service.infer_lifecycle_action(new_state),
                    ticket_id=ticket_id,
                    old_state=old_state_before,
                    new_state=new_state,
                    details={"session_id": session_id, "user_message": user_msg[:200]},
                )

        # ── 5. Build a human-readable confirmation response ───────────────────
        current_state = lifecycle.get("state", "UNKNOWN")
        if new_state:
            decision_response = (
                f"Ticket **{ticket_id}** status updated to **{current_state}**."
            )
        elif not is_creation_path:
            decision_response = (
                f"No valid transition applied for ticket **{ticket_id}**. "
                f"Current status is **{current_state}**. "
                f"Check that the command is valid from the current state."
            )
        else:
            decision_response = ""

        # ── 6. Collect notifications generated for this ticket ────────────────
        notifications = _collect_notifications(ticket_id, state)

        # ── 7. Audit (agent trace) ────────────────────────────────────────────
        try:
            from app.services.audit_service import log_agent_trace
            log_agent_trace(
                session_id=session_id,
                agent_name="Ticket Lifecycle Agent",
                output={
                    "ticket_id": ticket_id,
                    "lifecycle": lifecycle,
                    "new_state": new_state,
                    "username": username,
                    "user_role": user_role,
                },
            )
        except Exception as e:
            logger.error("Lifecycle Node: Agent trace audit failed: %s", e)

        logger.info(
            "Lifecycle Node: ticket=%s current_state=%s new_state=%s history_entries=%d",
            ticket_id,
            current_state,
            new_state,
            len(lifecycle.get("history", [])),
        )

        out = {
            "ticket_lifecycle": lifecycle,
            "notifications":    notifications,
        }
        if decision_response:
            out["decision_response"] = decision_response

        return out

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

def _resolve_target_state(user_msg: str) -> str:
    """
    Peeks at the user intent and returns the likely target lifecycle state.
    Used to determine which RBAC permission to check BEFORE calling
    auto_transition_from_intent.  Defaults to 'GENERIC' (→ update_ticket_lifecycle).
    """
    msg = user_msg.lower()
    if any(kw in msg for kw in ["close", "closed"]):
        return "CLOSED"
    if any(kw in msg for kw in ["resolved", "resolve", "fixed", "done", "completed"]):
        return "RESOLVED"
    if any(kw in msg for kw in ["assign"]):
        return "ASSIGNED"
    if any(kw in msg for kw in ["in progress", "start work", "working on"]):
        return "IN_PROGRESS"
    if any(kw in msg for kw in ["waiting for user", "wait for user"]):
        return "WAITING_FOR_USER"
    return "GENERIC"


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
