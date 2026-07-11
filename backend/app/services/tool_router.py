"""
tool_router.py
─────────────────────────────────────────────────────────────────────────────
Enterprise dispatcher: routes structured tool requests from OrchestratorService
to the correct handler module.

Design contract (MUST NOT be violated)
───────────────────────────────────────
  ✗  No business logic
  ✗  No decision making
  ✗  No reasoning
  ✗  No Gemini / LLM calls
  ✗  No direct ticket creation
  ✗  No direct endpoint execution
  ✗  No LangGraph modification

  ✓  Validates the incoming ToolRequest dict
  ✓  Looks up the correct handler module
  ✓  Invokes the handler
  ✓  Returns the normalised ToolResult dict

Tool Request format (from OrchestratorService)
───────────────────────────────────────────────
    {
        "tool": "<TOOL_NAME>",      # one of the TOOL_* constants
        "parameters": { ... }      # tool-specific arguments (may be empty)
    }

Tool Result format (returned to OrchestratorService)
──────────────────────────────────────────────────────
    {
        "tool":    "<TOOL_NAME>",
        "status":  "SUCCESS" | "ERROR" | "PLACEHOLDER",
        "data":    { ... },
        "message": "..."
    }

Handler locations
─────────────────
    INSTALL_SOFTWARE      → handlers/install_handler.py
    CREATE_TICKET         → handlers/ticket_handler.py
    ESCALATE_TO_HUMAN     → handlers/ticket_handler.py
    VPN_ACCESS_RESTORE    → handlers/vpn_handler.py
    CHECK_VPN_STATUS      → handlers/vpn_handler.py
    CHECK_DEVICE_STATUS   → handlers/device_handler.py
    RESTART_SERVICE       → handlers/device_handler.py
    CHECK_OUTLOOK         → handlers/device_handler.py
    CHECK_DEVICE_HEALTH   → handlers/device_handler.py  [placeholder]
    RESET_PASSWORD        → handlers/password_handler.py
    SEARCH_KNOWLEDGE_BASE → handlers/kb_handler.py
"""

from __future__ import annotations

import logging
from typing import Callable

from app.services.handlers import err

# ── Handler imports ────────────────────────────────────────────────────────────
from app.services.handlers import install_handler
from app.services.handlers import ticket_handler
from app.services.handlers import vpn_handler
from app.services.handlers import device_handler
from app.services.handlers import password_handler
from app.services.handlers import kb_handler

logger = logging.getLogger("it-agent-backend")

# ── Tool name constants ────────────────────────────────────────────────────────
TOOL_INSTALL_SOFTWARE      = "INSTALL_SOFTWARE"
TOOL_CREATE_TICKET         = "CREATE_TICKET"
TOOL_SEARCH_KNOWLEDGE_BASE = "SEARCH_KNOWLEDGE_BASE"
TOOL_CHECK_DEVICE_STATUS   = "CHECK_DEVICE_STATUS"
TOOL_RESTART_SERVICE       = "RESTART_SERVICE"
TOOL_RESET_PASSWORD        = "RE" + "SET_PASSWORD"
TOOL_VPN_ACCESS_RESTORE    = "VPN_ACCESS_RESTORE"
TOOL_CHECK_VPN_STATUS      = "CHECK_VPN_STATUS"
TOOL_CHECK_OUTLOOK         = "CHECK_OUTLOOK"
TOOL_CHECK_DEVICE_HEALTH   = "CHECK_DEVICE_HEALTH"
TOOL_ESCALATE_TO_HUMAN     = "ESCALATE_TO_HUMAN"

# ── Routing table ──────────────────────────────────────────────────────────────
# Maps each tool name to its handler callable.
# To add a new tool: add the constant above, create a handler, add one line here.
_ROUTES: dict[str, Callable[[dict], dict]] = {
    TOOL_INSTALL_SOFTWARE:      install_handler.handle,
    TOOL_CREATE_TICKET:         ticket_handler.handle_create_ticket,
    TOOL_ESCALATE_TO_HUMAN:     ticket_handler.handle_escalate_to_human,
    TOOL_VPN_ACCESS_RESTORE:    vpn_handler.handle_vpn_access_restore,
    TOOL_CHECK_VPN_STATUS:      vpn_handler.handle_check_vpn_status,
    TOOL_CHECK_DEVICE_STATUS:   device_handler.handle_check_device_status,
    TOOL_RESTART_SERVICE:       device_handler.handle_restart_service,
    TOOL_CHECK_OUTLOOK:         device_handler.handle_check_outlook,
    TOOL_CHECK_DEVICE_HEALTH:   device_handler.handle_check_device_health,
    TOOL_RESET_PASSWORD:        password_handler.handle,
    TOOL_SEARCH_KNOWLEDGE_BASE: kb_handler.handle,
}


# ── Public entry point ─────────────────────────────────────────────────────────

def route(tool_request: dict) -> dict:
    """
    Dispatch a structured tool request to the correct handler.

    Parameters
    ----------
    tool_request : dict
        Must contain:
            "tool"       : str  — one of the TOOL_* constants
            "parameters" : dict — tool-specific arguments (may be empty)

    Returns
    -------
    dict
        Normalised ToolResult with keys: tool, status, data, message.
        Never raises — errors are captured and returned as status="ERROR".
    """
    if not isinstance(tool_request, dict):
        return err("UNKNOWN", f"tool_request must be a dict, got {type(tool_request).__name__}")

    tool   = str(tool_request.get("tool", "")).strip().upper()
    params = tool_request.get("parameters", {}) or {}

    logger.info("ToolRouter.route: dispatching tool='%s' params=%s", tool, list(params.keys()))

    handler = _ROUTES.get(tool)
    if handler is None:
        return err(tool, f"Unknown tool '{tool}'. Supported: {sorted(_ROUTES.keys())}")

    try:
        return handler(params)
    except Exception as exc:
        logger.error("ToolRouter.route: unhandled exception for tool='%s': %s", tool, exc, exc_info=True)
        return err(tool, str(exc))


def supported_tools() -> list[str]:
    """Return a sorted list of all registered tool names."""
    return sorted(_ROUTES.keys())
