"""
troubleshooting_state_service.py
──────────────────────────────────────────────────────────────────────────────
Enterprise Troubleshooting State Manager for the Bridgestone IT Agent.

Responsibilities
----------------
• Maintain complete troubleshooting session state for the entire conversation.
• Track completed steps, failed steps, user answers, error codes, and results.
• Never repeat a step that has already been completed or attempted.
• Provide thread-safe in-memory storage (Phase 1).

Design contracts (MUST NOT be violated)
----------------------------------------
  ✓  State survives the entire conversation session — never reset mid-session.
  ✓  has_attempted() must be checked before guiding any troubleshooting action.
  ✓  State is updated via explicit mutation methods — never mutated directly.
  ✓  Thread-safe — a threading.Lock guards the in-memory session store.
  ✓  Designed for swap to Redis/DB in Phase 2 — storage is isolated behind
     get() / update() methods with no external references to _store.

Phase 2 upgrade path
---------------------
  Replace self._store (dict) with a Redis or database-backed store.
  The public API surface (create, get, update, record_step, ...) remains stable.
"""

from __future__ import annotations

import logging
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger("it-agent-backend")


# ── Enumerations ──────────────────────────────────────────────────────────────

class ResolutionStatus(str, Enum):
    UNRESOLVED         = "UNRESOLVED"
    PARTIALLY_RESOLVED = "PARTIALLY_RESOLVED"
    RESOLVED           = "RESOLVED"
    NEEDS_ADMIN        = "NEEDS_ADMIN"
    ESCALATED          = "ESCALATED"


class StepStatus(str, Enum):
    PENDING   = "pending"
    COMPLETED = "completed"
    FAILED    = "failed"
    SKIPPED   = "skipped"


# ── Data Contracts ────────────────────────────────────────────────────────────

@dataclass
class TroubleshootingStep:
    """A single troubleshooting action tracked within a session."""
    step_id: str
    instruction: str
    result: Optional[str]         = None
    status: StepStatus            = StepStatus.PENDING
    timestamp: datetime           = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "step_id":     self.step_id,
            "instruction": self.instruction,
            "result":      self.result,
            "status":      self.status.value,
            "timestamp":   self.timestamp.isoformat(),
        }


@dataclass
class TroubleshootingState:
    """
    Complete runtime state of a troubleshooting session.

    This dataclass is the single source of truth for everything the
    orchestrator knows about a session.  All fields are updated through
    TroubleshootingStateManager methods — never directly.
    """
    session_id: str
    current_issue: str
    strategy_domain: str

    completed_steps:  List[TroubleshootingStep] = field(default_factory=list)
    failed_steps:     List[TroubleshootingStep] = field(default_factory=list)
    current_step:     Optional[TroubleshootingStep] = None

    attempted_actions: List[str]        = field(default_factory=list)
    observed_results:  List[str]        = field(default_factory=list)
    error_codes:       List[str]        = field(default_factory=list)
    user_answers:      Dict[str, str]   = field(default_factory=dict)

    resolution_status: ResolutionStatus = ResolutionStatus.UNRESOLVED
    turn_count:        int              = 0

    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def to_summary(self) -> str:
        """Return a compact, human-readable state summary for prompt injection."""
        lines = [
            f"Issue: {self.current_issue}",
            f"Strategy: {self.strategy_domain}",
            f"Turns: {self.turn_count}",
            f"Status: {self.resolution_status.value}",
        ]
        if self.completed_steps:
            lines.append(
                f"Completed steps: {', '.join(s.instruction[:50] for s in self.completed_steps)}"
            )
        if self.failed_steps:
            lines.append(
                f"Failed steps: {', '.join(s.instruction[:50] for s in self.failed_steps)}"
            )
        if self.error_codes:
            lines.append(f"Error codes observed: {', '.join(self.error_codes)}")
        if self.user_answers:
            qa = "; ".join(f"{k}: {v}" for k, v in list(self.user_answers.items())[-5:])
            lines.append(f"User answers: {qa}")
        if self.observed_results:
            lines.append(f"Latest result: {self.observed_results[-1]}")
        return "\n".join(lines)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id":        self.session_id,
            "current_issue":     self.current_issue,
            "strategy_domain":   self.strategy_domain,
            "completed_steps":   [s.to_dict() for s in self.completed_steps],
            "failed_steps":      [s.to_dict() for s in self.failed_steps],
            "attempted_actions": self.attempted_actions,
            "error_codes":       self.error_codes,
            "user_answers":      self.user_answers,
            "resolution_status": self.resolution_status.value,
            "turn_count":        self.turn_count,
        }


# ── Service ───────────────────────────────────────────────────────────────────

