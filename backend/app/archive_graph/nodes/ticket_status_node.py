import logging

from app.graph.state import AgentState

logger = logging.getLogger("it-agent-backend")


def ticket_status_node(state: AgentState) -> dict:
    """
    Looks up the active ticket for the current session and returns a
    natural-language status update.

    Returns using the canonical LangGraph state keys:
        decision        → "TICKET_STATUS"
        decision_response → human-readable status text
    """
    ticket_id = state.get("active_ticket") or ""

    logger.info(
        "Ticket Status Node: session_id=%s | active_ticket='%s'",
        state.get("session_id"),
        ticket_id,
    )

    # ── Fallback: scan conversation history for a ticket ID ─────────────────
    if not ticket_id:
        session_id = state.get("session_id")
        if session_id:
            try:
                import re
                from app.database.session import get_db
                from app.database.repositories.conversation_repository import (
                    ConversationRepository,
                )

                with get_db() as db:
                    repo = ConversationRepository(db)
                    turns = repo.get_turns(session_id)

                for turn in reversed(turns):
                    match = re.search(r"INC\d{6}", turn.agent_response or "")
                    if match:
                        ticket_id = match.group(0)
                        logger.info(
                            "Ticket Status Node: Recovered ticket_id=%s from history",
                            ticket_id,
                        )
                        break
            except Exception as e:
                logger.warning(
                    "Ticket Status Node: History scan failed: %s", e
                )

    # ── No ticket found at all ───────────────────────────────────────────────
    if not ticket_id:
        logger.warning("Ticket Status Node: No active ticket found in state or history.")
        return {
            "decision": "TICKET_STATUS",
            "decision_response": (
                "I don't have an active ticket on record for this conversation yet. "
                "If you'd like me to raise a support ticket, just let me know!"
            ),
        }

    # ── Fetch from DB ────────────────────────────────────────────────────────
    try:
        from app.services.ticket_service import get_ticket

        ticket = get_ticket(ticket_id)
    except Exception as e:
        logger.error(
            "Ticket Status Node: Error fetching ticket %s: %s", ticket_id, e
        )
        ticket = None

    if not ticket:
        logger.warning("Ticket Status Node: Ticket %s not found in DB.", ticket_id)
        return {
            "decision": "TICKET_STATUS",
            "decision_response": (
                f"I have ticket reference **{ticket_id}** on file, but I couldn't "
                f"retrieve its current details. Please check the IT support portal "
                f"or contact the helpdesk for the latest status."
            ),
        }

    # ── Build human-readable response ────────────────────────────────────────
    status_text = ticket.get("status") or "Open"
    team_text = ticket.get("assigned_team") or "the IT support team"
    priority_text = ticket.get("priority") or "Normal"
    sla_hours = ticket.get("sla_hours")
    sla_text = f"{sla_hours} hours" if sla_hours else "standard SLA"

    response = (
        f"Here's the latest on ticket **{ticket_id}**: "
        f"It is currently **{status_text}** and assigned to **{team_text}**. "
        f"Priority is **{priority_text}** with an SLA target of **{sla_text}**."
    )

    # ── Memory context enrichment ──────────────────────────────────────────
    memory = state.get("memory") or {}
    problem_summary = memory.get("last_problem_summary", "")
    active_issue = memory.get("active_issue", "")
    if problem_summary:
        response += (
            f"\n\nThis ticket was created for the "
            f"**{active_issue}** issue you reported earlier: "
            f"*\"{problem_summary}\"*."
        )
    elif active_issue:
        response += (
            f"\n\nThis ticket is related to the **{active_issue}** issue "
            f"discussed in this conversation."
        )
    # ───────────────────────────────────────────────────────────────────────

    response += (
        " If you need to escalate, please contact the assigned team directly."
    )

    logger.info(
        "Ticket Status Node: Returning status for ticket %s → %s",
        ticket_id,
        status_text,
    )

    return {
        "decision": "TICKET_STATUS",
        "decision_response": response,
        # Ensure active_ticket stays in state
        "active_ticket": ticket_id,
    }