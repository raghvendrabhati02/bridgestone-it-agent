import logging
from app.graph.state import AgentState
from app.services.assignment_service import get_assignment_team

logger = logging.getLogger("it-agent-backend")

def assignment_node(state: AgentState) -> dict:
    logger.info("--- Assignment Node ---")
    category = state.get("category", "GENERAL")
    assigned_team = get_assignment_team(category)
    logger.info("Assignment Node completed. Assigned Team: %s", assigned_team)
    
    # Write trace record
    try:
        from app.services.audit_service import log_agent_trace
        log_agent_trace(
            session_id=state.get("session_id"),
            agent_name="Assignment Agent",
            output={"assigned_team": assigned_team}
        )
    except Exception as e:
        logger.error("Assignment Node: Failed to log trace: %s", e)
        
    return {"assigned_team": assigned_team}
