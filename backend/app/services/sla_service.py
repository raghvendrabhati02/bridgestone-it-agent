import os
import json
import logging
import google.generativeai as genai
from dotenv import load_dotenv

logger = logging.getLogger("it-agent-backend")

# Load environment variables
load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    env_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))
    load_dotenv(dotenv_path=env_path)
    api_key = os.getenv("GEMINI_API_KEY")

if api_key:
    genai.configure(api_key=api_key)

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
    SLA Agent: Calculates the priority based on category and issue description using Gemini.
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

    if api_key:
        try:
            model = genai.GenerativeModel("gemini-2.5-flash-lite")
            response = model.generate_content(
                prompt,
                generation_config={"response_mime_type": "application/json"},
                request_options={"timeout": 15.0}
            )
            if response and response.text:
                result = json.loads(response.text.strip())
                priority = result.get("priority", "").strip().upper()
                reason = result.get("reason", "").strip()
                if priority in ("LOW", "MEDIUM", "HIGH", "CRITICAL"):
                    logger.info("SLA Agent: Gemini determined priority: %s (Reason: %s)", priority, reason)
                    return priority
        except Exception as e:
            logger.error("SLA Agent: Gemini classification failed, using rules fallback. Error: %s", e)

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
