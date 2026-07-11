"""
diagnostic_engine.py
─────────────────────────────────────────────────────────────────────────────
Owns all diagnostic/clarification questions and answers extraction.

Design contracts:
  • Deterministic and rules-based (no Gemini calls).
  • Decides if confidence is high (bypass questions) or low (ask one question).
  • Extract answers from natural replies.
  • Prevents Gemini from generating troubleshooting steps or questions.
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger("it-agent-backend")

DIAGNOSTIC_QUESTIONS: Dict[str, List[Tuple[str, str]]] = {
    "VPN": [
        ("network_type", "Are you connected to office WiFi or home WiFi?"),
        ("error_code", "What error code do you see?"),
        ("client_opens", "Does GlobalProtect open?"),
        ("internet_works", "Can you browse the internet?"),
        ("vpn_only", "Is this affecting only VPN?"),
    ],
    "PRINTER": [
        ("printer_powered", "Is the printer powered on?"),
        ("printer_status", "Does Windows show Online or Offline?"),
        ("others_can_print", "Can anyone else print?"),
    ],
    "OUTLOOK": [
        ("outlook_opens", "Does Outlook open?"),
        ("login_related", "Is the issue login related?"),
        ("emails_syncing", "Are emails syncing?"),
    ],
    "PASSWORD_RESET": [
        ("forgot_password", "Forgot password?"),
        ("account_locked", "Account locked?"),
        ("mfa_failure", "MFA failure?"),
    ],
    "SHARED_MAILBOX": [
        ("access_denied", "Access denied?"),
        ("mailbox_missing", "Mailbox missing?"),
        ("send_as_issue", "Send As issue?"),
    ],
    "SOFTWARE_INSTALLATION": [
        ("software_name", "What software would you like to install?"),
    ],
    "SAP": [
        ("sap_error_type", "Are you getting an access error or a transaction error?"),
    ],
    "DEVICE_HEALTH": [
        ("device_issue", "Is your device running slow or crashing?"),
    ],
    "IT_ASSET_ALLOCATION": [
        ("asset_action", "Are you requesting a new device or returning one?"),
    ],
    "GUEST_WIFI": [
        ("guest_device", "Are you trying to connect a guest device?"),
    ],
    "NETWORK": [
        ("network_connection", "Are you connected via Ethernet or Wi-Fi?"),
    ],
}


def get_next_question(category: str, answers: Dict[str, str]) -> Optional[str]:
    """Return the next diagnostic question for the category whose field is not yet answered."""
    category_upper = category.strip().upper()
    questions = DIAGNOSTIC_QUESTIONS.get(category_upper, [])
    for field_name, question_text in questions:
        if field_name not in answers:
            return question_text
    return None


def extract_answers(category: str, message: str, last_question: str) -> Dict[str, str]:
    """Parse the reply and extract answer for the field mapping to the last question."""
    category_upper = category.strip().upper()
    questions = DIAGNOSTIC_QUESTIONS.get(category_upper, [])
    msg = message.lower().strip()

    field_name = None
    for f, q in questions:
        if q.lower() in last_question.lower() or last_question.lower() in q.lower():
            field_name = f
            break

    if not field_name:
        return {}

    value = msg
    # Field-specific extraction
    if field_name == "network_type":
        if "home" in msg:
            value = "home"
        elif "office" in msg:
            value = "office"
        elif "wifi" in msg:
            value = "wifi"
    elif field_name == "printer_status":
        if "offline" in msg:
            value = "offline"
        elif "online" in msg:
            value = "online"
    # Boolean fields
    elif any(
        x in field_name
        for x in [
            "opens",
            "works",
            "only",
            "powered",
            "can_print",
            "syncing",
            "related",
            "forgot",
            "locked",
            "failure",
            "denied",
            "missing",
            "issue",
            "guest",
        ]
    ):
        if any(w in msg for w in ["yes", "yeah", "yep", "true", "correct", "does", "is"]):
            value = "yes"
        elif any(w in msg for w in ["no", "nope", "not", "false", "broken", "doesn't", "isn't"]):
            value = "no"

    logger.info("DiagnosticEngine: Extracted %s = %s", field_name, value)
    return {field_name: value}


def is_confidence_high(category: str, message: str, answers: Dict[str, str]) -> bool:
    """
    Decide if confidence is high enough to load KB directly.
    Confidence is high if:
      - Category has no KB article.
      - At least one diagnostic question is answered.
      - The message is detailed (contains more than 1 word and is not just the category name).
    """
    category_upper = category.strip().upper()

    from app.services.knowledge_service import search_by_category
    if not search_by_category(category_upper):
        return True

    if len(answers) >= 1:
        return True

    msg = message.lower().strip()
    if len(msg.split()) >= 2 and msg != category_upper.lower():
        return True

    return False
