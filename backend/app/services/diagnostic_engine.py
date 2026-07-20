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
    # ── Connectivity ──────────────────────────────────────────────────────────
    "VPN": [
        ("network_type", "Are you connecting from the office network or from home/remote?"),
        ("error_code", "What error message or code is the VPN client showing?"),
        ("client_opens", "Does the VPN client (GlobalProtect/AnyConnect) open at all?"),
        ("internet_works", "Can you browse the internet without VPN?"),
    ],
    "WIFI": [
        ("all_sites", "Is it all websites/apps that are affected, or only specific ones?"),
        ("other_devices", "Are other devices on the same Wi-Fi network also affected?"),
        ("wired_works", "Does a wired (Ethernet) connection work on the same device?"),
        ("adapter_status", "What does Windows show for the Wi-Fi adapter — Connected, Limited, or No Internet?"),
    ],
    "NETWORK": [
        ("connection_type", "Are you connected via Ethernet or Wi-Fi?"),
        ("all_apps", "Is the issue affecting all applications, or only specific ones?"),
        ("recently_changed", "Did this start after any recent change — move, update, or new hardware?"),
    ],
    # ── Microsoft 365 ─────────────────────────────────────────────────────────
    "OUTLOOK": [
        ("outlook_opens", "Does Outlook open at all, or does it crash immediately?"),
        ("login_related", "Is Outlook prompting for your password repeatedly?"),
        ("emails_syncing", "Is Outlook showing emails but not syncing, or is the inbox completely empty?"),
        ("web_works", "Does Outlook Web (outlook.office.com) work in a browser?"),
    ],
    "TEAMS": [
        ("specific_issue", "Is the issue with audio/video, sign-in, calls dropping, or something else?"),
        ("web_works", "Does Teams work in a web browser (teams.microsoft.com)?"),
        ("other_apps", "Are other Microsoft 365 apps (Outlook, OneDrive) also affected?"),
    ],
    "ONEDRIVE": [
        ("sync_status", "What status does OneDrive show — Sync Paused, Processing Changes, or an error message?"),
        ("error_code", "Is there a specific error code or message shown?"),
        ("which_files", "Is the sync problem affecting all files or just a specific folder?"),
    ],
    "OFFICE": [
        ("which_app", "Which Office application is affected — Word, Excel, PowerPoint, or all of them?"),
        ("error_type", "Is this an activation error, a crash, or a specific feature not working?"),
        ("recently_updated", "Did this start after a recent Office update or reinstall?"),
    ],
    # ── Account & Authentication ───────────────────────────────────────────────
    "PASSWORD_RESET": [
        ("which_account", "Which system's password do you need to reset — Windows, M365, SAP, or VPN?"),
        ("account_locked", "Is the account showing as locked, or has the password expired?"),
        ("mfa_failure", "Is there an MFA (multi-factor authentication) prompt that is also failing?"),
    ],
    "LOGIN": [
        ("which_system", "Which system are you unable to log in to — Windows, M365, SAP, or a web application?"),
        ("error_message", "What is the exact error message shown on the login screen?"),
        ("after_change", "Did this start after a recent password change or account update?"),
    ],
    # ── Printing ──────────────────────────────────────────────────────────────
    "PRINTER": [
        ("printer_status", "Does Windows show the printer as Online or Offline?"),
        ("queue_stuck", "Are there print jobs queued but nothing printing?"),
        ("others_can_print", "Can other users on the same printer print successfully?"),
    ],
    # ── Software & Installation ───────────────────────────────────────────────
    "SOFTWARE_INSTALLATION": [
        ("software_name", "What is the exact name and version of the software you need to install?"),
    ],
    "ADOBE": [
        ("which_product", "Which Adobe product is having issues — Acrobat, Reader, or Creative Cloud?"),
        ("error_type", "Is it a license/activation error, a crash, or a specific feature not working?"),
        ("cc_signed_in", "Is the Creative Cloud desktop app installed and are you signed in?"),
    ],
    "CITRIX": [
        ("reaches_login", "Can you reach the Citrix login page in a browser?"),
        ("error_message", "What is the exact error message you see?"),
        ("on_vpn", "Are you connecting from outside the office — is VPN required?"),
    ],
    # ── Business Applications ─────────────────────────────────────────────────
    "SAP": [
        ("sap_module", "Which SAP module are you working in — FI, MM, SD, or another?"),
        ("transaction_code", "What is the transaction code where the error occurs?"),
        ("error_type", "Is this an access/authorization error or a functional/data error?"),
    ],
    # ── Security & System ─────────────────────────────────────────────────────
    "BITLOCKER": [
        ("locked_out", "Are you locked out of the drive and needing the recovery key?"),
        ("after_update", "Did the BitLocker prompt appear after a recent Windows Update?"),
        ("device_managed", "Is this device managed by Intune or joined to the company domain?"),
    ],
    "DRIVERS": [
        ("device_affected", "Which device is not working — GPU, audio, NIC, USB, or another?"),
        ("device_manager", "Does Device Manager show a yellow exclamation mark or an error code?"),
        ("after_update", "Did this start after a recent Windows Update?"),
    ],
    # ── Performance ───────────────────────────────────────────────────────────
    "PERFORMANCE": [
        ("when_slow", "Is the slowness at startup, when opening a specific app, or all the time?"),
        ("task_manager", "Can you open Task Manager and check — is CPU, Memory, or Disk at very high usage?"),
        ("restart_tried", "Has the device been restarted recently, or is it running for several days?"),
    ],
    # ── Operating System ──────────────────────────────────────────────────────
    "WINDOWS": [
        ("symptom", "What is the specific symptom — blue screen (BSOD), startup failure, update error, or app crash?"),
        ("error_code", "Is there a specific error code or stop code shown?"),
        ("after_update", "Did this start after a Windows Update?"),
    ],
    # ── Hardware ──────────────────────────────────────────────────────────────
    "HARDWARE": [
        ("which_device", "Which hardware is affected — keyboard, monitor, docking station, webcam, or something else?"),
        ("detected", "Is the device detected by Windows at all (visible in Device Manager)?"),
        ("physical_damage", "Is there any visible physical damage, or is it a connection/software issue?"),
    ],
    # ── Browser ───────────────────────────────────────────────────────────────
    "BROWSER": [
        ("which_browser", "Which browser are you using — Chrome, Edge, Firefox, or Internet Explorer?"),
        ("all_sites", "Is the issue affecting all websites or just specific ones?"),
        ("incognito", "Does the problem happen in Incognito/Private mode as well?"),
    ],
    # ── Legacy / Other ────────────────────────────────────────────────────────
    "SHARED_MAILBOX": [
        ("access_denied", "Are you getting an 'Access Denied' error for the shared mailbox?"),
        ("mailbox_missing", "Is the shared mailbox not appearing in Outlook at all?"),
        ("send_as_issue", "Are you unable to send mail as or on behalf of the shared mailbox?"),
    ],
    "DEVICE_HEALTH": [
        ("device_issue", "Is your device running slow, crashing, or showing errors?"),
    ],
    "IT_ASSET_ALLOCATION": [
        ("asset_action", "Are you requesting a new device or returning an existing one?"),
    ],
    "GUEST_WIFI": [
        ("guest_device", "Are you trying to connect a guest or personal device to the Wi-Fi?"),
    ],
    "NETWORK_LEGACY": [
        ("network_connection", "Are you connected via Ethernet or Wi-Fi?"),
    ],
}

# Map legacy NETWORK to the right key (NETWORK is already defined above with expanded questions)
DIAGNOSTIC_QUESTIONS["NETWORK"] = [
    ("connection_type", "Are you connected via Ethernet or Wi-Fi?"),
    ("all_apps", "Is the issue affecting all applications, or only specific ones?"),
    ("recently_changed", "Did this start after any recent change — move, update, or new hardware?"),
]


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
