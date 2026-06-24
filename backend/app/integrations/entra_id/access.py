import logging

logger = logging.getLogger("it-agent-backend")

def check_vpn_access(client, user_id: str) -> dict:
    from app.core.metrics import ACCESS_CHECKS_TOTAL
    try:
        ACCESS_CHECKS_TOTAL.inc()
    except Exception:
        pass
        
    logger.info("Entra ID access check: Checking VPN access for user %s", user_id)
    # Check if user is in "VPN Users" group
    from .groups import check_group_membership
    has_access = check_group_membership(client, user_id, "VPN Users")
    
    return {
        "user_id": user_id,
        "target": "VPN",
        "allowed": has_access,
        "details": "User is a member of the 'VPN Users' Entra group." if has_access else "User is not a member of 'VPN Users' Entra group."
    }

def check_application_access(client, user_id: str, app_name: str) -> dict:
    from app.core.metrics import ACCESS_CHECKS_TOTAL
    try:
        ACCESS_CHECKS_TOTAL.inc()
    except Exception:
        pass
        
    logger.info("Entra ID access check: Checking access to app %s for user %s", app_name, user_id)
    # Checks if user is in app_name group or App-app_name group
    from .groups import check_group_membership
    
    # We check group names like app_name, e.g., "Office 365" or "Domain Users" (since all users have access to Chrome, etc.)
    # In mock/real, we can check group membership. Let's do checking for app_name and app_name + " Users".
    has_access = (
        check_group_membership(client, user_id, app_name) or
        check_group_membership(client, user_id, f"{app_name} Users") or
        check_group_membership(client, user_id, "Domain Users")  # Fallback: domain users have default application permissions
    )
    
    return {
        "user_id": user_id,
        "target": app_name,
        "allowed": has_access,
        "details": f"User is authorized to access {app_name}." if has_access else f"User is blocked from accessing {app_name}."
    }

def check_security_group_access(client, user_id: str, group_name: str) -> dict:
    from app.core.metrics import ACCESS_CHECKS_TOTAL
    try:
        ACCESS_CHECKS_TOTAL.inc()
    except Exception:
        pass
        
    logger.info("Entra ID access check: Checking security group '%s' for user %s", group_name, user_id)
    from .groups import check_group_membership
    is_member = check_group_membership(client, user_id, group_name)
    
    return {
        "user_id": user_id,
        "target": group_name,
        "allowed": is_member,
        "details": f"User is a member of security group '{group_name}'." if is_member else f"User is not a member of security group '{group_name}'."
    }
