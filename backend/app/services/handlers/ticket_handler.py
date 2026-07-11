"""
handlers/ticket_handler.py
─────────────────────────────────────────────────────────────────────────────
Handles tools:
    CREATE_TICKET       → ticket_service.create_ticket()
    ESCALATE_TO_HUMAN   → placeholder (L2/L3 escalation queue pending)
"""

from app.services.handlers import ok, placeholder

TOOL_CREATE_TICKET     = "CREATE_TICKET"
TOOL_ESCALATE_TO_HUMAN = "ESCALATE_TO_HUMAN"


def handle_create_ticket(params: dict) -> dict:
    """→ ticket_service.create_ticket()"""
    from app.services.ticket_service import create_ticket
    category    = params.get("category", "GENERAL")
    description = params.get("description", "IT Support Issue")
    created_by  = params.get("created_by", None)
    result = create_ticket(category=category, issue_description=description, created_by=created_by)
    return ok(
        TOOL_CREATE_TICKET,
        data=result,
        message=f"Ticket created: {result.get('ticket_id', 'N/A')}.",
    )


def handle_escalate_to_human(_params: dict) -> dict:
    """Placeholder — L2/L3 escalation queue integration not yet connected."""
    return placeholder(
        TOOL_ESCALATE_TO_HUMAN,
        note="Human escalation queue integration is pending.",
    )
