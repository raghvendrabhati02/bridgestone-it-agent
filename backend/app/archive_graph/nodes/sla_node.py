import logging
from app.graph.state import AgentState
from app.services.sla_service import get_all_sla_records

logger = logging.getLogger("it-agent-backend")

def sla_node(state: AgentState) -> dict:
    import time
    logger.info("--- SLA Node ---")
    start_time = time.time()
    try:
        ticket = state.get("ticket", {})
        ticket_id = ticket.get("ticket_id")
        
        # Try retrieving from SLA records
        records = get_all_sla_records()
        sla_record = next((r for r in records if r.get("ticket_id") == ticket_id), None)
        
        if sla_record:
            sla_data = {
                "priority": sla_record.get("priority"),
                "sla_hours": sla_record.get("sla_hours")
            }
        else:
            # Fallback to values in ticket dictionary
            sla_data = {
                "priority": ticket.get("priority", "LOW"),
                "sla_hours": ticket.get("sla_hours", 24)
            }
            
        logger.info("SLA Node completed. SLA Data: %s", sla_data)
        
        # Write trace record
        try:
            from app.services.audit_service import log_agent_trace
            log_agent_trace(
                session_id=state.get("session_id"),
                agent_name="SLA Agent",
                output={"sla": sla_data}
            )
        except Exception as e:
            logger.error("SLA Node: Failed to log trace: %s", e)
            
        return {"sla": sla_data}
    finally:
        try:
            from app.core.metrics import AGENT_EXECUTION_TIME
            AGENT_EXECUTION_TIME.labels(agent_name="SLA Agent").observe(time.time() - start_time)
        except Exception:
            pass
