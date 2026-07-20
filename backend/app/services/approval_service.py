"""
Approval Service
================
Handles:
1. (New API) Local deterministic parsing of user confirmations (APPROVED, REJECTED, UNKNOWN)
   via detect_approval().
2. (Legacy API) Detection of privileged actions, creation and storage of approval
   entries, status updates, and audit logging.

All functions use defensive fallbacks.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass
from enum import Enum
import logging
import re
from typing import Dict, Any, Optional

logger = logging.getLogger("it-agent-backend")

# ─────────────────────────────────────────────────────────────────────────────
# New Sprint 1 Phase 3 Types
# ─────────────────────────────────────────────────────────────────────────────

class ApprovalStatus(str, Enum):
    """Possible outcomes of approval/rejection analysis."""
    UNKNOWN  = "UNKNOWN"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


@dataclass(frozen=True)
class ApprovalResult:
    """Detailed result of approval detection."""
    status: ApprovalStatus
    confidence: float
    matched_phrase: str
    reason: str


# ─────────────────────────────────────────────────────────────────────────────
# Phrase tables for deterministic detection
# ─────────────────────────────────────────────────────────────────────────────

_EXPLICIT_APPROVALS = {
    "please do", "go ahead", "do it", "approved", "approve", "confirm", "proceed",
}

_WEAK_APPROVALS = {
    "yes", "y", "yeah", "yep", "ok", "okay", "sure", "you can", "continue",
}

_EXPLICIT_REJECTIONS = {
    "no", "nope", "cancel", "don't", "do not", "stop", "abort", "reject", "never mind",
    "still not working", "not working", "not", "failed", "did not work",
}

_WEAK_REJECTIONS = {
    "not now", "later",
}

_AMBIGUOUS_PHRASES = {
    "thanks", "thank you", "hi", "hello", "good morning", "how are you", "maybe", "possibly", "not sure",
}


def _normalize(text: str) -> str:
    """Normalize user input: lowercase, strip punctuation (except apostrophes), trim spaces."""
    cleaned = text.lower().strip()
    # Keep alphanumeric characters, spaces, and apostrophes
    cleaned = re.sub(r"[^\w\s']", "", cleaned)
    # Collapse multiple spaces
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def detect_approval(user_message: str) -> ApprovalResult:
    """
    Deterministically analyze the user's latest message to detect approval,
    rejection, or ambiguous responses.

    Returns an ApprovalResult containing the status, confidence, matched phrase,
    and rationale. Does not perform database operations or call external APIs.
    """
    normalized = _normalize(user_message)
    logger.info("ApprovalService: Analyzing normalized message: '%s'", normalized)

    # 1. Handle exact match or prefix/substring checks for multi-word ambiguous phrases first
    for phrase in _AMBIGUOUS_PHRASES:
        if normalized == phrase or normalized.startswith(phrase + " "):
            return ApprovalResult(
                status=ApprovalStatus.UNKNOWN,
                confidence=0.0,
                matched_phrase=phrase,
                reason=f"Matched ambiguous phrase '{phrase}'",
            )

    # 2. Check for explicit rejections (multi-word first)
    for phrase in sorted(_EXPLICIT_REJECTIONS, key=len, reverse=True):
        if normalized == phrase or f" {phrase} " in f" {normalized} " or normalized.startswith(phrase + " ") or normalized.endswith(" " + phrase):
            return ApprovalResult(
                status=ApprovalStatus.REJECTED,
                confidence=1.0,
                matched_phrase=phrase,
                reason=f"Matched explicit rejection phrase '{phrase}'",
            )

    # 3. Check for weak rejections
    for phrase in _WEAK_REJECTIONS:
        if normalized == phrase or f" {phrase} " in f" {normalized} ":
            return ApprovalResult(
                status=ApprovalStatus.REJECTED,
                confidence=0.80,
                matched_phrase=phrase,
                reason=f"Matched weak rejection phrase '{phrase}'",
            )

    # 4. Check for explicit approvals (multi-word first)
    for phrase in sorted(_EXPLICIT_APPROVALS, key=len, reverse=True):
        if normalized == phrase or f" {phrase} " in f" {normalized} " or normalized.startswith(phrase + " ") or normalized.endswith(" " + phrase):
            return ApprovalResult(
                status=ApprovalStatus.APPROVED,
                confidence=0.98,
                matched_phrase=phrase,
                reason=f"Matched explicit approval phrase '{phrase}'",
            )

    # 5. Check for weak approvals
    for phrase in _WEAK_APPROVALS:
        if normalized == phrase or f" {phrase} " in f" {normalized} ":
            confidence = 0.90 if phrase in {"yes", "yeah", "yep"} else 0.80
            return ApprovalResult(
                status=ApprovalStatus.APPROVED,
                confidence=confidence,
                matched_phrase=phrase,
                reason=f"Matched weak approval phrase '{phrase}'",
            )

    # 6. Fallback to single-token checks if no substring/phrase matched
    tokens = normalized.split()
    for t in tokens:
        if t in _EXPLICIT_REJECTIONS:
            return ApprovalResult(
                status=ApprovalStatus.REJECTED,
                confidence=0.95,
                matched_phrase=t,
                reason=f"Matched explicit rejection token '{t}'",
            )
        if t in _EXPLICIT_APPROVALS:
            return ApprovalResult(
                status=ApprovalStatus.APPROVED,
                confidence=0.95,
                matched_phrase=t,
                reason=f"Matched explicit approval token '{t}'",
            )
        if t in _WEAK_APPROVALS:
            return ApprovalResult(
                status=ApprovalStatus.APPROVED,
                confidence=0.80,
                matched_phrase=t,
                reason=f"Matched weak approval token '{t}'",
            )

    return ApprovalResult(
        status=ApprovalStatus.UNKNOWN,
        confidence=0.0,
        matched_phrase="",
        reason="No matching phrases or tokens found",
    )


# ─────────────────────────────────────────────────────────────────────────────
# Legacy API implementation for backward compatibility
# ─────────────────────────────────────────────────────────────────────────────

# Privileged action keyword list
PRIVILEGED_KEYWORDS = [
    "restart",
    "reset_password",
    "password_reset",
    "change_configuration",
    "delete",
    "disable_account",
    "enable_account",
    "unlock_account",
    "force_logout",
    "revoke_access",
    "grant_access",
    "escalate",
    "modify_permissions",
    "clear_cache",
    "reboot",
    "vpn_access",
    "vpn_reset",
    "vpn_access_restoration",
    "software_installation",
]

# Volatile in-memory fallback (session_id -> approval dict)
_approval_store: Dict[str, Dict[str, Any]] = {}


def detect_privileged(state: Dict[str, Any]) -> bool:
    """
    Returns True if the recommended_action in state matches any privileged keyword.
    Also checks if `approval_required` was explicitly set True by an upstream node.
    """
    if state.get("approval_required"):
        return True

    recommended = (state.get("recommended_action") or "").lower()
    decision = (state.get("decision") or "").upper()

    if decision == "EXECUTE_ACTION" and any(kw in recommended for kw in PRIVILEGED_KEYWORDS):
        return True

    return False


def create_approval_entry(session_id: str, action: str) -> Dict[str, Any]:
    """
    Persists a PENDING approval entry for the given session and action.
    """
    entry = {
        "session_id": session_id,
        "recommended_action": action,
        "approval_status": "PENDING",
        "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
    }
    _approval_store[session_id] = entry

    try:
        from app.services.audit_service import log_approval
        log_approval(
            session_id=session_id,
            recommended_action=action,
            approval_status="PENDING",
        )
    except Exception:
        logger.exception("Approval Service: DB persist failed, using in-memory")

    logger.info(
        "Approval Service: Created PENDING entry for session=%s action=%s",
        session_id, action,
    )
    return entry


def update_approval(session_id: str, status: str) -> Dict[str, Any]:
    """
    Updates approval status (APPROVED / REJECTED) for a session.
    """
    status = status.upper().strip()
    existing = _approval_store.get(session_id, {})
    action = existing.get("recommended_action", "")
    entry = {
        "session_id": session_id,
        "recommended_action": action,
        "approval_status": status,
        "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
    }
    _approval_store[session_id] = entry

    try:
        from app.services.audit_service import log_approval
        log_approval(
            session_id=session_id,
            recommended_action=action,
            approval_status=status,
        )
    except Exception:
        logger.exception("Approval Service: DB update failed, using in-memory")

    logger.info(
        "Approval Service: Updated approval status=%s for session=%s",
        status, session_id,
    )
    return entry


def audit_approval(session_id: str, action: str, status: str) -> None:
    """
    Writes a dedicated approval audit trace via audit_service.log_agent_trace.
    """
    try:
        from app.services.audit_service import log_agent_trace
        log_agent_trace(
            session_id=session_id,
            agent_name="Approval Agent",
            output={
                "recommended_action": action,
                "approval_status": status,
                "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
            },
        )
    except Exception:
        logger.exception("Approval Service: Failed to write audit trace")


def get_approval(session_id: str) -> Optional[Dict[str, Any]]:
    """Returns the latest approval record for a session (in-memory)."""
    return _approval_store.get(session_id)
