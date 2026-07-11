"""
intent_router.py
─────────────────────────────────────────────────────────────────────────────
Enterprise Intent Router — deterministic, regex-first, priority-ordered.

Priority order (strictly enforced — never re-ordered):
  1. TICKET_COMMAND   — "create ticket", "raise incident", "open a ticket"
  2. RESTART          — "restart", "start over", "new issue", "reset"
  3. CANCEL           — "cancel", "abort", "stop", "never mind"
  4. STATUS           — "ticket status", "check ticket", "my ticket"
  5. RESOLVED_KEYWORD — "working", "fixed", "solved", "issue resolved"
  6. IT_ISSUE         — classified via detect_intent() (regex + Gemini)
  7. GENERAL          — anything else

Design contracts:
  • Stateless — all state lives on SessionState.
  • Pure — no I/O, no DB calls, no LLM calls (except _classify_category).
  • Deterministic — identical inputs produce identical outputs.
  • Never raises.
"""

from __future__ import annotations

import re
import logging
from dataclasses import dataclass
from enum import Enum
from typing import Optional

logger = logging.getLogger("it-agent-backend")


# ─────────────────────────────────────────────────────────────────────────────
# Intent types
# ─────────────────────────────────────────────────────────────────────────────

class IntentType(str, Enum):
    TICKET_COMMAND   = "TICKET_COMMAND"
    RESTART          = "RESTART"
    CANCEL           = "CANCEL"
    STATUS           = "STATUS"
    RESOLVED_KEYWORD = "RESOLVED_KEYWORD"
    IT_ISSUE         = "IT_ISSUE"
    GENERAL          = "GENERAL"


# ─────────────────────────────────────────────────────────────────────────────
# ServiceNow failure recovery intents
# ─────────────────────────────────────────────────────────────────────────────

class TicketFailureIntent(str, Enum):
    RETRY    = "RETRY"
    DRAFT    = "DRAFT"
    HELPDESK = "HELPDESK"
    UNKNOWN  = "UNKNOWN"


# ─────────────────────────────────────────────────────────────────────────────
# Route result
# ─────────────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class RouteResult:
    intent: IntentType
    category: Optional[str]        # populated only for IT_ISSUE
    normalized_message: str


# ─────────────────────────────────────────────────────────────────────────────
# Compiled regex patterns (deterministic, order-sensitive)
# ─────────────────────────────────────────────────────────────────────────────

_TICKET_PATTERNS = re.compile(
    r"\b(create|raise|open|log|submit|make|need)\s+"
    r"(an?\s+)?(the\s+)?(support\s+)?"
    r"(ticket|incident|case|support\s+request|sr)\b"
    r"|\bopen\s+incident\b"
    r"|\bescalate(\s+(this|issue|now))?\b",
    re.IGNORECASE,
)

_PASSWORD_RESET_PATTERNS = re.compile(
    r"\b(reset\s+(\w+\s+){0,2}password"
    r"|password\s+reset"
    r"|forgot\s+(\w+\s+){0,2}password"
    r"|password\s+expired"
    r"|cannot\s+login"
    r"|change\s+(\w+\s+){0,2}password"
    r"|unlock\s+(\w+\s+){0,2}account"
    r"|temporary\s+password)\b",
    re.IGNORECASE,
)

_RESTART_PATTERNS = re.compile(
    r"\b(start\s+over|begin\s+again|new\s+issue|new\s+problem|fresh\s+start|start\s+fresh|"
    r"reset\s+chat|reset\s+conversation|new\s+conversation|clear\s+conversation|new\s+session|clear\s+chat)\b"
    r"|^(\s*reset\s*|\s*restart\s*)[.!?]?$",
    re.IGNORECASE,
)

_CANCEL_PATTERNS = re.compile(
    r"\b(cancel|abort|stop|never\s+mind|forget\s+it|discard|quit|exit)\b",
    re.IGNORECASE,
)

_STATUS_PATTERNS = re.compile(
    r"\b(ticket\s+status|check\s+status|check\s+ticket|my\s+ticket|track\s+ticket|follow\s+up|update\s+on\s+ticket|what.?s\s+my\s+ticket)\b",
    re.IGNORECASE,
)

_RESOLVED_PATTERNS = re.compile(
    r"(?<!not )(?<!not\t)\b(working|fixed|solved|resolved|issue\s+resolved|problem\s+fixed|"
    r"it\s+works?|all\s+good|sorted|it.?s\s+working|now\s+working|resolved\s+now|"
    r"problem\s+solved)\b",
    re.IGNORECASE,
)

_RETRY_PATTERNS = re.compile(
    r"\b(retry|try\s+again|attempt\s+again|redo|try\s+once\s+more)\b",
    re.IGNORECASE,
)

_DRAFT_PATTERNS = re.compile(
    r"\b(save\s+draft|draft|save\s+for\s+later|save\s+it|save\s+this)\b",
    re.IGNORECASE,
)

