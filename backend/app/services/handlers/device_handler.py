"""
handlers/device_handler.py
─────────────────────────────────────────────────────────────────────────────
Handles tools:
    CHECK_DEVICE_STATUS  → tool_agent.execute_tools()  [category from params]
    RESTART_SERVICE      → tool_agent.execute_tools()  [category="NETWORK"]
    CHECK_OUTLOOK        → tool_agent.execute_tools()  [category="OUTLOOK"]
    CHECK_DEVICE_HEALTH  → placeholder (DeviceAgent integration pending)
"""

from app.services.handlers import ok, placeholder

TOOL_CHECK_DEVICE_STATUS = "CHECK_DEVICE_STATUS"
TOOL_RESTART_SERVICE     = "RESTART_SERVICE"
TOOL_CHECK_OUTLOOK       = "CHECK_OUTLOOK"
TOOL_CHECK_DEVICE_HEALTH = "CHECK_DEVICE_HEALTH"


def handle_check_device_status(params: dict) -> dict:
    """→ tool_agent.execute_tools() with category derived from params"""
    from app.services.tool_agent import execute_tools
    category     = params.get("category", "GENERAL")
    user_message = params.get("user_message", "")
    result = execute_tools(category=category, user_message=user_message)
    return ok(TOOL_CHECK_DEVICE_STATUS, data=result, message=f"Device status check completed for category '{category}'.")


def handle_restart_service(params: dict) -> dict:
    """→ tool_agent.execute_tools() with category="NETWORK" by default"""
    from app.services.tool_agent import execute_tools
    category     = params.get("category", "NETWORK")
    user_message = params.get("service_name", "network service")
    result = execute_tools(category=category, user_message=user_message)
    return ok(TOOL_RESTART_SERVICE, data=result, message=f"Service restart request executed for '{user_message}'.")


def handle_check_outlook(params: dict) -> dict:
    """→ tool_agent.execute_tools() with category="OUTLOOK" """
    from app.services.tool_agent import execute_tools
    user_message = params.get("user_message", "outlook status check")
    result = execute_tools(category="OUTLOOK", user_message=user_message)
    return ok(TOOL_CHECK_OUTLOOK, data=result, message="Outlook / Exchange status check completed.")


def handle_check_device_health(_params: dict) -> dict:
    """Placeholder — DeviceAgent REST integration not yet connected."""
    return placeholder(TOOL_CHECK_DEVICE_HEALTH, note="DeviceAgent health-check endpoint integration is pending.")
