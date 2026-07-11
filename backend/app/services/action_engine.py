"""
action_engine.py
─────────────────────────────────────────────────────────────────────────────
Owns all automated actions mapping and execution.

Design contracts:
  • Maps Intent/Category to Tool + Parameters + Confirmation Required.
  • ConversationService must never know how tools execute.
  • ConversationService -> ActionEngine -> ToolRouter -> Tool -> Response.
  • Never executes privileged tools without confirmation.
  • Every execution must be logged.
  • If tool execution fails, offers a ticket.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import app.services.tool_router as tool_router

logger = logging.getLogger("it-agent-backend")


@dataclass
class ActionDef:
    name: str
    tool: str
    parameters: dict = field(default_factory=dict)
    requires_confirmation: bool = True


# Mappings for all categories as requested in requirements
ACTIONS_MAP: Dict[str, List[ActionDef]] = {
    "VPN": [
        ActionDef("Reset VPN session", "VPN_ACCESS_RESTORE", {}, True),
        ActionDef("Unlock VPN account", "VPN_ACCESS_RESTORE", {"action": "unlock"}, True),
        ActionDef("Refresh VPN profile", "VPN_ACCESS_RESTORE", {"action": "refresh"}, True),
    ],
    "PASSWORD_RESET": [
        ActionDef("Reset password", "RESET_PASSWORD", {}, True),
        ActionDef("Unlock AD account", "RESET_PASSWORD", {"action": "unlock"}, True),
    ],
    "OUTLOOK": [
        ActionDef("Rebuild Outlook profile", "CHECK_OUTLOOK", {"action": "rebuild"}, False),
        ActionDef("Clear OST cache", "CHECK_OUTLOOK", {"action": "clear_cache"}, False),
        ActionDef("Restart Outlook", "RESTART_SERVICE", {"service": "outlook"}, False),
    ],
    "PRINTER": [
        ActionDef("Restart print spooler", "RESTART_SERVICE", {"service": "spooler"}, False),
        ActionDef("Clear print queue", "RESTART_SERVICE", {"service": "print_queue"}, False),
        ActionDef("Set default printer", "RESTART_SERVICE", {"service": "default_printer"}, False),
    ],
    "SOFTWARE_INSTALLATION": [
        ActionDef("Install approved software", "INSTALL_SOFTWARE", {}, True),
        ActionDef("Repair software", "INSTALL_SOFTWARE", {"action": "repair"}, True),
    ],
    "SHARED_MAILBOX": [
        ActionDef("Request access", "CREATE_TICKET", {"type": "shared_mailbox_access"}, True),
        ActionDef("Verify permissions", "CHECK_DEVICE_STATUS", {"check": "mailbox_permissions"}, False),
    ],
    "IT_ASSET_ALLOCATION": [
        ActionDef("Create asset request", "CREATE_TICKET", {"type": "asset_request"}, True),
    ],
}


class ActionEngine:
    """Enterprise Action Engine mapping categories to tool invocations."""

    def get_next_action(self, category: str, attempted: List[str]) -> Optional[ActionDef]:
        """Return the next unattempted ActionDef for the given category."""
        category_upper = category.strip().upper()
        actions = ACTIONS_MAP.get(category_upper, [])
        for act in actions:
            if act.name not in attempted:
                return act
        return None

    def execute(self, action: ActionDef) -> dict:
        """
        Execute the action via ToolRouter and log the execution.
        Never raises — errors are captured and returned in ToolResult format.
        """
        logger.info(
            "ActionEngine: Executing action='%s' tool='%s' params=%s",
            action.name,
            action.tool,
            action.parameters,
        )
        try:
            tool_request = {"tool": action.tool, "parameters": action.parameters}
            result = tool_router.route(tool_request)
            logger.info(
                "ActionEngine: Execution of action='%s' finished with status='%s'",
                action.name,
                result.get("status"),
            )
            return result
        except Exception as exc:
            logger.error(
                "ActionEngine: Execution of action='%s' failed: %s",
                action.name,
                exc,
                exc_info=True,
            )
            return {
                "tool": action.tool,
                "status": "ERROR",
                "data": {},
                "message": f"Execution failed: {exc}",
            }
