import logging

logger = logging.getLogger("it-agent-backend")

def check_admin_privileges() -> dict:
    """
    Verifies if the employee has administrator access privileges on their workstation.
    Returns: {"has_admin": bool, "user_group": str}
    """
    logger.info("Tools: Checking local admin privileges...")
    return {
        "has_admin": False,
        "user_group": "Domain Users"
    }

def check_software_installed(software_name: str) -> dict:
    """
    Checks if a specific software application is installed.
    Returns: {"installed": bool, "software_name": str, "version": str}
    """
    logger.info("Tools: Checking installation status of software: %s", software_name)
    return {
        "installed": False,
        "software_name": software_name,
        "version": "N/A"
    }

def install_software(software_name: str) -> dict:
    """
    Initiates installation of approved software via corporate software center.
    Returns: {"success": bool, "message": str}
    """
    logger.info("Tools: Initiating installation for software: %s", software_name)
    return {
        "success": True,
        "message": f"Successfully queued installation for {software_name}."
    }

def check_software_availability(software_name: str = "Chrome") -> dict:
    """
    Checks if the requested software is approved and available in corporate software repository.
    """
    logger.info("Tools: Checking availability of software: %s", software_name)
    approved_software = ["chrome", "firefox", "outlook", "sap", "vpn", "zoom", "teams"]
    is_approved = software_name.lower().strip() in approved_software
    return {
        "software": software_name,
        "approved": is_approved,
        "latest_version": "120.0.0" if is_approved else "N/A"
    }

from app.adapters.active_directory_adapter import ActiveDirectoryAdapter

ad_adapter = ActiveDirectoryAdapter()

def check_installation_permissions(user_id: str = "entra-user-12345") -> dict:
    """
    Checks if the user has permissions to install software.
    """
    logger.info("Tools: Checking installation permissions for %s via ActiveDirectoryAdapter...", user_id)
    try:
        res = ad_adapter.check_application_access(user_id, "Software Center")
        allowed = res.get("allowed", False)
        return {
            "has_permission": allowed,
            "policy_group": "Standard Employees Group" if allowed else "Unlicensed Guest Group"
        }
    except Exception as e:
        logger.error("Tools: Failed to check installation permissions: %s", e)
        return {"has_permission": False, "error": str(e)}
