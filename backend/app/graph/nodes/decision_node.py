import logging
from app.graph.state import AgentState
from app.services.decision_service import analyze_conversation

logger = logging.getLogger("it-agent-backend")

def decision_node(state: AgentState) -> dict:
    import time
    logger.info("--- Decision Node ---")
    start_time = time.time()
    try:
        # 0. Check pre-evaluated approval state
        approval_status = state.get("approval_status", "PENDING").upper().strip()
        if approval_status == "APPROVED":
            logger.info("Decision Node: User APPROVED recommended action. Routing to execute action.")
            try:
                from app.services.audit_service import log_agent_trace
                log_agent_trace(
                    session_id=state.get("session_id"),
                    agent_name="Approval Agent",
                    output={
                        "approval_status": "APPROVED",
                        "recommended_action": state.get("recommended_action")
                    }
                )
            except Exception as e:
                logger.error("Decision Node: Failed to log approval trace: %s", e)
                
            return {
                "decision": "EXECUTE_ACTION",
                "decision_response": "Request Created Successfully."
            }
        elif approval_status == "REJECTED":
            logger.info("Decision Node: User REJECTED recommended action. Routing to end.")
            try:
                from app.services.audit_service import log_agent_trace
                log_agent_trace(
                    session_id=state.get("session_id"),
                    agent_name="Approval Agent",
                    output={
                        "approval_status": "REJECTED",
                        "recommended_action": state.get("recommended_action")
                    }
                )
            except Exception as e:
                logger.error("Decision Node: Failed to log approval trace: %s", e)
                
            return {
                "decision": "REJECTED",
                "decision_response": "Request creation cancelled. Workflow ended."
            }

        category = state.get("category", "GENERAL")
        user_msg = state.get("user_message", "")
        context = state.get("knowledge_context", "")
        
        session_id = state.get("session_id")
        tool_result = state.get("tool_result")
        # Reflection Agent output — use these structured findings instead of raw tool data
        reflection = state.get("reflection")  # may be None if reflection_node not yet run
        from app.services.conversation_service import get_conversation
        conv_state = get_conversation(session_id)
        history = conv_state.conversation_history if conv_state else []
        
        logger.info(
            "Decision Node: Running analyze_conversation for category: %s | "
            "Reflection present: %s | Confidence: %.2f",
            category,
            reflection is not None,
            reflection.get("confidence", 0.0) if reflection else 0.0,
        )
        decision_result = analyze_conversation(
            category,
            history,
            user_msg,
            context,
            tool_result=tool_result,
            session_id=session_id,
            reflection=reflection,
        )
        
        # Handle direct error responses
        if isinstance(decision_result, dict) and "debug_error" in decision_result:
            logger.error("Decision Node: analyze_conversation returned error: %s", decision_result.get("debug_error"))
            decision = "ASK_MORE_INFO"
            decision_response = None
            approval_required = False
            recommended_action = ""
        else:
            decision = decision_result.get("action", "ASK_MORE_INFO")
            decision_response = decision_result.get("response") or ""   # never None — AgentState declares str
            approval_required = decision_result.get("approval_required", False)
            recommended_action = decision_result.get("recommended_action", "")
            category = decision_result.get("category", category)
            
        if decision == "RECOMMEND_ACTION":
            # FIX #2: Must become EXECUTE_ACTION so route_decision routes to approval_node.
            # WAIT_FOR_APPROVAL is not in the routing map and falls through to END silently.
            decision = "EXECUTE_ACTION"
            try:
                from app.services.audit_service import log_approval
                log_approval(
                    session_id=session_id,
                    recommended_action=recommended_action,
                    approval_status="PENDING"
                )
            except Exception as e:
                logger.error("Decision Node: Failed to log pending approval: %s", e)

        logger.info("DEBUG RECOMMENDED_ACTION=%s", recommended_action)
        logger.info("DEBUG DECISION=%s", decision)
        logger.info("Decision Node completed. Decision: %s, Response: %s", decision, decision_response)
        
        # Write trace record
        try:
            from app.services.audit_service import log_agent_trace
            log_agent_trace(
                session_id=session_id,
                agent_name="Decision Agent",
                output={
                    "decision": decision,
                    "decision_response": decision_response,
                    "approval_required": approval_required,
                    "recommended_action": recommended_action
                }
            )
        except Exception as e:
            logger.error("Decision Node: Failed to log trace: %s", e)
            
        return {
            "decision": decision,
            "decision_response": decision_response,
            "approval_required": approval_required,
            "approval_status": "PENDING" if approval_required else "PENDING",
            "recommended_action": recommended_action,
            "category": category
        }
    finally:
        try:
            from app.core.metrics import AGENT_EXECUTION_TIME
            AGENT_EXECUTION_TIME.labels(agent_name="Decision Agent").observe(time.time() - start_time)
        except Exception:
            pass
