"""
reasoning_service.py
──────────────────────────────────────────────────────────────────────────────
Enterprise Reasoning Engine for the Bridgestone IT Agent.

Responsibilities
----------------
• Build a structured decision prompt from ReasoningContext.
• Call AIProvider.generate_response() through the existing BaseAIProvider
  abstraction (provider-independent).
• Parse and validate the JSON response against DECISION_SCHEMA.
• Return a structured ReasoningResult — NEVER natural language.
• Apply deterministic fallback rules when the model fails or returns
  invalid JSON.

Design contracts (MUST NOT be violated)
----------------------------------------
  ✓  ReasoningResult NEVER contains user-facing text.
  ✓  Only calls BaseAIProvider.generate_response() — no direct LLM imports.
  ✓  JSON validation is strict — partial or malformed responses trigger fallback.
  ✓  Fallback rules are deterministic and always produce a valid ReasoningResult.
  ✓  Internal reasoning (raw_reasoning) is logged but NEVER forwarded to users.
  ✓  No business logic — only reasoning over supplied context.
"""

from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from app.services.ai_provider import BaseAIProvider
    from app.services.context_builder import ReasoningContext

logger = logging.getLogger("it-agent-backend")


# ── Decision Schema ───────────────────────────────────────────────────────────

# The LLM MUST return a JSON object matching these keys and types.
# Validated by _parse_and_validate() before any action is taken.
DECISION_SCHEMA: Dict[str, type] = {
    "next_action":            str,
    "confidence":             (int, float),
    "missing_information":    list,
    "selected_kb":            str,
    "selected_step":          str,
    "escalation":             bool,
    "reason_code":            str,
    "requires_confirmation":  bool,
}

VALID_NEXT_ACTIONS = {
    "ASK_QUESTION",
    "GUIDE_STEP",
    "RETRIEVE_KNOWLEDGE",
    "NEEDS_ADMIN",
    "ESCALATE",
    "RESOLVE",
    "WAIT",
}


# ── Enumerations ──────────────────────────────────────────────────────────────

class NextAction(str, Enum):
    ASK_QUESTION       = "ASK_QUESTION"       # gather more info from user
    GUIDE_STEP         = "GUIDE_STEP"         # guide user through next step
    RETRIEVE_KNOWLEDGE = "RETRIEVE_KNOWLEDGE" # KB fetch required before deciding
    NEEDS_ADMIN        = "NEEDS_ADMIN"        # requires privileged action
    ESCALATE           = "ESCALATE"           # create ServiceNow ticket
    RESOLVE            = "RESOLVE"            # issue is resolved
    WAIT               = "WAIT"               # waiting for user to complete step


# ── Data Contracts ────────────────────────────────────────────────────────────

@dataclass
class ReasoningResult:
    """
    Structured output of the ReasoningEngine.

    Contains only machine-readable decision fields.
    NEVER contains user-facing text — that is the responsibility of GeminiProvider.chat().
    """
    next_action:            NextAction
    confidence:             float
    missing_information:    List[str]
    selected_kb:            str
    selected_step:          str
    escalation:             bool
    reason_code:            str
    requires_confirmation:  bool
    raw_reasoning:          str         # LLM raw output — internal only, never shown to user
    is_fallback:            bool        # True if deterministic fallback was applied

    def to_dict(self) -> Dict[str, Any]:
        return {
            "next_action":           self.next_action.value,
            "confidence":            self.confidence,
            "missing_information":   self.missing_information,
            "selected_kb":           self.selected_kb,
            "selected_step":         self.selected_step,
            "escalation":            self.escalation,
            "reason_code":           self.reason_code,
            "requires_confirmation": self.requires_confirmation,
            "is_fallback":           self.is_fallback,
        }


# ── Service ───────────────────────────────────────────────────────────────────

