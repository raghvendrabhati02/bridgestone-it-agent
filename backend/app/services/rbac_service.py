"""
RBAC Service
============
Central permission authority for the Bridgestone IT Agent.

Role hierarchy
--------------
EMPLOYEE  < MANAGER  < ADMIN

Permission matrix
-----------------
Action                      EMPLOYEE  MANAGER  ADMIN
--------------------------  --------  -------  -----
create_ticket               ✅        ✅       ✅
view_own_tickets            ✅        ✅       ✅
view_all_tickets            ❌        ✅       ✅
update_ticket_lifecycle     ❌        ✅       ✅
resolve_ticket              ❌        ✅       ✅
close_ticket                ❌        ✅       ✅
approve_privileged_action   ❌        ✅       ✅
view_audit_logs             ❌        ❌       ✅
override_lifecycle          ❌        ❌       ✅
execute_privileged_action   ❌        ❌       ✅

Usage
-----
    from app.services.rbac_service import has_permission, check_permission

    if not has_permission("EMPLOYEE", "close_ticket"):
        return {"decision": "ACCESS_DENIED", ...}

    # OR — raises PermissionError if denied
    check_permission("MANAGER", "approve_privileged_action")
"""

import logging
from typing import Dict, Set, Optional

logger = logging.getLogger("it-agent-backend")

# ── Permission matrix ─────────────────────────────────────────────────────────

ROLE_PERMISSIONS: Dict[str, Set[str]] = {
    "EMPLOYEE": {
        "create_ticket",
        "view_own_tickets",
    },
    "MANAGER": {
        "create_ticket",
        "view_own_tickets",
        "view_all_tickets",
        "update_ticket_lifecycle",
        "resolve_ticket",
        "close_ticket",
        "approve_privileged_action",
    },
    "ADMIN": {
        "create_ticket",
        "view_own_tickets",
        "view_all_tickets",
        "update_ticket_lifecycle",
        "resolve_ticket",
        "close_ticket",
        "approve_privileged_action",
        "view_audit_logs",
        "override_lifecycle",
        "execute_privileged_action",
    },
}

# All known lifecycle transition actions that require RBAC checks
LIFECYCLE_ACTIONS = {
    "update_ticket_lifecycle",
    "resolve_ticket",
    "close_ticket",
    "override_lifecycle",
}

# All known privileged approval actions
APPROVAL_ACTIONS = {
    "approve_privileged_action",
    "execute_privileged_action",
}


# ── Public API ────────────────────────────────────────────────────────────────

def has_permission(role: Optional[str], action: str) -> bool:
    """
    Returns True if the given role is allowed to perform the action.
    Unknown roles are treated as EMPLOYEE for safety.
    """
    if not role:
        logger.warning("RBAC Service: No role provided — defaulting to EMPLOYEE for action '%s'", action)
        role = "EMPLOYEE"

    role = role.upper().strip()
    allowed = ROLE_PERMISSIONS.get(role, ROLE_PERMISSIONS["EMPLOYEE"])
    result = action in allowed

    if not result:
        logger.warning(
            "RBAC Service: PERMISSION DENIED — role='%s' action='%s'",
            role, action,
        )
    else:
        logger.debug(
            "RBAC Service: Permission GRANTED — role='%s' action='%s'",
            role, action,
        )

    return result


def check_permission(role: Optional[str], action: str) -> None:
    """
    Raises PermissionError if the role is not allowed to perform the action.
    Use this for imperative code paths.
    """
    if not has_permission(role, action):
        raise PermissionError(
            f"Role '{role}' is not authorised to perform action '{action}'."
        )


def get_permissions_for_role(role: Optional[str]) -> Set[str]:
    """Returns the full permission set for a given role."""
    if not role:
        return ROLE_PERMISSIONS["EMPLOYEE"]
    return ROLE_PERMISSIONS.get(role.upper().strip(), ROLE_PERMISSIONS["EMPLOYEE"])


def get_role_summary() -> Dict[str, list]:
    """Returns a JSON-serialisable summary of the permission matrix."""
    return {role: sorted(perms) for role, perms in ROLE_PERMISSIONS.items()}


def infer_lifecycle_action(target_state: str) -> str:
    """
    Maps a lifecycle target state to its required RBAC action.

    CLOSED                        → close_ticket
    RESOLVED                      → resolve_ticket
    ASSIGNED | IN_PROGRESS | etc  → update_ticket_lifecycle
    """
    state = (target_state or "").upper().strip()
    if state == "CLOSED":
        return "close_ticket"
    if state == "RESOLVED":
        return "resolve_ticket"
    return "update_ticket_lifecycle"


def build_access_denied_response(role: str, action: str, ticket_id: str = "") -> dict:
    """
    Builds a standard ACCESS_DENIED graph output dict.
    """
    ticket_ctx = f" on ticket {ticket_id}" if ticket_id else ""
    message = (
        f"⛔ **ACCESS_DENIED**\n\n"
        f"Your role **{role}** does not have permission to perform "
        f"**{action.replace('_', ' ').title()}**{ticket_ctx}.\n\n"
        f"Please contact your IT Manager or Administrator for assistance."
    )
    logger.warning(
        "RBAC Service: ACCESS_DENIED — role='%s' action='%s' ticket='%s'",
        role, action, ticket_id,
    )
    return {
        "decision": "ACCESS_DENIED",
        "decision_response": message,
    }
