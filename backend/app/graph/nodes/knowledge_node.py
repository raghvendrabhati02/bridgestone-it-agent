import logging
from app.graph.state import AgentState
from app.services.rag_service import load_knowledge_context

logger = logging.getLogger("it-agent-backend")

def knowledge_node(state: AgentState) -> dict:
    import time
    logger.info("--- Knowledge Node ---")
    start_time = time.time()
    try:
        category = state.get("category", "GENERAL")
        context = load_knowledge_context(category)
        logger.info("Knowledge Node completed. Context loaded.")
        
        # Write trace record
        try:
            from app.services.audit_service import log_agent_trace
            log_agent_trace(
                session_id=state.get("session_id"),
                agent_name="Knowledge Agent",
                output={"knowledge_context": context}
            )
        except Exception as e:
            logger.error("Knowledge Node: Failed to log trace: %s", e)
            
        return {"knowledge_context": context}
    finally:
        try:
            from app.core.metrics import AGENT_EXECUTION_TIME
            AGENT_EXECUTION_TIME.labels(agent_name="Knowledge Agent").observe(time.time() - start_time)
        except Exception:
            pass