class TroubleshootingStateManager:
    """
    Enterprise Troubleshooting State Manager.

    Thread-safe in-memory session store with a clean public API designed
    for a drop-in Phase 2 upgrade to Redis or database persistence.
    """

    def __init__(self) -> None:
        self._store: Dict[str, TroubleshootingState] = {}
        self._lock = threading.Lock()

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def create(
        self,
        session_id: str,
        issue: str,
        strategy_domain: str,
    ) -> TroubleshootingState:
        """
        Create a new TroubleshootingState for a session.

        If a state already exists for session_id it is returned unchanged
        (idempotent — safe to call on every orchestrator entry).
        """
        with self._lock:
            if session_id in self._store:
                logger.debug(
                    "[TroubleshootingStateManager]: State already exists for session '%s' — returning existing.",
                    session_id,
                )
                return self._store[session_id]

            state = TroubleshootingState(
                session_id=session_id,
                current_issue=issue,
                strategy_domain=strategy_domain,
            )
            self._store[session_id] = state
            logger.info(
                "[TroubleshootingStateManager]: Created state for session '%s', domain='%s'.",
                session_id, strategy_domain,
            )
            return state

    def get(self, session_id: str) -> Optional[TroubleshootingState]:
        """Return the state for session_id, or None if not found."""
        with self._lock:
            return self._store.get(session_id)

    def update(self, session_id: str, state: TroubleshootingState) -> None:
        """Persist an updated state back to the store."""
        state.updated_at = datetime.now()
        with self._lock:
            self._store[session_id] = state

    def get_or_create(
        self,
        session_id: str,
        issue: str,
        strategy_domain: str,
    ) -> TroubleshootingState:
        """Convenience method: return existing state or create a new one."""
        existing = self.get(session_id)
        if existing is not None:
            return existing
        return self.create(session_id, issue, strategy_domain)

    # ── Mutation Methods ──────────────────────────────────────────────────────

    def increment_turn(self, state: TroubleshootingState) -> TroubleshootingState:
        """Increment the conversation turn counter."""
        state.turn_count += 1
        state.updated_at = datetime.now()
        return state

    def record_step(
        self,
        state: TroubleshootingState,
        instruction: str,
        result: Optional[str] = None,
        success: bool = True,
    ) -> TroubleshootingState:
        """
        Record a troubleshooting step as completed or failed.

        Also adds the instruction to attempted_actions so has_attempted()
        can prevent the same step from being repeated.
        """
        step = TroubleshootingStep(
            step_id=str(uuid.uuid4())[:8],
            instruction=instruction,
            result=result,
            status=StepStatus.COMPLETED if success else StepStatus.FAILED,
        )
        if success:
            state.completed_steps.append(step)
        else:
            state.failed_steps.append(step)
        state.current_step = step

        # Add to attempted_actions for has_attempted() lookups
        action_key = instruction.lower().strip()[:80]
        if action_key not in state.attempted_actions:
            state.attempted_actions.append(action_key)

        if result:
            state.observed_results.append(result[:200])

        state.updated_at = datetime.now()
        logger.info(
            "[TroubleshootingStateManager]: Recorded step ('%s') status=%s for session '%s'.",
            instruction[:60], step.status.value, state.session_id,
        )
        return state

    def record_user_answer(
        self,
        state: TroubleshootingState,
        question: str,
        answer: str,
    ) -> TroubleshootingState:
        """
        Record a user's answer to a clarifying question.

        Extracts error codes automatically from answers.
        """
        state.user_answers[question] = answer

        # Extract error code patterns from the answer (e.g. "Error 619", "0x80070005")
        import re
        error_patterns = re.findall(
            r"\b(?:error\s+)?(?:0x[0-9a-fA-F]+|\d{3,6})\b", answer, re.IGNORECASE
        )
        for code in error_patterns:
            if code not in state.error_codes:
                state.error_codes.append(code)

        state.updated_at = datetime.now()
        return state

    def mark_resolved(self, state: TroubleshootingState) -> TroubleshootingState:
        """Mark the session as resolved."""
        state.resolution_status = ResolutionStatus.RESOLVED
        state.updated_at = datetime.now()
        logger.info(
            "[TroubleshootingStateManager]: Session '%s' marked RESOLVED after %d turns.",
            state.session_id, state.turn_count,
        )
        return state

    def mark_escalated(self, state: TroubleshootingState) -> TroubleshootingState:
        """Mark the session as escalated to ServiceNow."""
        state.resolution_status = ResolutionStatus.ESCALATED
        state.updated_at = datetime.now()
        logger.info(
            "[TroubleshootingStateManager]: Session '%s' marked ESCALATED after %d turns.",
            state.session_id, state.turn_count,
        )
        return state

    def mark_needs_admin(self, state: TroubleshootingState) -> TroubleshootingState:
        """Mark that the session requires admin intervention."""
        state.resolution_status = ResolutionStatus.NEEDS_ADMIN
        state.updated_at = datetime.now()
        return state

    def mark_partially_resolved(self, state: TroubleshootingState) -> TroubleshootingState:
        """Mark the session as partially resolved."""
        state.resolution_status = ResolutionStatus.PARTIALLY_RESOLVED
        state.updated_at = datetime.now()
        return state

    # ── Query Methods ─────────────────────────────────────────────────────────

    def has_attempted(self, state: TroubleshootingState, action: str) -> bool:
        """
        Return True if the given action instruction has already been attempted.

        Comparison is case-insensitive and truncated to 80 characters to
        handle slight wording variations from the LLM.
        """
        action_key = action.lower().strip()[:80]
        for attempted in state.attempted_actions:
            # Exact match or substantial overlap (first 40 chars match)
            if action_key == attempted or action_key[:40] == attempted[:40]:
                return True
        return False

    def session_count(self) -> int:
        """Return the number of active sessions in the store."""
        with self._lock:
            return len(self._store)
