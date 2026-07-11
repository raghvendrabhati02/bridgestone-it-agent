"""
handlers/__init__.py
─────────────────────────────────────────────────────────────────────────────
Shared result-builder helpers for all ToolRouter handler modules.

Every handler returns a normalised ToolResult dict:
    {
        "tool":    str,                         # echoed tool name
        "status":  "SUCCESS"|"ERROR"|"PLACEHOLDER",
        "data":    dict,                        # service response payload
        "message": str                          # human-readable summary
    }

Import pattern inside any handler:
    from app.services.handlers import ok, err, placeholder
"""

from __future__ import annotations

import logging

logger = logging.getLogger("it-agent-backend")


def ok(tool: str, data: dict, message: str = "") -> dict:
    """Return a normalised SUCCESS result."""
    return {"tool": tool, "status": "SUCCESS", "data": data, "message": message}


def err(tool: str, reason: str) -> dict:
    """Return a normalised ERROR result. Never raises."""
    logger.error("ToolRouter handler error — tool='%s': %s", tool, reason)
    return {"tool": tool, "status": "ERROR", "data": {}, "message": reason}


def placeholder(tool: str, note: str) -> dict:
    """Return a PLACEHOLDER result for tools not yet wired to a downstream service."""
    logger.info("ToolRouter placeholder — tool='%s': %s", tool, note)
    return {"tool": tool, "status": "PLACEHOLDER", "data": {}, "message": note}
