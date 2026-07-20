import os
import json
import logging
from dotenv import load_dotenv

logger = logging.getLogger("it-agent-backend")

# Load environment variables
load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    env_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))
    load_dotenv(dotenv_path=env_path)
    api_key = os.getenv("GEMINI_API_KEY")


from app.agents.conversation_agent import ConversationAgent
from app.agents.planner_agent import PlannerAgent
from app.agents.reasoning_agent import ReasoningAgent
from app.agents.response_agent import ResponseAgent

# Instantiate singletons for the agents
conversation_agent = ConversationAgent()
planner_agent = PlannerAgent()
reasoning_agent = ReasoningAgent()
response_agent = ResponseAgent()

def analyze_conversation(
    category: str,
    conversation_history: list[dict],
    latest_user_message: str,
    knowledge_context: str,
    tool_result: dict = None,
    session_id: str = None,
    reflection: dict = None,  # Pre-computed from reflection_node in LangGraph
) -> dict:
    """
    Analyzes the conversation state to determine the next logical action.
    Utilizes the multi-agent chain to classifiy user intent, generate plans,
    reason over diagnostics, and compose friendly conversational replies.
    Returns a dict with:
      "action": "ASK_MORE_INFO" | "RECOMMEND_ACTION" | "RESOLVED" | "CREATE_TICKET"
      "reason": str
      "response": str (optional)
      "approval_required": bool
      "recommended_action": str
      "category": str (optional category update)
    """
    logger.info("=== Multi-Agent Conversational Layer Debug ===")
    logger.info("Category: %s", category)
    logger.info("Latest User Message: %s", latest_user_message)
    logger.info("Tool Result: %s", json.dumps(tool_result, indent=2) if tool_result else "None")

    # Determine session status if possible
    current_status = "ACTIVE"
    if session_id:
        try:
            from app.services.conversation_service import get_conversation
            conv_state = get_conversation(session_id)
            if conv_state:
                current_status = conv_state.status
        except Exception as e:
            logger.warning("Decision Service: Failed to retrieve session status: %s", e)

    # 1. Conversation Agent: Classify intent and category
    classification = conversation_agent.classify_message(
        latest_user_message,
        conversation_history,
        current_category=category,
        current_status=current_status
    )
    intent = classification.get("intent", "IT_ISSUE")
    detected_category = classification.get("category", category)
    logger.info("ConversationAgent Result: Intent=%s, Category=%s", intent, detected_category)

    # 2. Reasoning Agent: Summarize findings from diagnostics
    # ── Use pre-computed reflection from the LangGraph reflection_node if available ──
    if reflection and reflection.get("findings"):
        reasoning = reflection  # Already has: findings, observations, hypotheses, confidence, etc.
        logger.info(
            "DecisionService: Using pre-computed reflection from LangGraph node. "
            "Confidence=%.2f, Observations=%d",
            reasoning.get("confidence", 0.0),
            len(reasoning.get("observations", [])),
        )
    else:
        # Fallback: run reasoning inline (e.g. direct service calls without LangGraph)
        reasoning = reasoning_agent.reason_over_state(
            category,
            tool_result,
            conversation_history,
        )
        logger.info(
            "DecisionService: Inline ReasoningAgent used. Findings='%s'",
            reasoning.get("findings", "")[:80],
        )
    logger.info("ReasoningAgent Result: Findings='%s', ApprovalRequired=%s", reasoning.get("findings"), reasoning.get("approval_needed"))

    # 3. Planner Agent: Determine planned next actions
    plan = planner_agent.generate_plan(
        intent,
        detected_category,
        latest_user_message,
        conversation_history,
        current_status,
        tool_result=tool_result,
        approval_status="PENDING"
    )
    logger.info("PlannerAgent Result: Generated Plan=%s", plan)

    # 4. Response Agent: Generate a conversational, friendly natural language response
    response_text = response_agent.generate_response(
        latest_user_message,
        conversation_history,
        plan,
        reasoning,
        detected_category,
        knowledge_context=knowledge_context
    )

    # 5. Map plan action to LangGraph action state
    plan_action = plan[0] if plan else "ASK_QUESTION"
    action_mapping = {
        "ASK_QUESTION": "ASK_MORE_INFO",
        "RUN_TOOL": "ASK_MORE_INFO",
        "CREATE_TICKET": "CREATE_TICKET",
        "REQUEST_APPROVAL": "RECOMMEND_ACTION",
        "EXECUTE_ACTION": "EXECUTE_ACTION",
        "CANCEL_WORKFLOW": "REJECTED",
        "RESOLVE_ISSUE": "RESOLVED"
    }
    mapped_action = action_mapping.get(plan_action, "ASK_MORE_INFO")

    action_result = {
        "action": mapped_action,
        "reason": reasoning.get("rationale", "Multi-agent chain decided action."),
        "response": response_text,
        "approval_required": reasoning.get("approval_needed", False) or plan_action == "REQUEST_APPROVAL",
        "recommended_action": reasoning.get("recommended_action", ""),
        "category": detected_category
    }
    logger.info("Final Multi-Agent Decision: %s (Response: '%s')", action_result["action"], response_text[:100])
    return action_result

