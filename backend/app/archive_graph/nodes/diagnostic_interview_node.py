import os
import json
import logging
from app.services.ai_provider import get_ai_provider
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

    # If category is GENERAL, conversation, greeting, ticket request, or ticket status, bypass interview
    msg_lower = user_message.lower()
    ticket_keywords = [
        "create ticket", "create a ticket", "create support ticket", "create a support ticket",
        "raise ticket", "raise a ticket", "open incident", "open an incident", "escalate", "support ticket",
        "open a ticket", "open support ticket", "open a support ticket"
    ]
    is_ticket_req = any(kw in msg_lower for kw in ticket_keywords)

    is_approval = (state.get("status") == "AWAITING_APPROVAL" or 
                   (state.get("approval_status") or "PENDING").upper().strip() in ("APPROVED", "REJECTED"))

    if category in ("GENERAL", "CHAT", "TICKET_STATUS", "SERVICE_REQUEST") or state.get("route") in ("ticket_lifecycle", "ticket_status", "service_request") or is_ticket_req or is_approval:
        logger.info("Diagnostic Interview: Bypassing interview for category: %s (explicit ticket request=%s, approval=%s)", category, is_ticket_req, is_approval)
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
    acknowledgments = {
        "VPN": "I understand how frustrating VPN connection issues can be, especially when you need to access remote resources. Let's get that checked out! I'll run a diagnostic on our gateway and inspect your account access configuration. While I do that, could you help me with a few details?",
        "OUTLOOK": "Outlook sync or launch issues can really slow down your day, so let's resolve this. I will verify your Exchange connectivity and check your mailbox status on our mail servers. In the meantime, could you clarify a couple of points for me?",
        "NETWORK": "I'm sorry to hear you're experiencing connectivity trouble; a slow or dropping network is always a hassle. I'll run some diagnostics to evaluate your local network latency and packet loss. To help me narrow it down, could you answer these questions?",
        "SOFTWARE_INSTALLATION": "Getting software installed should be a quick process. I will check our approved catalog listing and verify your local administrative privileges for this installation. While I run that check, could you share a bit more information?",
        "SAP": "SAP errors can definitely block your workflow. I will perform a quick check on the SAP Basis server status and database connectivity. To help troubleshoot, could you let me know what error you're seeing?",
        "PASSWORD_RESET": "I can certainly help you get back into your account. I'll inspect Active Directory to check for any lockouts or credential expiration. To make sure I take the right action, could you let me know a few details?",
        "PRINTER": "Printer issues are always a pain. I will query the print spooler status and verify if the printer queue is online. While I run that check, could you tell me what's happening with the print jobs?",
        "HARDWARE": "I'm sorry you're dealing with hardware trouble. Hardware issues can be tricky, so let's look into this. I'll verify if there are any known hardware advisories or replacement options available. Could you describe the situation a bit more?",
    }
    
    question_blocks = {
        "VPN": (
            "1. Are you seeing a specific error or symptom?\n"
            "   [A] Connection Timeout (Error 809 / 868)\n"
            "   [B] Authentication Denied / locked account\n"
            "   [C] Cisco AnyConnect client fails to open\n"
            "   [D] Other / Not sure\n"
            "2. Are you connected via Wi-Fi or a wired ethernet cable?"
        ),
        "OUTLOOK": (
            "1. Is Outlook failing to open entirely, or is it open but refusing to send/receive emails?\n"
            "2. Are you accessing email on the Outlook desktop app, the web version (OWA), or mobile?"
        ),
        "NETWORK": (
            "1. Are you able to access any external websites (like google.com), or is all internet access down?\n"
            "2. Are you experiencing high packet loss or extremely slow browsing speeds?"
        ),
        "SOFTWARE_INSTALLATION": (
            "1. What is the exact name and version of the software you are trying to install?\n"
            "2. Did you see a specific error code, such as a 'Permission Denied' or 'Administrator Required' message?"
        ),
        "SAP": (
            "1. Which SAP module or transaction code (T-code) are you trying to access?\n"
            "2. What is the exact error code or message displayed on your screen?"
        ),
        "PASSWORD_RESET": (
            "1. Is this for your primary Windows domain/laptop login, or a specific application like SAP?\n"
            "2. Are you currently locked out of your account, or is your password about to expire?"
        ),
        "PRINTER": (
            "1. Is the printer showing as 'Offline' in Windows, or are print jobs silently stuck in the queue?\n"
            "2. What is the printer model or office location name?"
        ),
        "HARDWARE": (
            "1. Could you describe the problem? Is there visible physical damage, or is a component (display, keyboard, power) failing?\n"
            "2. Are you working from a corporate office, or remote/home?"
        ),
    }

    category_key = category.upper().strip()
    ack = acknowledgments.get(category_key, f"I'm sorry you're running into issues with your {category_key.lower().replace('_', ' ')}. Let's look into this and check the relevant systems. While I check that, could you provide a bit more detail?")
    q_block = question_blocks.get(category_key, "1. What exact symptoms or error messages are you seeing on your screen?\n2. When did this issue first start happening?")
    
    question_text = f"{ack}\n\n{q_block}"
    questions = get_category_questions(category)
    logger.info("Diagnostic Interview: Context insufficient. Asking questions: %s", questions)

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
        provider = get_ai_provider()
        response = provider.generate_response(prompt)
        if response:
            result = json.loads(response.strip())
            return bool(result.get("sufficient", False))
    except Exception as e:
        logger.warning("Diagnostic Interview: LLM sufficiency check failed (%s). Using rules.", e)

    # Rule-based fallback checks
    msg_lower = message.lower()
    cat_key = category.upper().strip()
    if cat_key == "VPN":
        # Check if they specified details
        return any(kw in msg_lower for kw in ("timeout", "auth", "credential", "lock", "wifi", "ethernet", "password", "reset", "disabled"))
    elif cat_key == "OUTLOOK":
        return any(kw in msg_lower for kw in ("open", "sync", "desktop", "web", "mobile", "cache", "server", "credentials"))
    elif cat_key == "NETWORK":
        return any(kw in msg_lower for kw in ("google", "internet", "packet", "loss", "slow", "ping", "website"))
    elif cat_key == "SOFTWARE_INSTALLATION":
        return any(kw in msg_lower for kw in ("chrome", "firefox", "outlook", "sap", "vpn", "zoom", "teams", "error", "admin"))
    elif cat_key == "HARDWARE":
        return any(kw in msg_lower for kw in ("screen", "monitor", "display", "keyboard", "mouse", "hinge", "laptop", "power", "charger", "broken", "battery", "damage"))
    elif cat_key == "PASSWORD_RESET":
        return any(kw in msg_lower for kw in ("unlock", "domain", "active directory", "ad", "locked out", "expired", "change", "reset", "forgot"))
    elif cat_key == "SAP":
        return any(kw in msg_lower for kw in ("fico", "basis", "t-code", "tcode", "login", "role", "access", "production"))
    elif cat_key == "PRINTER":
        return any(kw in msg_lower for kw in ("spooler", "queue", "offline", "jam", "toner", "paper", "print job"))
    
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
