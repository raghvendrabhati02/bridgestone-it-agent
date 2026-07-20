"""
response_builder.py
─────────────────────────────────────────────────────────────────────────────
Single formatter for all chatbot responses.

Design contract:
  • Every string shown to the user originates from exactly one function here.
  • No business logic — only string composition.
  • All functions are pure (no I/O, no state).
  • Never raises — returns a safe fallback on any unexpected input.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional


# ─────────────────────────────────────────────────────────────────────────────
# Troubleshooting step
# ─────────────────────────────────────────────────────────────────────────────

def format_step(step_details: Dict[str, Any]) -> str:
    """Format a single KB troubleshooting step for display to the user."""
    if not step_details:
        return "Please follow the troubleshooting steps. Have you completed this step?"

    step_num = step_details.get("step", "")
    title = step_details.get("title", "").strip()
    instruction = step_details.get("instruction", "").strip()
    image = step_details.get("image", "").strip()
    caption = step_details.get("caption", "").strip()

    question = "Have you completed this step?" if step_num == 1 else "Did that work?"

    parts = [f"**Step {step_num}: {title}**"] if title else [f"**Step {step_num}**"]
    if instruction:
        parts.append(instruction)
    if image:
        parts.append(f"[Screenshot: {image}{' — ' + caption if caption else ''}]")
    parts.append(question)

    return "\n".join(parts)


# ─────────────────────────────────────────────────────────────────────────────
# Verification (after all steps done)
# ─────────────────────────────────────────────────────────────────────────────

def format_verification(verification_questions: Optional[List[str]] = None) -> str:
    """Format the solution verification prompt after all KB steps are complete."""
    base = "I've guided you through all the recommended troubleshooting steps."
    question = (
        verification_questions[0]
        if verification_questions
        else "Did that resolve your issue?"
    )
    return f"{base} {question}"


# ─────────────────────────────────────────────────────────────────────────────
# Ticket creation
# ─────────────────────────────────────────────────────────────────────────────

def format_ticket_prompt() -> str:
    """Ask the user if they want a ServiceNow ticket created."""
    return (
        "I've guided you through all recommended troubleshooting steps, "
        "but it looks like the issue is still unresolved. "
        "Would you like me to create a ServiceNow ticket?"
    )


def format_ticket_created(
    ticket_id: str,
    assigned_team: str,
    request_type: str = "INCIDENT",
    requires_approval: bool = False,
    status_label: str = "",
) -> str:
    """Confirm that a ticket has been successfully created, with workflow-specific messaging."""
    if requires_approval or request_type == "SERVICE_REQUEST":
        return (
            f"✅ Your service request **{ticket_id}** has been created and is now "
            f"**pending manager approval**. "
            f"Once your manager approves it, the **{assigned_team}** team will begin fulfillment. "
            f"You can track its status in **My Tickets**. Is there anything else I can help with?"
        )
    return (
        f"✅ Support ticket **{ticket_id}** has been created and assigned to "
        f"**{assigned_team}**. "
        f"The team will follow up with you shortly. "
        f"You can track progress in **My Tickets**. "
        f"Is there anything else I can help you with?"
    )


def format_ticket_declined() -> str:
    """Acknowledge that the user declined ticket creation."""
    return (
        "Understood — I won't create a ticket at this time. "
        "Feel free to reach out if the issue persists or if you need anything else."
    )


# ─────────────────────────────────────────────────────────────────────────────
# Resolution
# ─────────────────────────────────────────────────────────────────────────────

def format_resolution() -> str:
    """Confirm that the issue has been resolved."""
    return (
        "I'm glad your issue has been resolved! "
        "Feel free to reach out if anything else comes up."
    )


# ─────────────────────────────────────────────────────────────────────────────
# Category / issue switch
# ─────────────────────────────────────────────────────────────────────────────

def format_issue_switch(new_category: str) -> str:
    """Acknowledge that the user has switched to a new issue category."""
    readable = new_category.replace("_", " ").title()
    return f"Got it — let me help you with the {readable} issue."


# ─────────────────────────────────────────────────────────────────────────────
# Step re-prompt (user didn't confirm completion)
# ─────────────────────────────────────────────────────────────────────────────

def format_step_reprompt(step_details: Dict[str, Any]) -> str:
    """Ask the user to complete the current step before advancing."""
    step_num = step_details.get("step", "")
    title = step_details.get("title", "this step").strip()
    return (
        f"Please complete Step {step_num} ({title}) before we move on. "
        "Let me know once you've done it."
    )


# ─────────────────────────────────────────────────────────────────────────────
# Error / fallback
# ─────────────────────────────────────────────────────────────────────────────

def format_error(context: str = "") -> str:
    """Return a safe, user-friendly error message."""
    base = "I encountered an issue processing your request."
    if context:
        base += f" ({context})"
    return base + " Please try again, or I can raise a support ticket for you."


# ─────────────────────────────────────────────────────────────────────────────
# General / Gemini pass-through
# ─────────────────────────────────────────────────────────────────────────────

def format_general(text: str) -> str:
    """
    Sanitise and return a Gemini-generated response.
    Strips leading/trailing whitespace and prefixes that should not be shown.
    """
    if not text or not text.strip():
        return "I'm here to help. Could you tell me more about your issue?"
    cleaned = text.strip()
    # Remove any accidental internal prefixes that Gemini might produce
    for bad_prefix in ("[GeminiService Error]", "Error:", "ERROR:"):
        if cleaned.startswith(bad_prefix):
            return format_error()
    return cleaned


# ─────────────────────────────────────────────────────────────────────────────
# Intent Router — Restart / Cancel
# ─────────────────────────────────────────────────────────────────────────────

def format_restart_ack() -> str:
    """Acknowledge a conversation restart."""
    return (
        "I've reset our conversation. "
        "What IT issue can I help you with today?"
    )


def format_cancel_ack() -> str:
    """Acknowledge that the current workflow has been cancelled."""
    return (
        "I've cancelled the current workflow. "
        "Feel free to let me know if you need help with anything else."
    )


# ─────────────────────────────────────────────────────────────────────────────
# Intent Router — Status
# ─────────────────────────────────────────────────────────────────────────────

def format_status_response(ticket_id: str) -> str:
    """Return the active ticket reference to the user."""
    return (
        f"Your active support ticket is **{ticket_id}**. "
        "The IT team is working on it and will follow up with you shortly. "
        "Is there anything else I can help you with?"
    )


def format_status_not_found() -> str:
    """Inform the user that no active ticket exists for this session."""
    return (
        "I don't have an active support ticket for this session. "
        "If you'd like me to create one, just say **'create ticket'**."
    )


# ─────────────────────────────────────────────────────────────────────────────
# Intent Router — Direct ticket command
# ─────────────────────────────────────────────────────────────────────────────

def format_ticket_command_prompt() -> str:
    """Ask user to confirm they want a ticket created immediately."""
    return (
        "I can create a ServiceNow support ticket for your issue right away. "
        "Would you like me to go ahead and create it?"
    )


# ─────────────────────────────────────────────────────────────────────────────
# ServiceNow failure recovery
# ─────────────────────────────────────────────────────────────────────────────

def format_sn_failure_options() -> str:
    """Offer three recovery paths when ServiceNow is unreachable."""
    return (
        "I'm sorry — I was unable to reach the ServiceNow ticketing system. "
        "What would you like to do?\n\n"
        "1. **Retry** — Try creating the ticket again\n"
        "2. **Save Draft** — Save your issue details for later submission\n"
        "3. **Contact Helpdesk** — Get direct helpdesk contact information"
    )


def format_draft_saved(issue_desc: str) -> str:
    """Confirm that the user's issue has been saved as a draft."""
    preview = (issue_desc[:100] + "...") if len(issue_desc) > 100 else issue_desc
    return (
        f"I've saved your issue as a draft: *\"{preview}\"*\n\n"
        "You can reference this with the IT helpdesk at any time. "
        "Is there anything else I can help you with?"
    )


def format_helpdesk_contact() -> str:
    """Return the IT helpdesk contact details."""
    return (
        "You can reach the IT Helpdesk directly through the following channels:\n\n"
        "📞 **Phone**: +1 800-IT-HELPDESK\n"
        "📧 **Email**: ithelpdesk@bridgestone.com\n"
        "🕐 **Hours**: Monday–Friday, 8:00 AM – 6:00 PM (your local time)\n\n"
        "Please describe your issue when contacting support so they can assist you quickly. "
        "Is there anything else I can help you with?"
    )
