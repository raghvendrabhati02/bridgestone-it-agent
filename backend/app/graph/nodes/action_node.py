import logging
from app.graph.state import AgentState
from app.services.action_service import execute_action

logger = logging.getLogger("it-agent-backend")

def action_node(state: AgentState) -> dict:
    """
    Orchestrator node for the Action Agent. Executes recommended IT service requests.
    """
    import time
    logger.info("--- Action Agent Node ---")
    start_time = time.time()
    try:
        action_type = state.get("recommended_action", "GENERAL")
        category = state.get("category", "GENERAL")
        user_msg = state.get("user_message", "")
        
        result = execute_action(action_type, category, user_msg)
        logger.info("Action Agent Node completed. Result: %s", result)
        
        # Write trace record
        try:
            from app.services.audit_service import log_agent_trace
            log_agent_trace(
                session_id=state.get("session_id"),
                agent_name="Action Agent",
                output={"action_result": result}
            )
        except Exception as e:
            logger.error("Action Node: Failed to log trace: %s", e)
            
        return {"action_result": result}
    finally:
        try:
            from app.core.metrics import AGENT_EXECUTION_TIME
            AGENT_EXECUTION_TIME.labels(agent_name="Action Agent").observe(time.time() - start_time)
        except Exception:
            pass
