import logging
from app.graph.state import AgentState
from app.services.intent_service import detect_intent

logger = logging.getLogger("it-agent-backend")

def intent_node(state: AgentState) -> dict:
    import time
    logger.info("--- Intent Node ---")
    start_time = time.time()
    try:
        user_msg = state.get("user_message", "")
        current_category = state.get("category", "GENERAL")
        detected = detect_intent(user_msg)
        
        # Handle direct errors
        if isinstance(detected, dict) and "debug_error" in detected:
            logger.error("Intent Node failed: %s", detected.get("debug_error"))
            detected = "GENERAL"
            
        final_category = current_category if detected == "GENERAL" else detected
            
        logger.info("Intent Node completed. Detected: %s, Selected Category: %s", detected, final_category)
        
        # Write trace record
        try:
            from app.services.audit_service import log_agent_trace
            log_agent_trace(
                session_id=state.get("session_id"),
                agent_name="Intent Agent",
                output={"category": final_category}
            )
        except Exception as e:
            logger.error("Intent Node: Failed to log trace: %s", e)
            
        return {"category": final_category}
    finally:
        try:
            from app.core.metrics import AGENT_EXECUTION_TIME
            AGENT_EXECUTION_TIME.labels(agent_name="Intent Agent").observe(time.time() - start_time)
        except Exception:
            pass
