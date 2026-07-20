import os
import json
import logging
from app.services.ai_provider import get_ai_provider
from dotenv import load_dotenv

logger = logging.getLogger("it-agent-backend")

# Load environment variables
load_dotenv()


# SLA database/rules tracker
sla_records = []

def calculate_sla(priority: str) -> int:
    """
    SLA Agent: Maps a priority to the correct SLA hours.
      LOW -> 24 Hours
      MEDIUM -> 8 Hours
      HIGH -> 4 Hours
      CRITICAL -> 1 Hour
    """
    priority_upper = priority.strip().upper()
    if priority_upper == "CRITICAL":
        return 1
    elif priority_upper == "HIGH":
        return 4
    elif priority_upper == "MEDIUM":
        return 8
    elif priority_upper == "LOW":
        return 24
    return 24

def calculate_priority(category: str, issue_description: str) -> str:
    """
    SLA Agent: Calculates the priority based on category and issue description using AI provider.
    Returns: "LOW" | "MEDIUM" | "HIGH" | "CRITICAL"
    """
    logger.info("SLA Agent: Calculating priority for category: %s, issue: %s", category, issue_description)

    prompt = (
        "You are an IT Support SLA Agent.\n"
        "Classify the priority of the following IT support issue.\n\n"
        "Priority Levels and Definitions:\n"
        "- LOW: Standard support requests, single-user desktop issues, access requests, general queries, software installs, printer queries.\n"
        "- MEDIUM: Standard issues impacting business processes, VPN not working, Outlook not opening, normal access issues.\n"
        "- HIGH: Serious issues impacting multiple users or critical processes, Production SAP failure, critical application down.\n"
        "- CRITICAL: Complete service outage, entire company network down, server down, security incident, data breach.\n\n"
        f"Issue Category: {category}\n"
        f"Issue Description: {issue_description}\n\n"
        "Return ONLY a valid JSON object matching this schema:\n"
        "{\n"
        '  "priority": "LOW" | "MEDIUM" | "HIGH" | "CRITICAL",\n'
        '  "reason": "short explanation of the priority calculation"\n'
        "}"
    )

    try:
        provider = get_ai_provider()
        response = provider.generate_response(prompt)
        if response:
            result = json.loads(response.strip())
            priority = result.get("priority", "").strip().upper()
            reason = result.get("reason", "").strip()
            if priority in ("LOW", "MEDIUM", "HIGH", "CRITICAL"):
                logger.info("SLA Agent: AI provider determined priority: %s (Reason: %s)", priority, reason)
                return priority
    except Exception as e:
        logger.error("SLA Agent: AI provider classification failed, using rules fallback. Error: %s", e)

    # Rule-based fallback system
    desc_lower = issue_description.lower().strip()
    cat_upper = category.upper().strip()

    # Critical rule matching
    critical_keywords = ["server down", "outage", "network down", "security breach", "hack", "compromised", "entire building"]
    if any(kw in desc_lower for kw in critical_keywords):
        return "CRITICAL"

    # High rule matching
    high_keywords = ["production sap failure", "sap failure", "production is down", "urgent", "system crash", "cannot login to sap"]
    if any(kw in desc_lower for kw in high_keywords) or cat_upper == "SAP":
        return "HIGH"

    # Medium rule matching
    if cat_upper in ("VPN", "OUTLOOK"):
        return "MEDIUM"

    # Low rule matching (Desktop issues, software, printers, etc.)
    return "LOW"

def store_sla_record(ticket_id: str, priority: str, sla_hours: int) -> dict:
    """
    Stores calculated SLA record in memory.
    """
    record = {
        "ticket_id": ticket_id,
        "priority": priority,
        "sla_hours": sla_hours
    }
    sla_records.append(record)
    return record

def get_all_sla_records() -> list[dict]:
    """
    Returns list of SLA records.
    """
    return sla_records
