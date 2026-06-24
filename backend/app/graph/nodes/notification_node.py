import logging
from app.graph.state import AgentState
from app.services.notification_service import get_notifications

logger = logging.getLogger("it-agent-backend")

def notification_node(state: AgentState) -> dict:
    logger.info("--- Notification Node ---")
    ticket = state.get("ticket", {})
    ticket_id = ticket.get("ticket_id")
    
    # Retrieve all notifications and filter for this ticket
    all_notifs = get_notifications()
    ticket_notifs = [notif for notif in all_notifs if notif.get("ticket_id") == ticket_id]
    
    logger.info("Notification Node completed. Notification count for ticket %s: %d", ticket_id, len(ticket_notifs))
    
    # Write trace record
    try:
        from app.services.audit_service import log_agent_trace
        log_agent_trace(
            session_id=state.get("session_id"),
            agent_name="Notification Agent",
            output={"notifications": ticket_notifs}
        )
    except Exception as e:
        logger.error("Notification Node: Failed to log trace: %s", e)
        
    return {"notifications": ticket_notifs}
