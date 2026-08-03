"""
mock_assignment_service.py
─────────────────────────────────────────────────────────────────────────────
Assignment Group resolution and routing service for Mock ITSM Platform.
Reuses app.services.assignment_service for routing rules:
  VPN → Network Team
  Outlook / Teams → Microsoft 365 Team
  Software Installation → Software Support
  Printer → Hardware Support
  Password Reset / General → Service Desk
"""

import logging
from typing import List
from app.services.assignment_service import get_assignment_team

logger = logging.getLogger("it-agent-backend")

ASSIGNMENT_GROUPS = [
    "Network Team",
    "Microsoft 365 Team",
    "Software Support",
    "Hardware Support",
    "Security Team",
    "Service Desk"
]


class MockAssignmentService:
    @staticmethod
    def get_assignment_team(category: str, issue_description: str = "") -> str:
        """Determines target Assignment Group by delegating to canonical assignment_service."""
        desc = (issue_description or "").lower()
        if "vpn" in desc or "wifi" in desc or "network" in desc:
            return "Network Team"
        elif "outlook" in desc or "teams" in desc or "m365" in desc or "email" in desc:
            return "Microsoft 365 Team"
        elif "software" in desc or "install" in desc:
            return "Software Support"
        elif "printer" in desc or "hardware" in desc:
            return "Hardware Support"
        elif "password" in desc or "reset" in desc:
            return "Service Desk"

        return get_assignment_team(category)

    @staticmethod
    def list_all_groups() -> List[str]:
        return ASSIGNMENT_GROUPS
