import logging

from app.agents.planner_agent import PlannerAgent
from app.graph.state import AgentState

logger = logging.getLogger("it-agent-backend")

_planner = PlannerAgent()


def planner_node(state: AgentState) -> dict:
    """
    Generates a structured plan for the current IT support issue.

    Incoming keys used: user_message, category, tool_result, approval_status
    Outgoing keys:      plan
    """
    user_message = state.get("user_message", "")
    category = state.get("category", "GENERAL")
    tool_result = state.get("tool_result") or {}
    approval_status = state.get("approval_status", "PENDING")

    logger.info(
        "Planner Node: incoming — category='%s', tool_result_keys=%s",
        category,
        list(tool_result.keys()) if isinstance(tool_result, dict) else tool_result,
    )

    try:
        # PlannerAgent.generate_plan returns a list[str] of step names
        steps = _planner.generate_plan(
            intent="IT_ISSUE",        # default; intent_node has already classified
            category=category,
            message=user_message,
            history=[],               # full history not needed for planning
            current_status="ACTIVE",
            tool_result=tool_result,
            approval_status=approval_status,
        )
        plan = {
            "goal": f"Resolve {category} issue",
            "steps": steps,
        }
    except Exception as e:
        logger.error("Planner Node: PlannerAgent.generate_plan failed: %s", e)
        plan = {
            "goal": "Resolve user issue",
            "steps": ["ASK_QUESTION"],
        }

    logger.info(
        "Planner Node: outgoing — plan=%s",
        plan,
    )

    return {"plan": plan}