"""
Root Cause Node — LangGraph node wrapping RootCauseAgent.

Position: Tool → **RootCause** → Reflection → Decision

Consumes:
    state["category"]
    state["user_message"]
    state["tool_result"]
    state["knowledge_context"]

Produces:
    state["root_cause_analysis"]   — structured root-cause dict
"""

import logging
import time

from app.graph.state import AgentState
from app.agents.root_cause_agent import RootCauseAgent

logger = logging.getLogger("it-agent-backend")

_agent = RootCauseAgent()


def root_cause_node(state: AgentState) -> dict:
    logger.info("--- Root Cause Node ---")
    start_time = time.time()

    try:
        category = state.get("category", "GENERAL")
        user_msg = state.get("user_message", "")
        tool_result = state.get("tool_result") or {}
        knowledge_ctx = state.get("knowledge_context", "")

        analysis = _agent.analyze(
            category=category,
            user_message=user_msg,
            tool_result=tool_result,
            knowledge_context=knowledge_ctx,
        )

        logger.info(
            "Root Cause Node complete — confidence=%.2f, causes=%d, action='%s'",
            analysis.get("confidence", 0.0),
            len(analysis.get("possible_causes", [])),
            analysis.get("recommended_action", ""),
        )

        # Audit trace
        try:
            from app.services.audit_service import log_agent_trace
            log_agent_trace(
                session_id=state.get("session_id"),
                agent_name="Root Cause Agent",
                output=analysis,
            )
        except Exception as e:
            logger.error("Root Cause Node: Failed to log trace: %s", e)

        return {"root_cause_analysis": analysis}

    except Exception as e:
        logger.error("Root Cause Node: Unexpected error: %s", e, exc_info=True)
        return {
            "root_cause_analysis": {
                "observations": ["Root cause analysis could not complete."],
                "possible_causes": [],
                "confidence": 0.0,
                "recommended_action": "",
                "summary": "I encountered an error during root cause analysis. "
                           "The troubleshooting flow will continue with available data.",
            }
        }

    finally:
        try:
            from app.core.metrics import AGENT_EXECUTION_TIME
            AGENT_EXECUTION_TIME.labels(agent_name="Root Cause Agent").observe(
                time.time() - start_time
            )
        except Exception:
            pass
