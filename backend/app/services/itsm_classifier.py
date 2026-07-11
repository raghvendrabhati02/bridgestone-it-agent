"""
itsm_classifier.py
──────────────────────────────────────────────────────────────────────────────
Pure, stateless classifier for incoming IT requests.

Determines:
  • request_type    — "INCIDENT" | "SERVICE_REQUEST" | "PRIVILEGED_ACTION"
  • approval_status — "NOT_REQUIRED" | "PENDING"
  • manager         — username of the assigned manager (or None)
  • initial_status  — initial ticket status (maps to TicketState values)

Workflow Rules:
  SERVICE_REQUEST  → status=WAITING_MANAGER, approval_status=PENDING
                     Appears in Manager Portal for approval.
                     After approval → moves to Admin Queue.

  INCIDENT         → status=NEW, approval_status=NOT_REQUIRED
                     Goes directly to Admin Queue (no manager approval needed).
                     Examples: VPN, Printer, Outlook, WiFi, Teams, Password Reset.

  PRIVILEGED_ACTION → status=WAITING_MANAGER, approval_status=PENDING
                      Requires manager review due to security sensitivity.

Rules evaluated in priority order:
  1. Category or description matches privileged keywords → PRIVILEGED_ACTION
  2. Category is a known service-catalog item            → SERVICE_REQUEST
  3. Anything else                                       → INCIDENT
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional
import logging

logger = logging.getLogger("it-agent-backend")

# ── Privileged action indicators ────────────────────────────────────────────

PRIVILEGED_KEYWORDS: set[str] = {
    "change_configuration",
    "disable_account", "enable_account",
    "force_logout", "revoke_access", "grant_access",
    "delete_user", "create_user", "admin_access",
    "firewall_rule", "network_policy",
}

PRIVILEGED_CATEGORIES: set[str] = {
    "ACCESS_REVOKE",
    "ACCESS_GRANT",
}

# ── Service-catalog categories (require manager approval) ───────────────────
# These represent procurement/provisioning items — not operational incidents.

SERVICE_REQUEST_CATEGORIES: set[str] = {
    # Software
    "SOFTWARE_INSTALLATION",
    "SOFTWARE",
    "SOFTWARE_REQUEST",
    # SAP
    "SAP_ACCESS",
    "SAP",
    # Shared resources
    "SHARED_MAILBOX",
    "DISTRIBUTION_LIST",
    "SHARED_FOLDER",
    "SHARED_DRIVE",
    # Hardware / Assets
    "IT_ASSET_ALLOCATION",
    "ASSET_ALLOCATION",
    "ASSET_REQUEST",
    "NEW_LAPTOP",
    "NEW_LAPTOP_REQUEST",
    "HARDWARE_REQUEST",
    "HARDWARE",
    "LAPTOP_REQUEST",
    "MOBILE_DEVICE",
    "MOBILE_REQUEST",
    "MONITOR_REQUEST",
    # Licensing
    "LICENSE_REQUEST",
    "LICENSE",
    # Onboarding
    "ONBOARDING",
    "NEW_EMPLOYEE",
    "NEW_HIRE",
}

# Partial phrase matches in description that indicate a service request
SERVICE_REQUEST_PHRASES: list[str] = [
    "request access",
    "request license",
    "request software",
    "new laptop",
    "new device",
    "install software",
    "software installation",
    "software install",
    "hardware request",
    "shared mailbox",
    "distribution list",
    "shared folder",
    "sap access",
    "sap request",
    "onboard new",
    "new employee",
    "new hire",
    "procurement",
    "purchase request",
    "it asset",
    "asset request",
    "order monitor",
    "request monitor",
    "request a laptop",
    "order a laptop",
    "need a laptop",
    "request printer access",
    "shared drive",
]

# ── Incident categories — go directly to Admin Queue, NO manager approval ───
# These are operational disruptions requiring immediate IT response.

INCIDENT_CATEGORIES: set[str] = {
    "VPN",
    "OUTLOOK",
    "NETWORK",
    "WIFI",
    "WIRELESS",
    "PRINTER",
    "PASSWORD",
    "PASSWORD_RESET",
    "TEAMS",
    "MICROSOFT_TEAMS",
    "HARDWARE",   # break/fix is an incident; procurement is a service request
    "GENERAL",
    "SECURITY",
}

# ── Default manager ──────────────────────────────────────────────────────────
DEFAULT_MANAGER = "manager"


@dataclass(frozen=True)
class ClassificationResult:
    """Immutable result of request classification."""
    request_type: str            # "INCIDENT" | "SERVICE_REQUEST" | "PRIVILEGED_ACTION"
    approval_status: str         # "NOT_REQUIRED" | "PENDING"
    manager: Optional[str]       # Manager username or None
    initial_status: str          # Initial TicketState value
    requires_approval: bool      # Convenience flag


def classify_request(
    category: str,
    description: str = "",
) -> ClassificationResult:
    """
    Classify a request and return routing metadata.

    SERVICE_REQUEST  → WAITING_MANAGER (manager must approve before Admin Queue)
    INCIDENT         → NEW (goes directly to Admin Queue, no manager needed)
    PRIVILEGED_ACTION → WAITING_MANAGER (security-sensitive, needs manager sign-off)

    Args:
        category:    Ticket category (e.g., "VPN", "PASSWORD", "Software").
        description: Issue description / user message.

    Returns:
        ClassificationResult with routing and approval metadata.
    """
    cat_upper = (category or "").upper().replace(" ", "_")
    desc_lower = (description or "").lower()

    # ── Priority 1: Privileged actions ─────────────────────────────────────
    if cat_upper in PRIVILEGED_CATEGORIES:
        logger.info("ITSM Classifier: %s → PRIVILEGED_ACTION (category match)", category)
        return ClassificationResult(
            request_type="PRIVILEGED_ACTION",
            approval_status="PENDING",
            manager=DEFAULT_MANAGER,
            initial_status="WAITING_MANAGER",
            requires_approval=True,
        )

    if any(kw in desc_lower for kw in PRIVILEGED_KEYWORDS):
        matched = next(kw for kw in PRIVILEGED_KEYWORDS if kw in desc_lower)
        logger.info("ITSM Classifier: %s → PRIVILEGED_ACTION (keyword '%s')", category, matched)
        return ClassificationResult(
            request_type="PRIVILEGED_ACTION",
            approval_status="PENDING",
            manager=DEFAULT_MANAGER,
            initial_status="WAITING_MANAGER",
            requires_approval=True,
        )

    # ── Priority 2: Service requests ────────────────────────────────────────
    if cat_upper in SERVICE_REQUEST_CATEGORIES:
        logger.info("ITSM Classifier: %s → SERVICE_REQUEST (category match)", category)
        return ClassificationResult(
            request_type="SERVICE_REQUEST",
            approval_status="PENDING",
            manager=DEFAULT_MANAGER,
            initial_status="WAITING_MANAGER",
            requires_approval=True,
        )

    if any(phrase in desc_lower for phrase in SERVICE_REQUEST_PHRASES):
        matched = next(p for p in SERVICE_REQUEST_PHRASES if p in desc_lower)
        logger.info("ITSM Classifier: %s → SERVICE_REQUEST (phrase '%s')", category, matched)
        return ClassificationResult(
            request_type="SERVICE_REQUEST",
            approval_status="PENDING",
            manager=DEFAULT_MANAGER,
            initial_status="WAITING_MANAGER",
            requires_approval=True,
        )

    # ── Priority 3: Known incident categories — direct to Admin Queue ───────
    if cat_upper in INCIDENT_CATEGORIES:
        logger.info("ITSM Classifier: %s → INCIDENT (known incident category)", category)
        return ClassificationResult(
            request_type="INCIDENT",
            approval_status="NOT_REQUIRED",
            manager=None,
            initial_status="NEW",
            requires_approval=False,
        )

    # ── Priority 4: Default — treat as incident ──────────────────────────────
    logger.info("ITSM Classifier: %s → INCIDENT (default fallback)", category)
    return ClassificationResult(
        request_type="INCIDENT",
        approval_status="NOT_REQUIRED",
        manager=None,
        initial_status="NEW",
        requires_approval=False,
    )
