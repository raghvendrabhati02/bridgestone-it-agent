import logging
from app.graph.state import AgentState
from app.services.tool_agent import execute_tools_for_category

logger = logging.getLogger("it-agent-backend")

def tool_node(state: AgentState) -> dict:
    import time
    logger.info("--- Tool Node ---")
    start_time = time.time()
    try:
        category = state.get("category", "GENERAL")
        user_msg = state.get("user_message", "")
        tool_result = execute_tools_for_category(category, user_msg)
        logger.info("Tool Node completed. Result: %s", tool_result)
        
        # Write trace record
        try:
            from app.services.audit_service import log_agent_trace
            log_agent_trace(
                session_id=state.get("session_id"),
                agent_name="Tool Agent",
                output={"tool_result": tool_result}
            )
        except Exception as e:
            logger.error("Tool Node: Failed to log trace: %s", e)
            
        return {"tool_result": tool_result}
    finally:
        try:
            from app.core.metrics import AGENT_EXECUTION_TIME
            AGENT_EXECUTION_TIME.labels(agent_name="Tool Agent").observe(time.time() - start_time)
        except Exception:
            pass
