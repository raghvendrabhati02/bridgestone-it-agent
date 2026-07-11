"""
handlers/vpn_handler.py
─────────────────────────────────────────────────────────────────────────────
Handles tools:
    VPN_ACCESS_RESTORE  → action_service.create_vpn_restoration_request()
    CHECK_VPN_STATUS    → tool_agent.execute_tools()  [category="VPN"]
"""

from app.services.handlers import ok

TOOL_VPN_ACCESS_RESTORE = "VPN_ACCESS_RESTORE"
TOOL_CHECK_VPN_STATUS   = "CHECK_VPN_STATUS"


def handle_vpn_access_restore(params: dict) -> dict:
    """→ action_service.create_vpn_restoration_request()"""
    from app.services.action_service import create_vpn_restoration_request
    detail = params.get("detail", "VPN access restoration requested.")
    result = create_vpn_restoration_request(detail=detail)
    return ok(TOOL_VPN_ACCESS_RESTORE, data=result, message="VPN access restoration request submitted.")


def handle_check_vpn_status(params: dict) -> dict:
    """→ tool_agent.execute_tools() with category="VPN" """
    from app.services.tool_agent import execute_tools
    user_message = params.get("user_message", "vpn status check")
    result = execute_tools(category="VPN", user_message=user_message)
    return ok(TOOL_CHECK_VPN_STATUS, data=result, message="VPN status check completed.")
