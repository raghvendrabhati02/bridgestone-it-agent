import logging

logger = logging.getLogger("it-agent-backend")

def check_internet_connection() -> dict:
    """
    Checks if the local system has active internet connectivity.
    Returns: {"connected": bool, "ping_ms": float, "status": str}
    """
    logger.info("Tools: Checking internet connectivity...")
    return {
        "connected": True,
        "ping_ms": 14.5,
        "status": "Online"
    }

def restart_system() -> dict:
    """
    Simulates a system restart.
    Returns: {"success": bool, "message": str}
    """
    logger.info("Tools: Requesting system restart...")
    return {
        "success": True,
        "message": "System reboot initiated successfully."
    }

def get_system_info() -> dict:
    """
    Retrieves system specifications.
    Returns: {"os": str, "hostname": str, "ip_address": str}
    """
    logger.info("Tools: Retrieving system information...")
    return {
        "os": "Windows 11 Enterprise",
        "hostname": "BS-EMP-WS09",
        "ip_address": "192.168.1.104"
    }
