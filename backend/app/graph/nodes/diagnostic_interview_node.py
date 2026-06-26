import os
import json
import logging
import google.generativeai as genai
from app.graph.state import AgentState

logger = logging.getLogger("it-agent-backend")

def diagnostic_interview_node(state: AgentState) -> dict:
    """
    Diagnostic Interview Node.
    Gathers initial context before running planner or tools.
    Short-circuits to END by setting decision_response if questions are needed.
    """
    logger.info("--- Diagnostic Interview Node ---")
    
    category = state.get("category", "GENERAL").upper().strip()
    user_message = state.get("user_message", "")
    interview_state = state.get("diagnostic_interview")

    # If category is GENERAL, conversation, or greeting/ticket status/etc, bypass interview
    if category in ("GENERAL", "CHAT", "TICKET_STATUS", "SERVICE_REQUEST") or state.get("route") in ("ticket_lifecycle", "ticket_status", "service_request"):
        logger.info("Diagnostic Interview: Bypassing interview for category: %s", category)
        return {}

    # Check if we already did or skipped the interview
    if interview_state and isinstance(interview_state, dict):
        status = interview_state.get("status")
        if status == "pending":
            # User has replied to our interview questions!
            # Record their answers and mark as completed
            logger.info("Diagnostic Interview: User replied to interview questions. Recording response and proceeding.")
            updated_state = {
                "status": "completed",
                "questions": interview_state.get("questions", []),
                "answers": [user_message]
            }
            return {"diagnostic_interview": updated_state, "decision_response": ""}
        elif status in ("completed", "skipped"):
            logger.info("Diagnostic Interview: Interview already completed/skipped. Proceeding.")
            return {}

    # First turn of troubleshooting: evaluate context sufficiency
    is_sufficient = check_context_sufficiency(category, user_message)

    if is_sufficient:
        logger.info("Diagnostic Interview: Context is sufficient. Skipping interview.")
        return {
            "diagnostic_interview": {
                "status": "skipped",
                "questions": [],
                "answers": []
            }
        }

    # Context is insufficient: generate and ask questions
    questions = get_category_questions(category)
    logger.info("Diagnostic Interview: Context insufficient. Asking questions: %s", questions)
    
    question_text = (
        f"To help you troubleshoot your {category.title()} issue, could you please provide a bit more detail?\n\n"
        + "\n".join(f"- {q}" for q in questions)
    )

    return {
        "diagnostic_interview": {
            "status": "pending",
            "questions": questions,
            "answers": []
        },
        "decision": "ASK_MORE_INFO",
        "decision_response": question_text
    }

def check_context_sufficiency(category: str, message: str) -> bool:
    """
    Checks if the user's message has enough diagnostic context to skip the interview.
    """
    api_key = os.getenv("GEMINI_API_KEY")
    if api_key:
        try:
            prompt = f"""You are an IT support assistant for Bridgestone.
Analyze if the user's message has enough details to diagnose a {category} issue.
For example, does it mention the error message, symptom type (e.g. timeout vs auth), or platform (desktop/web)?

User Message: "{message}"

Return a JSON object with a single boolean key "sufficient".
JSON:
{{
  "sufficient": true
}}
"""
            model = genai.GenerativeModel("gemini-2.5-flash-lite")
            response = model.generate_content(
                prompt,
                generation_config={"response_mime_type": "application/json"},
                request_options={"timeout": 6.0}
            )
            if response and response.text:
                result = json.loads(response.text.strip())
                return bool(result.get("sufficient", False))
        except Exception as e:
            logger.warning("Diagnostic Interview: LLM sufficiency check failed (%s). Using rules.", e)

    # Rule-based fallback checks
    msg_lower = message.lower()
    if category == "VPN":
        # Check if they specified details
        return any(kw in msg_lower for kw in ("timeout", "auth", "credential", "lock", "wifi", "ethernet", "password", "reset"))
    elif category == "OUTLOOK":
        return any(kw in msg_lower for kw in ("open", "sync", "desktop", "web", "mobile", "cache", "server", "credentials"))
    elif category == "NETWORK":
        return any(kw in msg_lower for kw in ("google", "internet", "packet", "loss", "slow", "ping", "website"))
    elif category == "SOFTWARE_INSTALLATION":
        return any(kw in msg_lower for kw in ("chrome", "firefox", "outlook", "sap", "vpn", "zoom", "teams", "error", "admin"))
    
    return False

def get_category_questions(category: str) -> list[str]:
    """
    Returns standard questions for a category.
    """
    questions = {
        "VPN": [
            "Are you getting a connection timeout or an authentication/credentials error?",
            "Are you connected via Wi-Fi or a wired ethernet cable?"
        ],
        "OUTLOOK": [
            "Is Outlook failing to open entirely, or is it open but refusing to send/receive emails?",
            "Are you using the Outlook desktop app, Outlook web app, or mobile app?"
        ],
        "NETWORK": [
            "Are you able to access any external websites (like google.com)?",
            "Are you experiencing high packet loss or extremely slow browsing speeds?"
        ],
        "SOFTWARE_INSTALLATION": [
            "What is the exact name of the software you are trying to install?",
            "Did you see any error code or message during the installation failure?"
        ],
        "SAP": [
            "Which SAP module are you trying to access?",
            "What is the exact error code or message displayed on the screen?"
        ]
    }
    return questions.get(category.upper().strip(), [
        "Could you describe the exact error message or symptom you are seeing?",
        "When did this issue start happening?"
    ])
