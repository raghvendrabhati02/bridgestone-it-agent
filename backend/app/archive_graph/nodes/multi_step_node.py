import logging
import time
from app.graph.state import AgentState
from app.agents.multi_step_planner_agent import MultiStepPlannerAgent
from app.agents.hypothesis_tracker_agent import HypothesisTrackerAgent
from app.agents.engineer_summary_agent import EngineerSummaryAgent

logger = logging.getLogger("it-agent-backend")

_planner_agent = MultiStepPlannerAgent()
_tracker_agent = HypothesisTrackerAgent()
_summary_agent = EngineerSummaryAgent()

def multi_step_node(state: AgentState) -> dict:
    """
    Multi-Step node that orchestrates hypothesis updates, loop control, and final diagnostic summary generation.
    Runs after the tool execution node.
    """
    logger.info("--- Multi-Step Node ---")
    start_time = time.time()

    try:
        category = state.get("category", "GENERAL")
        user_message = state.get("user_message", "")
        
        # 1. Update Tool Chain
        tool_chain = list(state.get("tool_chain") or [])
        latest_tool_result = state.get("tool_result")
        
        if latest_tool_result and isinstance(latest_tool_result, dict):
            # Check if this tool run is already in the chain to avoid duplicates
            already_exists = any(
                t.get("tool_name") == latest_tool_result.get("tool_name") 
                for t in tool_chain
            )
            if not already_exists:
                tool_chain.append(latest_tool_result)
                logger.info("Multi-Step Node: Added tool result for '%s' to tool chain.", latest_tool_result.get("tool_name"))

        # 2. Update Hypothesis Tracker
        current_hypotheses = list(state.get("hypothesis_tracker") or [])
        updated_hypotheses = _tracker_agent.update_hypotheses(
            category=category,
            tool_chain=tool_chain,
            current_hypotheses=current_hypotheses,
            user_message=user_message
        )

        # 3. Increment Iterations
        iterations = state.get("troubleshooting_iterations", 0) + 1
        logger.info("Multi-Step Node: Troubleshooting iteration %d / 3", iterations)

        # 4. Decide next step
        next_tool = None
        complete = False

        if iterations >= 3:
            logger.info("Multi-Step Node: Max iterations (3) reached. Stopping loop.")
            complete = True
        else:
            next_tool = _planner_agent.plan_next_step(
                category=category,
                tool_chain=tool_chain,
                hypotheses=updated_hypotheses,
                user_message=user_message
            )
            if next_tool is None:
                logger.info("Multi-Step Node: Planner decided to stop troubleshooting loop.")
                complete = True
            else:
                logger.info("Multi-Step Node: Planner requested next tool execution for category: %s", next_tool)

        # 5. Generate Engineer Summary if complete
        engineer_summary = state.get("engineer_summary")
        if complete:
            engineer_summary = _summary_agent.generate_summary(
                category=category,
                tool_chain=tool_chain,
                hypotheses=updated_hypotheses,
                user_message=user_message
            )
            logger.info("Multi-Step Node: Generated final engineer summary.")

        # Write trace record
        try:
            from app.services.audit_service import log_agent_trace
            log_agent_trace(
                session_id=state.get("session_id"),
                agent_name="Multi-Step Diagnostic Agent",
                output={
                    "tool_chain_length": len(tool_chain),
                    "hypotheses_count": len(updated_hypotheses),
                    "iterations": iterations,
                    "complete": complete,
                    "next_tool": next_tool
                }
            )
        except Exception as e:
            logger.error("Multi-Step Node: Failed to log trace: %s", e)

        return {
            "tool_chain": tool_chain,
            "hypothesis_tracker": updated_hypotheses,
            "troubleshooting_iterations": iterations,
            "troubleshooting_complete": complete,
            "next_tool": next_tool,
            "engineer_summary": engineer_summary
        }
    finally:
        try:
            from app.core.metrics import AGENT_EXECUTION_TIME
            AGENT_EXECUTION_TIME.labels(agent_name="Multi-Step Node").observe(time.time() - start_time)
        except Exception:
            pass
