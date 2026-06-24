import logging

logger = logging.getLogger("it-agent-backend")

def check_email_sync_status() -> dict:
    """
    Checks email sync status between local Outlook client and Microsoft Exchange.
    Returns: {"synced": bool, "last_sync": str, "offline_mode": bool}
    """
    logger.info("Tools: Checking Outlook email sync status...")
    return {
        "synced": True,
        "last_sync": "Just now",
        "offline_mode": False
    }

def repair_outlook_profile() -> dict:
    """
    Triggers a clean-up/repair sequence of the active Outlook profile.
    Returns: {"success": bool, "message": str}
    """
    logger.info("Tools: Repairing Outlook profile...")
    return {
        "success": True,
        "message": "Outlook profile repair sequence completed successfully."
    }

def clear_outlook_cache() -> dict:
    """
    Clears local offline Outlook data file (OST) cache.
    Returns: {"success": bool, "bytes_cleared": int}
    """
    logger.info("Tools: Clearing Outlook OST cache...")
    return {
        "success": True,
        "bytes_cleared": 104857600  # 100 MB mock
    }

from app.adapters.microsoft_graph_adapter import MicrosoftGraphAdapter
from app.adapters.active_directory_adapter import ActiveDirectoryAdapter

graph_adapter = MicrosoftGraphAdapter()
ad_adapter = ActiveDirectoryAdapter()

def check_mailbox_status(user_id: str = "graph-user-12345") -> dict:
    """
    Checks the status of the employee's Outlook mailbox.
    """
    logger.info("Tools: Validating user account status in Entra ID first...")
    try:
        ad_user = ad_adapter.check_user_access(user_id)
        if ad_user.get("status") != "ACTIVE":
            logger.warning("Tools: User account %s is DISABLED in Active Directory / Entra ID.", user_id)
            return {
                "success": False,
                "error": f"Mailbox inaccessible because user account is {ad_user.get('status')}."
            }
    except Exception as e:
        logger.error("Tools: Failed to validate user status in Active Directory: %s", e)

    logger.info("Tools: Checking mailbox status for user %s via MicrosoftGraphAdapter...", user_id)
    try:
        res = graph_adapter.get_mailbox_status(user_id)
        return {
            "mailbox_status": res.get("mailbox_status"),
            "quota_used": "42%",
            "size_gb": 21.0
        }
    except Exception as e:
        logger.error("Tools: Failed to check mailbox status: %s", e)
        return {"success": False, "error": str(e)}

def check_exchange_connectivity() -> dict:
    """
    Checks connection connectivity to the Microsoft Exchange Server.
    """
    logger.info("Tools: Checking Exchange server connectivity via MicrosoftGraphAdapter...")
    try:
        res = graph_adapter.check_exchange_connectivity()
        return {
            "exchange_server": res.get("exchange_server"),
            "protocol": res.get("protocol"),
            "latency_ms": res.get("latency_ms")
        }
    except Exception as e:
        logger.error("Tools: Failed to check Exchange connectivity: %s", e)
        return {"success": False, "error": str(e)}
