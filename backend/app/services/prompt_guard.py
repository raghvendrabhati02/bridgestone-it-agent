"""
prompt_guard.py
──────────────────────────────────────────────────────────────────────────────
Phase 4: Risk-Based Prompt Injection Protection

Implements a three-tier risk classifier for user-supplied text before it
enters the AI pipeline. The design follows the user's approved approach:

  HIGH confidence attack  → reject (HTTP 400) + audit log
  MEDIUM confidence       → sanitize suspicious fragment, continue
  LOW confidence          → allow, but emit a structured warning log

Architecture
────────────
  • Pattern matching is done in two passes:
      Pass 1: exact / anchored patterns  (HIGH)
      Pass 2: contextual / fuzzy patterns (MEDIUM)
  • Both passes are case-insensitive.
  • No blocking on individual legitimate words (e.g. "system", "act").
  • Blocking requires the FULL pattern match, not just a substring keyword.

Patterns
────────
  HIGH (confirmed attack attempt):
    - "ignore (all|previous|your) instructions"
    - "disregard (all|previous|your) instructions"
    - "<system>" / "[SYSTEM]" / "###SYSTEM" tokens that look like prompt delimiters
    - "forget everything" / "forget your (previous|prior) instructions"
    - "you are now [DAN|GPT|god mode|jailbreak]"
    - "jailbreak" as a standalone directive (not in a question about security)
    - "do anything now" (DAN prompt)

  MEDIUM (suspicious, sanitize):
    - "act as [^.]{0,30} without restrictions"
    - "pretend (you are|to be) [^.]{0,30}"
    - "override (safety|content) (filter|policy)"
    - "your new instructions are"
    - "from now on you (must|will|should|are)"
    - "[INST]" / "<<SYS>>" (LLaMA/Mixtral injection markers)

Usage
─────
    from app.services.prompt_guard import scan_message, PromptInjectionError

    try:
        safe_message = scan_message(user_input)
    except PromptInjectionError as e:
        # Return HTTP 400 and log the attempt
        raise HTTPException(status_code=400, detail=str(e))

    # safe_message is either the original or sanitized version
    ai_response = provider.chat(safe_message)
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional

logger = logging.getLogger("it-agent-backend")


# ──────────────────────────────────────────────────────────────────────────────
# Risk classification
# ──────────────────────────────────────────────────────────────────────────────

class InjectionRisk(str, Enum):
    NONE   = "none"
    LOW    = "low"
    MEDIUM = "medium"
    HIGH   = "high"


@dataclass
class ScanResult:
    risk:            InjectionRisk
    matched_pattern: Optional[str]
    safe_message:    str            # original or sanitized
    was_sanitized:   bool = False
    audit_required:  bool = False


class PromptInjectionError(ValueError):
    """Raised on HIGH-confidence injection attempts. Callers should return HTTP 400."""
    pass


# ──────────────────────────────────────────────────────────────────────────────
# Pattern registry
# ──────────────────────────────────────────────────────────────────────────────

# Each entry: (compiled regex, human-readable label)
_HIGH_PATTERNS: List[tuple] = [
    (re.compile(r"\bignore\s+(?:(?:all|previous|your|prior|any)\s+){1,3}instructions?\b", re.I), "ignore_instructions"),
    (re.compile(r"\bdisregard\s+(?:(?:all|previous|your|prior|any)\s+){1,3}instructions?\b", re.I), "disregard_instructions"),
    (re.compile(r"\bforget\s+(everything|your\s+(previous|prior|all)\s+instructions?)\b", re.I), "forget_instructions"),
    (re.compile(r"\byou\s+are\s+now\s+(dan|god\s*mode|jailbreak|uncensored|unrestricted)\b", re.I), "you_are_now_jailbreak"),
    (re.compile(r"\bdo\s+anything\s+now\b", re.I), "DAN_do_anything_now"),
    (re.compile(r"<\s*/?system\s*>", re.I), "system_tag_delimiter"),
    (re.compile(r"\[SYSTEM\]", re.I), "system_bracket_delimiter"),
    (re.compile(r"###\s*system\b", re.I), "system_hash_delimiter"),
    (re.compile(r"\bjailbreak\s+(this|the|ai|model|assistant|system|chatbot)\b", re.I), "jailbreak_directive"),
    (re.compile(r"\bnew\s+instructions?\s*:\s*.{0,10}ignore\b", re.I), "new_instructions_ignore"),
]

_MEDIUM_PATTERNS: List[tuple] = [
    (re.compile(r"\bact\s+as\b.{0,40}\bwithout\s+(any\s+)?(restrictions?|limits?|rules?|filters?)\b", re.I), "act_as_no_restrictions"),
    (re.compile(r"\bpretend\s+(you\s+are|to\s+be)\b.{0,60}", re.I), "pretend_to_be"),
    (re.compile(r"\boverride\s+(safety|content|ethical)\s+(filter|policy|guidelines?|rules?)\b", re.I), "override_safety_policy"),
    (re.compile(r"\byour\s+new\s+instructions?\s+are\b", re.I), "your_new_instructions"),
    (re.compile(r"\bfrom\s+now\s+on\s+you\s+(must|will|should|are)\b", re.I), "from_now_on_directive"),
    (re.compile(r"\[INST\]", re.I), "llama_inst_delimiter"),
    (re.compile(r"<<SYS>>", re.I), "llama_sys_delimiter"),
    (re.compile(r"\bsystem\s+prompt\s*:", re.I), "system_prompt_colon"),
]

# Fragment-removal patterns used to sanitize MEDIUM matches
_SANITIZE_PATTERNS: List[re.Pattern] = [
    re.compile(p.pattern, re.I) for p, _ in _MEDIUM_PATTERNS
]


# ──────────────────────────────────────────────────────────────────────────────
# Core scanner
# ──────────────────────────────────────────────────────────────────────────────

def scan_message(message: str, correlation_id: str = "") -> str:
    """
    Scan a user message for prompt injection attempts.

    Returns:
        The original message (NONE/LOW risk) or a sanitized version (MEDIUM risk).

    Raises:
        PromptInjectionError: on HIGH-confidence injection.
    """
    result = _classify(message)

    _emit_log(result, correlation_id)

    if result.risk == InjectionRisk.HIGH:
        raise PromptInjectionError(
            "Your request was flagged as potentially malicious. "
            "Please rephrase and try again."
        )

    return result.safe_message


def scan_rag_context(context: str) -> str:
    """
    Sanitize RAG knowledge-base context before injecting it into the AI prompt.
    Strips instruction-like fragments that could hijack the model.
    """
    sanitized = context
    for pattern in _SANITIZE_PATTERNS:
        sanitized = pattern.sub("[content filtered]", sanitized)
    for pattern, _ in _HIGH_PATTERNS:
        sanitized = pattern.sub("[content filtered]", sanitized)
    return sanitized


# ──────────────────────────────────────────────────────────────────────────────
# Classification engine
# ──────────────────────────────────────────────────────────────────────────────

def _classify(message: str) -> ScanResult:
    # Pass 1 — HIGH confidence
    for pattern, label in _HIGH_PATTERNS:
        if pattern.search(message):
            return ScanResult(
                risk=InjectionRisk.HIGH,
                matched_pattern=label,
                safe_message=message,
                was_sanitized=False,
                audit_required=True,
            )

    # Pass 2 — MEDIUM confidence → sanitize
    for pattern, label in _MEDIUM_PATTERNS:
        if pattern.search(message):
            sanitized = _sanitize(message)
            return ScanResult(
                risk=InjectionRisk.MEDIUM,
                matched_pattern=label,
                safe_message=sanitized,
                was_sanitized=True,
                audit_required=False,
            )

    # LOW or NONE — return as-is
    # Heuristic: very long messages (>4000 chars) get a LOW flag for monitoring
    if len(message) > 4000:
        return ScanResult(
            risk=InjectionRisk.LOW,
            matched_pattern="message_length_heuristic",
            safe_message=message,
            was_sanitized=False,
            audit_required=False,
        )

    return ScanResult(
        risk=InjectionRisk.NONE,
        matched_pattern=None,
        safe_message=message,
        was_sanitized=False,
        audit_required=False,
    )


def _sanitize(message: str) -> str:
    """Remove MEDIUM-risk fragments from the message."""
    result = message
    for pattern in _SANITIZE_PATTERNS:
        result = pattern.sub("[removed]", result)
    return result.strip()


# ──────────────────────────────────────────────────────────────────────────────
# Logging
# ──────────────────────────────────────────────────────────────────────────────

def _emit_log(result: ScanResult, correlation_id: str) -> None:
    if result.risk == InjectionRisk.NONE:
        return

    if result.risk == InjectionRisk.HIGH:
        logger.warning(
            "[PromptGuard] HIGH-confidence injection blocked | "
            "pattern=%s correlation_id=%s",
            result.matched_pattern, correlation_id,
            extra={
                "prompt_guard_risk": result.risk,
                "prompt_guard_pattern": result.matched_pattern,
                "correlation_id": correlation_id,
                "audit_required": True,
            },
        )
    elif result.risk == InjectionRisk.MEDIUM:
        logger.warning(
            "[PromptGuard] MEDIUM-confidence injection sanitized | "
            "pattern=%s correlation_id=%s",
            result.matched_pattern, correlation_id,
            extra={
                "prompt_guard_risk": result.risk,
                "prompt_guard_pattern": result.matched_pattern,
                "correlation_id": correlation_id,
            },
        )
    else:  # LOW
        logger.info(
            "[PromptGuard] LOW-confidence flag (monitoring only) | "
            "pattern=%s correlation_id=%s",
            result.matched_pattern, correlation_id,
            extra={
                "prompt_guard_risk": result.risk,
                "prompt_guard_pattern": result.matched_pattern,
                "correlation_id": correlation_id,
            },
        )