_HELPDESK_PATTERNS = re.compile(
    r"\b(helpdesk|help\s+desk|contact\s+helpdesk|contact\s+support|call\s+helpdesk|contact\s+it)\b",
    re.IGNORECASE,
)


# ─────────────────────────────────────────────────────────────────────────────
# Input normalization
# ─────────────────────────────────────────────────────────────────────────────

def normalize(message: str) -> str:
    """Lowercase, collapse whitespace, strip leading/trailing spaces."""
    text = message.lower().strip()
    text = re.sub(r"\s+", " ", text)
    return text


# ─────────────────────────────────────────────────────────────────────────────
# ServiceNow failure recovery detector
# ─────────────────────────────────────────────────────────────────────────────

def detect_ticket_failure_intent(message: str) -> TicketFailureIntent:
    """
    Detect which recovery path the user chose after a ServiceNow failure.
    Supports regex phrases AND numeric shortcuts (1, 2, 3).
    """
    if _RETRY_PATTERNS.search(message):
        return TicketFailureIntent.RETRY
    if _DRAFT_PATTERNS.search(message):
        return TicketFailureIntent.DRAFT
    if _HELPDESK_PATTERNS.search(message):
        return TicketFailureIntent.HELPDESK

    # Numeric / ordinal shortcuts
    norm = normalize(message)
    if norm in {"1", "one", "option 1", "option one"}:
        return TicketFailureIntent.RETRY
    if norm in {"2", "two", "option 2", "option two"}:
        return TicketFailureIntent.DRAFT
    if norm in {"3", "three", "option 3", "option three"}:
        return TicketFailureIntent.HELPDESK

    return TicketFailureIntent.UNKNOWN


# ─────────────────────────────────────────────────────────────────────────────
# Enterprise Intent Router
# ─────────────────────────────────────────────────────────────────────────────

class IntentRouter:
    """
    Stateless, deterministic intent router.
    Regex patterns are checked in strict priority order before any LLM call.
    """

    def route(self, message: str) -> RouteResult:
        """
        Route an incoming message to an IntentType.

        Priority (never violated):
          1. TICKET_COMMAND
          2. RESTART
          3. CANCEL
          4. STATUS
          5. RESOLVED_KEYWORD
          6. IT_ISSUE  (LLM-assisted)
          7. GENERAL
        """
        normalized = normalize(message)

        # 1. Ticket command — highest priority
        if _TICKET_PATTERNS.search(message):
            logger.info("IntentRouter: TICKET_COMMAND matched | input=%r", normalized)
            cat = self._classify_category(message)
            return RouteResult(IntentType.TICKET_COMMAND, cat, normalized)

        # 2. Password reset command — priority above restart
        if _PASSWORD_RESET_PATTERNS.search(message):
            logger.info("IntentRouter: PASSWORD_RESET matched | input=%r", normalized)
            return RouteResult(IntentType.IT_ISSUE, "PASSWORD_RESET", normalized)

        # 3. Restart conversation
        if _RESTART_PATTERNS.search(message):
            logger.info("IntentRouter: RESTART matched | input=%r", normalized)
            return RouteResult(IntentType.RESTART, None, normalized)

        # 3. Cancel workflow
        if _CANCEL_PATTERNS.search(message):
            logger.info("IntentRouter: CANCEL matched | input=%r", normalized)
            return RouteResult(IntentType.CANCEL, None, normalized)

        # 4. Ticket/issue status check
        if _STATUS_PATTERNS.search(message):
            logger.info("IntentRouter: STATUS matched | input=%r", normalized)
            return RouteResult(IntentType.STATUS, None, normalized)

        # 5. Resolved keyword — immediate resolution shortcut
        if _RESOLVED_PATTERNS.search(message):
            logger.info("IntentRouter: RESOLVED_KEYWORD matched | input=%r", normalized)
            return RouteResult(IntentType.RESOLVED_KEYWORD, None, normalized)

        # 6. IT Issue — classify via intent_service (regex + optional LLM)
        category = self._classify_category(message)
        if category and category != "GENERAL":
            logger.info("IntentRouter: IT_ISSUE → %s | input=%r", category, normalized)
            return RouteResult(IntentType.IT_ISSUE, category, normalized)

        # 7. General conversation fallback
        logger.info("IntentRouter: GENERAL fallback | input=%r", normalized)
        return RouteResult(IntentType.GENERAL, None, normalized)

    def _classify_category(self, message: str) -> Optional[str]:
        """
        Delegate to intent_service.detect_intent() for category classification.
        Returns None on any error so callers can fall through to GENERAL.
        """
        try:
            from app.services.intent_service import detect_intent
            result = detect_intent(message)
            if isinstance(result, dict):
                return None
            return result or None
        except Exception as exc:
            logger.warning("IntentRouter._classify_category error: %s", exc)
            return None
