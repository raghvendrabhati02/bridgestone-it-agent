import logging

from app.agents.ticket_status_agent import TicketStatusAgent

logger = logging.getLogger("it-agent-backend")

_status_agent = TicketStatusAgent()


def context_router_node(state) -> dict:
    """
    Routes the conversation to either the ticket_status path or the
    standard intent/troubleshooting path.

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

    try:
        is_status = _status_agent.is_status_request(message)
    except Exception as e:
        logger.error("Context Router Node: TicketStatusAgent.is_status_request failed: %s", e)
        is_status = False

    route = "ticket_status" if is_status else "intent"

    logger.info("Context Router Node: outgoing — route='%s'", route)

    return {"route": route}