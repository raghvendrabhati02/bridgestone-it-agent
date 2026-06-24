import logging
import time
from app.graph.state import AgentState
from app.agents.reasoning_agent import ReasoningAgent

logger = logging.getLogger("it-agent-backend")

# Singleton — instantiated once at import time
_reasoning_agent = ReasoningAgent()


def reflection_node(state: AgentState) -> dict:
    """
    LangGraph Reflection Node.

    Sits between tool_node and decision_node in the troubleshooting pipeline.

    Consumes:
        state["tool_result"]   — raw diagnostic output from tool_node
        state["category"]      — detected issue category
        state["user_message"]  — original user query
        state["session_id"]    — for conversation history lookup

    Produces (written into AgentState):
        state["reflection"]    — full structured reflection dict
    """
    logger.info("--- Reflection Node ---")
    start_time = time.time()
    try:
        category    = state.get("category", "GENERAL")
        user_msg    = state.get("user_message", "")
        tool_result = state.get("tool_result")
        session_id  = state.get("session_id")

        # ── Root Cause Analysis (new — from root_cause_node) ─────────
        rca = state.get("root_cause_analysis")

        # Fetch conversation history
        history: list[dict] = []
        try:
            from app.services.conversation_service import get_conversation
            conv_state = get_conversation(session_id)
            if conv_state:
                history = conv_state.conversation_history
        except Exception as e:
            logger.warning("Reflection Node: Could not fetch conversation history: %s", e)

        # Enrich tool_result with root-cause context so the reasoning agent
        # can generate more intelligent hypotheses and findings.
        enriched_tool_result = dict(tool_result) if tool_result else {}
        if rca and isinstance(rca, dict):
            enriched_tool_result["_root_cause_analysis"] = rca
            logger.info(
                "Reflection Node: Enriching with root_cause_analysis — "
                "causes=%d, confidence=%.2f",
                len(rca.get("possible_causes", [])),
                rca.get("confidence", 0.0),
            )

        # Run the Reflection Agent
        reflection = _reasoning_agent.reflect(
            query=user_msg,
            category=category,
            tool_result=enriched_tool_result,
            history=history,
        )

        # Merge root-cause observations into reflection for downstream use
        if rca and isinstance(rca, dict):
            # Append root-cause possible_causes as additional hypotheses
            rca_causes = rca.get("possible_causes", [])
            existing_hyp = reflection.get("hypotheses", [])
            for cause in rca_causes:
                if cause not in existing_hyp:
                    existing_hyp.append(cause)
            reflection["hypotheses"] = existing_hyp

            # If reflection has low confidence but RCA has higher, boost it
            rca_conf = rca.get("confidence", 0.0)
            ref_conf = reflection.get("confidence", 0.0)
            if rca_conf > ref_conf:
                reflection["confidence"] = (rca_conf + ref_conf) / 2

            # Carry forward the recommended action if reflection didn't set one
            if not reflection.get("recommended_action") and rca.get("recommended_action"):
                reflection["recommended_action"] = rca["recommended_action"]

        logger.info(
            "Reflection Node complete. "
            "Confidence=%.2f | Observations=%d | Hypotheses=%d | "
            "ApprovalNeeded=%s | EscalationNeeded=%s | Action='%s'",
            reflection.get("confidence", 0.0),
            len(reflection.get("observations", [])),
            len(reflection.get("hypotheses", [])),
            reflection.get("approval_needed"),
            reflection.get("escalation_needed"),
            reflection.get("recommended_action"),
        )

        # Audit trace
        try:
            from app.services.audit_service import log_agent_trace
            log_agent_trace(
                session_id=session_id,
                agent_name="Reflection Agent",
                output=reflection,
            )
        except Exception as e:
            logger.error("Reflection Node: Failed to log trace: %s", e)

        return {"reflection": reflection}

    except Exception as e:
        logger.error("Reflection Node: Unexpected error: %s", e, exc_info=True)
        return {
            "reflection": {
                "observations": ["Reflection analysis could not be completed due to an internal error."],
                "hypotheses": [],
                "confidence": 0.0,
                "recommended_action": "",
                "findings": "I was unable to complete the diagnostic analysis. Please try again.",
                "escalation_needed": False,
                "approval_needed": False,
                "rationale": f"Reflection node error: {e}",
            }
        }

    finally:
        try:
            from app.core.metrics import AGENT_EXECUTION_TIME
            AGENT_EXECUTION_TIME.labels(agent_name="Reflection Agent").observe(
                time.time() - start_time
            )
        except Exception:
            pass
