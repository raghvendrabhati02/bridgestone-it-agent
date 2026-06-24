import logging
from app.graph.state import AgentState
from app.agents.conversation_agent import ConversationAgent

logger = logging.getLogger("it-agent-backend")

_FALLBACK_RESPONSE = (
    "Hello! I'm your Bridgestone IT support assistant. "
    "How can I help you today?"
)


def conversation_node(state: AgentState) -> dict:
    """
    Generates a conversational response for greetings, identity, small-talk, etc.

    Incoming keys used: user_message, session_id
    Outgoing keys:      decision, decision_response, category, tool_result
    """
    import time
    logger.info(
        "Conversation Agent Node: incoming — user_message='%s'",
        str(state.get("user_message", ""))[:80],
    )
    start_time = time.time()
    try:
        user_msg = state.get("user_message", "")
        session_id = state.get("session_id")

        # Get history
        history: list = []
        try:
            from app.services.conversation_service import get_conversation
            conv_state = get_conversation(session_id)
            history = conv_state.conversation_history if conv_state else []
        except Exception as e:
            logger.warning("Conversation Agent Node: Could not fetch history: %s", e)

        # Classify intent (already done in router but we need it for response generation)
        intent = "GREETING"
        try:
            agent = ConversationAgent()
            classification = agent.classify_message(user_msg, history)
            intent = classification.get("intent", "GREETING")
        except Exception as e:
            logger.warning("Conversation Agent Node: classify_message failed: %s", e)

        # Generate the natural conversation response
        response_text = _FALLBACK_RESPONSE
        try:
            if not isinstance(agent, ConversationAgent):
                agent = ConversationAgent()
            response_text = agent.generate_conversational_response(user_msg, history, intent)
            if not response_text or not isinstance(response_text, str):
                response_text = _FALLBACK_RESPONSE
        except Exception as e:
            logger.warning("Conversation Agent Node: generate_conversational_response failed: %s. Using fallback.", e)
            response_text = _FALLBACK_RESPONSE

        logger.info(
            "Conversation Agent Node: outgoing — decision='CHAT', response='%s'",
            response_text[:80],
        )

        # Write trace log in audit database
        try:
            from app.services.audit_service import log_agent_trace
            log_agent_trace(
                session_id=session_id,
                agent_name="Conversation Agent",
                output={"intent": intent, "response": response_text}
            )
        except Exception as e:
            logger.error("Conversation Agent Node: Failed to log trace: %s", e)

        return {
            "decision": "CHAT",
            "decision_response": response_text,
            "category": "GENERAL",
            "tool_result": {},  # Clear any tool results to ensure no tool card renders in UI
        }

    except Exception as e:
        logger.error("Conversation Agent Node: Unhandled exception: %s", e, exc_info=True)
        return {
            "decision": "CHAT",
            "decision_response": _FALLBACK_RESPONSE,
            "category": "GENERAL",
            "tool_result": {},
        }

    finally:
        try:
            from app.core.metrics import AGENT_EXECUTION_TIME
            AGENT_EXECUTION_TIME.labels(agent_name="Conversation Agent").observe(time.time() - start_time)
        except Exception:
            pass
