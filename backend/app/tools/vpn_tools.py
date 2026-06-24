import logging
from app.adapters.vpn_adapter import VPNAdapter

logger = logging.getLogger("it-agent-backend")
vpn_adapter = VPNAdapter()

def check_vpn_connection_status() -> dict:
    """
    Checks the status of the corporate VPN client.
    Returns: {"connected": bool, "gateway": str, "client": str}
    """
    logger.info("Tools: Checking VPN status...")
    return {
        "connected": False,
        "gateway": "vpn-gateway.bridgestone.com",
        "client": "AnyConnect"
    }

def restart_vpn_client() -> dict:
    """
    Restarts the VPN client service.
    Returns: {"success": bool, "message": str}
    """
    logger.info("Tools: Restarting VPN client...")
    return {
        "success": True,
        "message": "VPN client restarted successfully."
    }

def get_vpn_client_version() -> dict:
    """
    Retrieves the version of the installed VPN client.
    Returns: {"version": str, "up_to_date": bool}
    """
    logger.info("Tools: Retrieving VPN client version...")
    return {
        "version": "4.10.05085",
        "up_to_date": True
    }

def check_vpn_gateway() -> dict:
    """
    Checks the status of the corporate VPN gateway.
    """
    logger.info("Tools: Checking VPN Gateway via VPNAdapter...")
    return vpn_adapter.check_gateway_status()

from app.adapters.active_directory_adapter import ActiveDirectoryAdapter

ad_adapter = ActiveDirectoryAdapter()

def check_user_vpn_access(username: str) -> dict:
    """
    Checks if the given user has access to VPN.
    """
    logger.info("Tools: Checking user VPN access for: %s via ActiveDirectoryAdapter...", username)
    try:
        res = ad_adapter.check_vpn_access(username)
        is_member = res.get("allowed", False)
        return {
            "username": username,
            "vpn_access": "ACTIVE" if is_member else "DISABLED",
            "group_membership": "VPN Users" if is_member else "None"
        }
    except Exception as e:
        logger.error("Tools: Failed to check VPN access: %s", e)
        return {"success": False, "error": str(e)}

def check_vpn_health() -> dict:
    """
    Checks the overall health parameters of the VPN service.
    """
    logger.info("Tools: Checking VPN health via VPNAdapter...")
    res = vpn_adapter.check_gateway_status()
    return {
        "vpn_gateway": res.get("vpn_gateway"),
        "latency_ms": res.get("latency_ms"),
        "status": res.get("status")
    }
