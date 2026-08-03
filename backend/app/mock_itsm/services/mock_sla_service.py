"""
mock_sla_service.py
─────────────────────────────────────────────────────────────────────────────
SLA Service for Mock ITSM Platform.
Maps Priority levels to SLA resolution hours:
  CRITICAL -> 1 Hour
  HIGH     -> 4 Hours
  MEDIUM   -> 8 Hours
  LOW      -> 24 Hours
"""

import logging

logger = logging.getLogger("it-agent-backend")


class MockSLAService:
    @staticmethod
    def calculate_priority(category: str, description: str = "") -> str:
        """Determines priority level based on category and text keywords."""
        cat_upper = (category or "").upper()
        desc_lower = (description or "").lower()

        if any(kw in desc_lower for kw in ["outage", "entire network", "data breach", "server crash"]):
            return "CRITICAL"
        elif any(kw in desc_lower for kw in ["urgent", "sap failure", "production down"]) or cat_upper == "SAP":
            return "HIGH"
        elif cat_upper in ("VPN", "OUTLOOK", "NETWORK"):
            return "MEDIUM"
        return "LOW"

    @staticmethod
    def calculate_sla_hours(priority: str) -> int:
        p = (priority or "").strip().upper()
        if p == "CRITICAL":
            return 1
        elif p == "HIGH":
            return 4
        elif p == "MEDIUM":
            return 8
        elif p == "LOW":
            return 24
        return 24
