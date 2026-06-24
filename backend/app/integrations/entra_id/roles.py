import logging

logger = logging.getLogger("it-agent-backend")

def get_user_roles(client, user_id: str) -> list:
    logger.info("Entra ID role check: Fetching roles for user %s", user_id)
    # Check if user is in admin or manager groups
    from .groups import check_group_membership
    roles = []
    
    # Map Entra ID group membership directly to directory roles
    if check_group_membership(client, user_id, "Domain Admins") or check_group_membership(client, user_id, "IT Admins"):
        roles.append("ADMIN")
    if check_group_membership(client, user_id, "Domain Managers") or check_group_membership(client, user_id, "IT Managers"):
        roles.append("MANAGER")
        
    # Standard role for all valid AD accounts
    roles.append("EMPLOYEE")
    return roles

def check_admin_role(client, user_id: str) -> bool:
    roles = get_user_roles(client, user_id)
    return "ADMIN" in roles

def check_manager_role(client, user_id: str) -> bool:
    roles = get_user_roles(client, user_id)
    return "MANAGER" in roles or "ADMIN" in roles
