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
    GREETING         = "GREETING"


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
    r"|\b(create|create\s+it|yes\s+create|yes\s+please\s+create|please\s+create)\b"
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
    r"reset\s+chat|reset\s+conversation|new\s+conversation|clear\s+conversation|new\s+session|clear\s+chat"
    r"|restart\s+and\s+cancel)\b"
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

_GREETING_PATTERNS = re.compile(
    r"^(\s*(hi|hello|hey|good\s+morning|good\s+evening|greetings|howdy|yo|hiya|hello\s+there|hi\s+there)\s*)[.,!?]?$",
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

def _detect_explicit_category(message: str, current_category: Optional[str] = None) -> Optional[str]:
    text = message.lower().strip()
    # We map category names to their keywords
    categories = {
        "VPN": ["vpn", "globalprotect", "global protect", "remote access", "anyconnect", "cisco"],
        "OUTLOOK": ["outlook", "email", "mailbox", "exchange", "mail"],
        "PRINTER": ["printer", "printing", "print", "scanner"],
        "TEAMS": ["teams", "microsoft teams"],
        "WIFI": ["wifi", "wi-fi", "wireless", "bs-guest", "bsguest"],
        "PASSWORD_RESET": ["password", "reset password", "forgot password", "account locked"],
        "SOFTWARE_INSTALLATION": ["software", "install", "application", "setup", "uninstall", "download", "adobe", "citrix", "vscode"],
        "SAP": ["sap"]
    }
    
    # First, check for categories OTHER than current_category
    for cat, keywords in categories.items():
        if current_category and cat.upper() == current_category.upper():
            continue
        if any(kw in text for kw in keywords):
            return cat
            
    # If no other category is found, check current_category
    if current_category:
        keywords = categories.get(current_category.upper())
        if keywords and any(kw in text for kw in keywords):
            return current_category.upper()
            
    return None


def _is_generic_followup(message: str) -> bool:
    text = message.lower().strip()
    text = re.sub(r"\s+", " ", text)
    # List of generic words/phrases
    generic_words = {
        "yes", "no", "ok", "okay", "done", "not working", "tried", "still", "still not working",
        "working", "fixed", "disabled", "offline", "online", "not loading", "loading", "error", 
        "failed", "success", "cancel", "abort", "stop", "never mind", "forget it", "discard", 
        "quit", "exit", "y", "n", "it works", "it is working", "all good", "sorted", "help",
        "restart", "start over", "new issue", "reset"
    }
    if text in generic_words:
        return True
    # If the message is short and contains only words from generic list
    words = text.split()
    if len(words) <= 3:
        word_set = {
            "yes", "no", "ok", "okay", "not", "working", "work", "fixed", "disabled", 
            "offline", "online", "loading", "error", "failed", "success", "done", 
            "cancel", "abort", "stop", "never", "mind", "forget", "it", "discard", 
            "quit", "exit", "y", "n", "still", "all", "good", "sorted", "help", 
            "restart", "start", "over", "new", "issue", "reset", "this", "that", 
            "is", "does", "not", "tried"
        }
        if all(w in word_set for w in words):
            return True
    return False


# ─────────────────────────────────────────────────────────────────────────────
# Enterprise Intent Router
# ─────────────────────────────────────────────────────────────────────────────

class IntentRouter:
    """
    Stateless, deterministic intent router.
    Regex patterns are checked in strict priority order before any LLM call.
    """

    def route(self, message: str, conversation_locked: bool = False, current_category: Optional[str] = None) -> RouteResult:
        import time
        from app.core.logging_context import request_id_ctx, session_id_ctx
        t0 = time.time()
        req_id = request_id_ctx.get() or "N/A"
        sess_id = session_id_ctx.get() or "N/A"
        logger.info(">>> TRACE PIPELINE: IntentRouter.route Start | Request ID: %s | Session ID: %s | Message: %r | Locked: %s | Current Category: %s", req_id, sess_id, message, conversation_locked, current_category)
        try:
            res = self._route_internal(message, conversation_locked, current_category)
            elapsed = (time.time() - t0) * 1000
            logger.info("<<< TRACE PIPELINE: IntentRouter.route End | Request ID: %s | Session ID: %s | Elapsed: %.2f ms | Category: %s | Intent: %s", req_id, sess_id, elapsed, res.category, res.intent.value)
            return res
        except Exception as exc:
            elapsed = (time.time() - t0) * 1000
            logger.error("!!! TRACE PIPELINE ERROR: IntentRouter.route | Request ID: %s | Session ID: %s | Elapsed: %.2f ms | Error: %s", req_id, sess_id, elapsed, exc, exc_info=True)
            raise

    def _route_internal(self, message: str, conversation_locked: bool = False, current_category: Optional[str] = None) -> RouteResult:
        normalized = normalize(message)

        # 1. Ticket command — highest priority
        if _TICKET_PATTERNS.search(message):
            logger.info("IntentRouter: TICKET_COMMAND matched | input=%r", normalized)
            try:
                cat = self._classify_category(message, current_category)
            except TypeError:
                cat = self._classify_category(message)
            return RouteResult(IntentType.TICKET_COMMAND, cat, normalized)

        # Generic reply guard: if conversation is locked and it's a generic follow-up, do NOT reclassify
        if conversation_locked and _is_generic_followup(message):
            logger.info("IntentRouter: Generic follow-up matched during locked session | input=%r", normalized)
            if _RESOLVED_PATTERNS.search(message):
                return RouteResult(IntentType.RESOLVED_KEYWORD, None, normalized)
            if _CANCEL_PATTERNS.search(message):
                return RouteResult(IntentType.CANCEL, None, normalized)
            if _RESTART_PATTERNS.search(message):
                return RouteResult(IntentType.RESTART, None, normalized)
            return RouteResult(IntentType.GENERAL, None, normalized)

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

        # 5.5 Standalone greeting detection
        if _GREETING_PATTERNS.search(message):
            logger.info("IntentRouter: GREETING matched | input=%r", normalized)
            return RouteResult(IntentType.GREETING, None, normalized)

        # 6. IT Issue — classify via intent_service (regex + optional LLM)
        try:
            category = self._classify_category(message, current_category)
        except TypeError:
            category = self._classify_category(message)
        if category and category != "GENERAL":
            logger.info("IntentRouter: IT_ISSUE → %s | input=%r", category, normalized)
            return RouteResult(IntentType.IT_ISSUE, category, normalized)

        # 7. General conversation fallback
        logger.info("IntentRouter: GENERAL fallback | input=%r", normalized)
        return RouteResult(IntentType.GENERAL, None, normalized)

    def _classify_category(self, message: str, current_category: Optional[str] = None) -> Optional[str]:
        """
        Delegate to intent_service.detect_intent() for category classification.
        Checks deterministic local scanner first before using LLM.
        Returns None on any error so callers can fall through to GENERAL.
        """
        explicit = _detect_explicit_category(message, current_category)
        if explicit:
            logger.info("IntentRouter: Explicit category detected locally: %s", explicit)
            return explicit

        import time
        t0 = time.time()
        logger.info(">>> TRACE STAGE: IntentRouter._classify_category Start | Msg: %s", message)
        try:
            from app.services.intent_service import detect_intent
            result = detect_intent(message)
            elapsed = (time.time() - t0) * 1000
            if isinstance(result, dict):
                logger.info("<<< TRACE STAGE: IntentRouter._classify_category End | Result: None (dict returned) | Elapsed: %.2f ms", elapsed)
                return None
            logger.info("<<< TRACE STAGE: IntentRouter._classify_category End | Result: %s | Elapsed: %.2f ms", result, elapsed)
            return result or None
        except Exception as exc:
            elapsed = (time.time() - t0) * 1000
            logger.warning("!!! TRACE STAGE ERROR: IntentRouter._classify_category failed | Elapsed: %.2f ms | Error: %s", elapsed, exc)
            return None
