import logging
from app.graph.state import AgentState
from app.agents.conversation_agent import ConversationAgent

logger = logging.getLogger("it-agent-backend")


def router_node(state: AgentState) -> dict:
    """
    Classifies the user message intent and routes to conversation or troubleshooting.

    Incoming keys used: user_message, session_id
    Outgoing keys:      decision, category
    """
    import time
    logger.info(
        "Router Node: incoming — user_message='%s'",
        str(state.get("user_message", ""))[:80],
    )
    start_time = time.time()
    try:
        user_msg = state.get("user_message", "")
        session_id = state.get("session_id")

        # Get conversation history for context if available
        history: list = []
        try:
            from app.services.conversation_service import get_conversation
            conv_state = get_conversation(session_id)
            history = conv_state.conversation_history if conv_state else []
        except Exception as e:
            logger.warning("Router Node: Could not fetch conversation history: %s", e)

        # Classify the message using ConversationAgent
        try:
            agent = ConversationAgent()
            classification = agent.classify_message(user_msg, history)
            intent = classification.get("intent", "IT_ISSUE")
        except Exception as e:
            logger.warning("Router Node: ConversationAgent classification failed: %s. Defaulting to IT_ISSUE.", e)
            intent = "IT_ISSUE"

        logger.info("Router Node: Classified user message intent as '%s'", intent)

        conversational_intents = {"GREETING", "IDENTITY", "SMALL_TALK", "CAPABILITY", "THANKS", "GOODBYE"}
        if intent in conversational_intents:
            logger.info("Router Node: Detected conversational intent. Routing to conversation node.")
            out = {"decision": "CHAT", "category": "GENERAL"}
        else:
            logger.info("Router Node: Troubleshooting intent. Routing to context_router → standard flow.")
            out = {"decision": "TROUBLESHOOT"}

        logger.info("Router Node: outgoing — decision='%s'", out.get("decision"))
        return out

    except Exception as e:
        logger.error("Router Node: Unhandled exception: %s. Defaulting to CHAT fallback.", e, exc_info=True)
        return {"decision": "CHAT", "category": "GENERAL"}

    finally:
        try:
            from app.core.metrics import AGENT_EXECUTION_TIME
            AGENT_EXECUTION_TIME.labels(agent_name="Router Agent").observe(time.time() - start_time)
        except Exception:
            pass
