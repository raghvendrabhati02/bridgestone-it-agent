import logging
import re

from app.agents.ticket_status_agent import TicketStatusAgent

logger = logging.getLogger("it-agent-backend")

_status_agent = TicketStatusAgent()

# ---------------------------------------------------------------------------
# Lifecycle command keywords that map to ticket state transitions.
# Ordered longest-match first so "start work" beats "start".
# ---------------------------------------------------------------------------
_LIFECYCLE_KEYWORDS = [
    # IN_PROGRESS
    "start work",
    "in progress",
    "working on",
    "in_progress",
    "start working",
    # WAITING_FOR_USER
    "waiting for user",
    "wait for user",
    "awaiting user",
    "waiting_for_user",
    # RESOLVED
    "resolved",
    "resolve",
    "fixed",
    "done",
    "completed",
    "solution",
    # CLOSED
    "close ticket",
    "close",
    "closed",
    # ASSIGNED
    "assign",
]


_TICKET_ID_RE = re.compile(r"\b(INC\d+|TKT[-\w]+)\b", re.IGNORECASE)


def _is_lifecycle_command(message: str) -> bool:
    """Return True when the message contains a ticket lifecycle intent keyword."""
    msg = message.lower().strip()
    return any(kw in msg for kw in _LIFECYCLE_KEYWORDS)


def _has_explicit_ticket_id(message: str) -> bool:
    """Return True if the message contains a ticket ID match."""
    return bool(_TICKET_ID_RE.search(message))


def context_router_node(state) -> dict:
    """
    Routes the conversation to the appropriate sub-graph path.

    Priority order:
      1. ticket_lifecycle — user is issuing a lifecycle command (start work / resolved / close …)
                            AND there is ticket context (active_ticket or ticket ID in message)
      2. ticket_status   — user is asking for the current status of a ticket
      3. intent          — standard troubleshooting / decision pipeline

    Incoming keys used: user_message, active_ticket
    Outgoing keys:      route
    """
    message = state.get("user_message", "")
    active_ticket = state.get("active_ticket", "")

    logger.info(
        "Context Router Node: incoming — message='%s', active_ticket='%s'",
        message[:80],
        active_ticket,
    )

    # ── 1. Lifecycle command check (highest priority) ─────────────────────────
    if _is_lifecycle_command(message):
        if active_ticket or _has_explicit_ticket_id(message):
            logger.info(
                "Context Router Node: Lifecycle command detected with ticket context. Routing to 'ticket_lifecycle'."
            )
            return {"route": "ticket_lifecycle"}
        else:
            logger.info(
                "Context Router Node: Lifecycle command detected but NO ticket context. Falling through to status/intent."
            )

    # ── 2. Service request check ──────────────────────────────────────────────
    intent = state.get("intent", "")
    active_request = state.get("active_request", "")
    if intent == "SERVICE_REQUEST" or active_request:
        logger.info("Context Router Node: Service request intent or active request context. Routing to 'service_request'.")
        return {"route": "service_request"}

    # ── 3. Ticket status check ────────────────────────────────────────────────
    try:
        is_status = _status_agent.is_status_request(message)
    except Exception as e:
        logger.error("Context Router Node: TicketStatusAgent.is_status_request failed: %s", e)
        is_status = False

    route = "ticket_status" if is_status else "intent"

    logger.info("Context Router Node: outgoing — route='%s'", route)
    return {"route": route}