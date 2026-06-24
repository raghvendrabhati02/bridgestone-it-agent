"""
Memory Node — LangGraph node that loads session memory at the start of graph execution.

Position: Router → **Memory** → Context Router

Consumes:
    state["session_id"]
    state["user_message"]
    state["active_issue"]
    state["active_ticket"]
    state["reflection"]          (from previous turn, if available)
    state["root_cause_analysis"] (from previous turn, if available)

Produces:
    state["memory"]  — session context dict
"""

import logging
import time

from app.graph.state import AgentState
from app.agents.memory_agent import MemoryAgent

logger = logging.getLogger("it-agent-backend")

_agent = MemoryAgent()


def memory_node(state: AgentState) -> dict:
    logger.info("--- Memory Node ---")
    start_time = time.time()

    try:
        session_id = state.get("session_id", "")

        memory = _agent.load_memory(
            session_id=session_id,
            state=state,
        )

        logger.info(
            "Memory Node: loaded — active_issue='%s', last_ticket='%s', "
            "problem_summary='%s'",
            memory.get("active_issue", ""),
            memory.get("last_ticket", ""),
            (memory.get("last_problem_summary", "") or "")[:60],
        )

        return {"memory": memory}

    except Exception as e:
        logger.error("Memory Node: Unexpected error: %s", e, exc_info=True)
        return {
            "memory": {
                "active_issue": state.get("active_issue", ""),
                "conversation_goal": "",
                "last_problem_summary": "",
                "last_root_cause": "",
                "last_ticket": state.get("active_ticket", ""),
            }
        }

    finally:
        try:
            from app.core.metrics import AGENT_EXECUTION_TIME
            AGENT_EXECUTION_TIME.labels(agent_name="Memory Agent").observe(
                time.time() - start_time
            )
        except Exception:
            pass