class ReasoningEngine:
    """
    Enterprise ITSM Reasoning Engine.

    Calls the existing AI provider abstraction to obtain a structured
    decision, validates the JSON output, and returns a ReasoningResult.
    Falls back deterministically when the model fails.
    """

    # Maximum turns before forcing escalation consideration
    ESCALATION_TURN_THRESHOLD: int = 8

    # System instruction sent alongside the decision prompt
    SYSTEM_INSTRUCTION: str = (
        "You are an ITSM Reasoning Engine for an enterprise IT support system. "
        "Your role is to analyse the provided context and return a single valid JSON "
        "decision object. "
        "Output ONLY the JSON object. No markdown fences, no explanation, no extra text. "
        "All string values must be plain text. Boolean values must be true or false (lowercase)."
    )

    def __init__(self, ai_provider: "BaseAIProvider", context_builder=None) -> None:
        self._provider = ai_provider
        self._context_builder = context_builder  # injected to avoid circular import

    # ── Public API ────────────────────────────────────────────────────────────

    def reason(self, context: "ReasoningContext") -> ReasoningResult:
        """
        Produce a structured ReasoningResult for the given context.

        Flow:
        1. Build decision prompt via ContextBuilder.
        2. Call ai_provider.generate_response() through BaseAIProvider abstraction.
        3. Parse and validate JSON against DECISION_SCHEMA.
        4. Return ReasoningResult.
        5. On any failure → deterministic fallback.

        Args:
            context: ReasoningContext assembled by ContextBuilder.

        Returns:
            ReasoningResult — always valid, never raises.
        """
        t_start = time.monotonic()

        logger.info(
            ">>> ENTRY [ReasoningEngine.reason]: session turn=%d, category='%s', "
            "missing_evidence=%d, attempted=%d",
            context.turn_count,
            context.category,
            len(context.missing_evidence),
            len(context.attempted_actions),
        )

        # 1. Build the structured decision prompt
        try:
            prompt = self._build_decision_prompt(context)
        except Exception as exc:
            logger.warning("[ReasoningEngine]: Prompt build failed: %s — using fallback.", exc)
            return self._fallback_decision(context, reason="prompt_build_error")

        # 2. Call AI provider
        # generate_response(user_message, knowledge_context=None) — system instruction
        # is embedded at the top of the prompt string rather than a separate kwarg.
        raw_response: str = ""
        try:
            raw_response = self._provider.generate_response(
                user_message=prompt,
            )
            # generate_response may return a response object or a string
            if hasattr(raw_response, "text"):
                raw_response = raw_response.text
            raw_response = str(raw_response).strip()
        except Exception as exc:
            logger.warning(
                "[ReasoningEngine]: AI provider call failed (%s: %s) — using fallback.",
                type(exc).__name__, exc,
            )
            return self._fallback_decision(context, reason="provider_error")

        # 3. Parse and validate
        result = self._parse_and_validate(raw_response, context)
        if result is None:
            logger.warning(
                "[ReasoningEngine]: JSON validation failed — using fallback. "
                "Raw response (first 200 chars): %r",
                raw_response[:200],
            )
            result = self._fallback_decision(context, reason="schema_validation_error")

        elapsed_ms = int((time.monotonic() - t_start) * 1000)
        logger.info(
            "<<< EXIT [ReasoningEngine.reason]: next_action=%s, reason_code=%s, "
            "confidence=%.2f, is_fallback=%s, latency=%dms",
            result.next_action.value,
            result.reason_code,
            result.confidence,
            result.is_fallback,
            elapsed_ms,
        )

        # Internal reasoning logged but never forwarded to users
        if result.raw_reasoning:
            logger.debug(
                "[ReasoningEngine]: Internal reasoning (NOT for users): %s",
                result.raw_reasoning[:500],
            )

        return result

    # ── Prompt Construction ───────────────────────────────────────────────────

    def _build_decision_prompt(self, context: "ReasoningContext") -> str:
        """
        Build the structured decision prompt.

        The SYSTEM_INSTRUCTION is prepended to the prompt so it is included
        in the user_message passed to generate_response() — there is no
        separate system_instruction parameter on that method.

        Delegates to ContextBuilder if injected; otherwise builds inline.
        """
        if self._context_builder is not None:
            inner = self._context_builder.build_decision_prompt(context)
            return f"{self.SYSTEM_INSTRUCTION}\n\n{inner}"

        # Inline fallback prompt builder (used when ContextBuilder not injected)
        history_text = "\n".join(
            f"{'User' if t.get('role') == 'user' else 'Assistant'}: {(t.get('text') or t.get('content') or '')[:150]}"
            for t in (context.conversation_history or [])[-6:]
        )

        return (
            f"{self.SYSTEM_INSTRUCTION}\n\n"
            f"Category: {context.category}\n"
            f"Strategy: {context.strategy_name}\n"
            f"Issue: {context.issue_summary}\n\n"
            f"Required evidence:\n" +
            "\n".join(f"- {ev}" for ev in context.required_evidence) +
            f"\n\nMissing evidence:\n" +
            ("\n".join(f"- {ev}" for ev in context.missing_evidence) if context.missing_evidence else "None") +
            f"\n\nAttempted actions:\n" +
            ("\n".join(f"- {a}" for a in context.attempted_actions) if context.attempted_actions else "None") +
            f"\n\nSession state:\n{context.state_summary}"
            f"\nTurn count: {context.turn_count}"
            f"\n\nKB context:\n{context.retrieved_knowledge_summary or 'No KB found'}"
            f"\n\nConversation:\n{history_text or 'None'}"
            f"\n\nUser message: {context.user_message}"
            f"\n\nReturn ONLY this JSON:\n"
            + json.dumps({
                "next_action": "ASK_QUESTION|GUIDE_STEP|RETRIEVE_KNOWLEDGE|NEEDS_ADMIN|ESCALATE|RESOLVE|WAIT",
                "confidence": "0.0-1.0",
                "missing_information": ["list"],
                "selected_kb": "article_id or ''",
                "selected_step": "step or ''",
                "escalation": False,
                "reason_code": "short_code",
                "requires_confirmation": False,
            })
        )


    # ── JSON Parsing & Validation ─────────────────────────────────────────────

    def _parse_and_validate(
        self,
        raw: str,
        context: "ReasoningContext",
    ) -> Optional[ReasoningResult]:
        """
        Parse raw LLM output and validate against DECISION_SCHEMA.

        Returns:
            ReasoningResult if valid; None if validation fails.
        """
        if not raw:
            return None

        # Strip markdown fences if present
        clean = raw.strip()
        clean = re.sub(r"^```(?:json)?", "", clean, flags=re.IGNORECASE).strip()
        clean = re.sub(r"```$", "", clean).strip()

        # Find the first complete JSON object
        brace_start = clean.find("{")
        brace_end = clean.rfind("}")
        if brace_start == -1 or brace_end == -1:
            return None
        clean = clean[brace_start:brace_end + 1]

        try:
            data = json.loads(clean)
        except json.JSONDecodeError:
            return None

        if not isinstance(data, dict):
            return None

        # Validate required keys and types
        for key, expected_type in DECISION_SCHEMA.items():
            if key not in data:
                logger.debug("[ReasoningEngine._parse_and_validate]: Missing key '%s'.", key)
                return None
            if not isinstance(data[key], expected_type):
                # Allow int where float is expected
                if expected_type == (int, float) and isinstance(data[key], (int, float)):
                    pass
                else:
                    logger.debug(
                        "[ReasoningEngine._parse_and_validate]: Key '%s' has wrong type %s (expected %s).",
                        key, type(data[key]).__name__, expected_type,
                    )
                    return None

        # Validate next_action is a known value
        next_action_str = str(data.get("next_action", "")).upper().strip()
        if next_action_str not in VALID_NEXT_ACTIONS:
            logger.debug(
                "[ReasoningEngine._parse_and_validate]: Invalid next_action '%s'.",
                next_action_str,
            )
            return None

        # Normalise confidence to [0.0, 1.0]
        confidence = float(data.get("confidence", 0.5))
        confidence = max(0.0, min(1.0, confidence))

        return ReasoningResult(
            next_action=NextAction(next_action_str),
            confidence=confidence,
            missing_information=list(data.get("missing_information", [])),
            selected_kb=str(data.get("selected_kb", "")).strip(),
            selected_step=str(data.get("selected_step", "")).strip(),
            escalation=bool(data.get("escalation", False)),
            reason_code=str(data.get("reason_code", "LLM_DECISION")).strip(),
            requires_confirmation=bool(data.get("requires_confirmation", False)),
            raw_reasoning=raw,
            is_fallback=False,
        )

    # ── Deterministic Fallback ────────────────────────────────────────────────

    def _fallback_decision(
        self,
        context: "ReasoningContext",
        reason: str = "fallback",
    ) -> ReasoningResult:
        """
        Apply deterministic fallback rules when the LLM fails.

        Rules (in priority order):
        1. Turn count > ESCALATION_TURN_THRESHOLD + unresolved → ESCALATE
        2. Missing required evidence → ASK_QUESTION
        3. KB available + evidence complete → GUIDE_STEP
        4. Default → ASK_QUESTION
        """
        logger.info(
            "[ReasoningEngine._fallback_decision]: Applying deterministic fallback. reason='%s', "
            "turn=%d, missing_evidence=%d",
            reason, context.turn_count, len(context.missing_evidence),
        )

        # Rule 1: Prolonged unresolved session → escalate
        if context.turn_count > self.ESCALATION_TURN_THRESHOLD:
            return ReasoningResult(
                next_action=NextAction.ESCALATE,
                confidence=0.80,
                missing_information=[],
                selected_kb="",
                selected_step="",
                escalation=True,
                reason_code="STEPS_EXHAUSTED",
                requires_confirmation=True,
                raw_reasoning=f"[fallback] {reason}",
                is_fallback=True,
            )

        # Rule 2: Missing evidence → ask the first missing item
        if context.missing_evidence:
            return ReasoningResult(
                next_action=NextAction.ASK_QUESTION,
                confidence=0.60,
                missing_information=context.missing_evidence[:3],
                selected_kb="",
                selected_step="",
                escalation=False,
                reason_code="MISSING_EVIDENCE",
                requires_confirmation=False,
                raw_reasoning=f"[fallback] {reason}",
                is_fallback=True,
            )

        # Rule 3: KB available + evidence complete → guide a step
        if context.retrieved_knowledge_summary and not context.attempted_actions:
            return ReasoningResult(
                next_action=NextAction.GUIDE_STEP,
                confidence=0.70,
                missing_information=[],
                selected_kb="",
                selected_step="",
                escalation=False,
                reason_code="KB_AVAILABLE",
                requires_confirmation=False,
                raw_reasoning=f"[fallback] {reason}",
                is_fallback=True,
            )

        # Rule 4: Default → ask a question
        return ReasoningResult(
            next_action=NextAction.ASK_QUESTION,
            confidence=0.50,
            missing_information=["Please describe the issue in more detail."],
            selected_kb="",
            selected_step="",
            escalation=False,
            reason_code="DEFAULT_ASK",
            requires_confirmation=False,
            raw_reasoning=f"[fallback] {reason}",
            is_fallback=True,
        )
