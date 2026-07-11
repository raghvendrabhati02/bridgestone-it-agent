"""
handlers/password_handler.py
─────────────────────────────────────────────────────────────────────────────
Handles tool:
    RESET_PASSWORD  → action_service.create_access_restoration_request()
"""

from app.services.handlers import ok

TOOL = "RESET_PASSWORD"


def handle(params: dict) -> dict:
    """→ action_service.create_access_restoration_request()"""
    from app.services.action_service import create_access_restoration_request
    detail   = params.get("detail", "Password reset request.")
    category = params.get("category", "PASSWORD_RESET")
    result = create_access_restoration_request(category=category, detail=detail)
    return ok(TOOL, data=result, message="Password reset / access restoration request created.")
