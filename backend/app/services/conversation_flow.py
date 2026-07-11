"""
conversation_flow.py
─────────────────────────────────────────────────────────────────────────────
Sprint 2 — Phase 1: Conversation Flow Engine

Responsible ONLY for managing, tracking, and validating state transitions
in the conversation lifecycle.

Prevents:
    - Skipping stages
    - Random ticket creation
    - Random approval execution
    - Infinite troubleshooting loops

Does NOT interact with DB, LLM/Gemini, ToolRouter, or FastAPI routes.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Optional

logger = logging.getLogger("it-agent-backend")


# ─────────────────────────────────────────────────────────────────────────────
# Conversation Stages Enum
# ─────────────────────────────────────────────────────────────────────────────

class ConversationStage(str, Enum):
    """Lifecycle stages for an enterprise IT support conversation."""
    NEW                  = "NEW"
    UNDERSTANDING        = "UNDERSTANDING"
    TROUBLESHOOTING      = "TROUBLESHOOTING"
    WAITING_CONFIRMATION = "WAITING_CONFIRMATION"
    EXECUTING_ACTION     = "EXECUTING_ACTION"
    VERIFYING_SOLUTION   = "VERIFYING_SOLUTION"
    RESOLVED             = "RESOLVED"
    ESCALATED            = "ESCALATED"


# ─────────────────────────────────────────────────────────────────────────────
# State machine validation rules
# ─────────────────────────────────────────────────────────────────────────────
_VALID_TRANSITIONS: dict[ConversationStage, set[ConversationStage]] = {
    ConversationStage.NEW: {
        ConversationStage.UNDERSTANDING,
        ConversationStage.TROUBLESHOOTING,
    },
    ConversationStage.UNDERSTANDING: {
        ConversationStage.TROUBLESHOOTING,
        ConversationStage.WAITING_CONFIRMATION,
        ConversationStage.ESCALATED,
    },
    ConversationStage.TROUBLESHOOTING: {
        ConversationStage.WAITING_CONFIRMATION,
        ConversationStage.VERIFYING_SOLUTION,
        ConversationStage.RESOLVED,
        ConversationStage.ESCALATED,
    },
    ConversationStage.WAITING_CONFIRMATION: {
        ConversationStage.EXECUTING_ACTION,
        ConversationStage.VERIFYING_SOLUTION,
        ConversationStage.TROUBLESHOOTING,
        ConversationStage.RESOLVED,
        ConversationStage.ESCALATED,
    },
    ConversationStage.EXECUTING_ACTION: {
        ConversationStage.VERIFYING_SOLUTION,
        ConversationStage.RESOLVED,
        ConversationStage.ESCALATED,
    },
    ConversationStage.VERIFYING_SOLUTION: {
        ConversationStage.RESOLVED,
        ConversationStage.TROUBLESHOOTING,
        ConversationStage.ESCALATED,
    },
    ConversationStage.RESOLVED: {
        ConversationStage.NEW,
        ConversationStage.UNDERSTANDING,
    },
    ConversationStage.ESCALATED: {
        ConversationStage.NEW,
        ConversationStage.UNDERSTANDING,
    },
}


# ─────────────────────────────────────────────────────────────────────────────
# Conversation Flow State Dataclass
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class ConversationFlowState:
    """Dataclass holding context variables for conversation flow lifecycle."""
    conversation_id: str
    stage: ConversationStage = ConversationStage.NEW
    issue_category: str = "GENERAL"
    attempt_number: int = 0
    max_attempts: int = 3
    waiting_for_confirmation: bool = False
    ticket_created: bool = False
    issue_resolved: bool = False
    last_question: Optional[str] = None
    notes: Optional[str] = None


# ─────────────────────────────────────────────────────────────────────────────
# Public API Methods
# ─────────────────────────────────────────────────────────────────────────────

def create_flow(
    conversation_id: str,
    issue_category: str = "GENERAL",
    max_attempts: int = 3,
) -> ConversationFlowState:
    """
    Instantiate a new conversation flow state context.
    """
    state = ConversationFlowState(
        conversation_id=conversation_id,
        stage=ConversationStage.NEW,
        issue_category=issue_category,
        max_attempts=max_attempts,
    )
    logger.info(
        "ConversationFlow: Initialized new flow for session %s (category=%s, max_attempts=%d)",
        conversation_id,
        issue_category,
        max_attempts,
    )
    return state


def move_to_stage(state: ConversationFlowState, target_stage: ConversationStage) -> bool:
    """
    Attempt to transition the conversation state machine to target_stage.

    Enforces strict transition rules. Returns True if successful.
    Raises ValueError for invalid transitions to prevent software logic errors.
    """
    current = state.stage
    if current == target_stage:
        return True  # No-op, already at target

    allowed = _VALID_TRANSITIONS.get(current, set())
    if target_stage not in allowed:
        logger.warning(
            "ConversationFlow: REJECTED invalid transition for session %s: %s -> %s (Allowed: %s)",
            state.conversation_id,
            current.value,
            target_stage.value,
            [s.value for s in allowed],
        )
        raise ValueError(
            f"Invalid transition: cannot move state machine from {current.value} to {target_stage.value}."
        )

    logger.info(
        "ConversationFlow: Transitioned session %s: %s -> %s",
        state.conversation_id,
        current.value,
        target_stage.value,
    )
    state.stage = target_stage
    return True


def can_execute_action(state: ConversationFlowState, approval_received: bool) -> bool:
    """
    Check if a privileged automation action is allowed to run.

    Requires:
      - Current stage is WAITING_CONFIRMATION
      - Employee has explicitly APPROVED (approval_received is True)
    """
    allowed = (state.stage == ConversationStage.WAITING_CONFIRMATION) and approval_received
    logger.info(
        "ConversationFlow: can_execute_action evaluated for session %s — result=%s (stage=%s, approved=%s)",
        state.conversation_id,
        allowed,
        state.stage.value,
        approval_received,
    )
    return allowed


def should_create_ticket(state: ConversationFlowState, employee_approved: bool) -> bool:
    """
    Check if ticket escalation to ServiceNow should be triggered.

    Requires:
      - Issue is unresolved
      - Troubleshooting attempts have reached or exceeded max_attempts
      - Employee explicitly approves ticket creation
    """
    should_escalate = (
        (not state.issue_resolved)
        and (state.attempt_number >= state.max_attempts)
        and employee_approved
    )
    logger.info(
        "ConversationFlow: should_create_ticket evaluated for session %s — result=%s "
        "(resolved=%s, attempts=%d/%d, approved=%s)",
        state.conversation_id,
        should_escalate,
        state.issue_resolved,
        state.attempt_number,
        state.max_attempts,
        employee_approved,
    )
    return should_escalate


def increment_attempt(state: ConversationFlowState) -> None:
    """
    Increment the troubleshooting attempt counter.
    """
    state.attempt_number += 1
    logger.info(
        "ConversationFlow: Incremented attempt for session %s (%d/%d)",
        state.conversation_id,
        state.attempt_number,
        state.max_attempts,
    )


def mark_resolved(state: ConversationFlowState) -> None:
    """
    Directly move to RESOLVED state and flag the issue as fixed.
    This acts as a terminal override and bypasses standard state transition checks.
    """
    state.stage = ConversationStage.RESOLVED
    state.issue_resolved = True
    logger.info("ConversationFlow: Marked session %s as RESOLVED", state.conversation_id)


def mark_escalated(state: ConversationFlowState) -> None:
    """
    Directly move to ESCALATED state and flag the ticket as created.
    This acts as a terminal override and bypasses standard state transition checks.
    """
    state.stage = ConversationStage.ESCALATED
    state.ticket_created = True
    logger.info("ConversationFlow: Marked session %s as ESCALATED", state.conversation_id)


def reset(state: ConversationFlowState) -> None:
    """
    Reset the conversation flow state variables back to initial defaults.
    """
    logger.info("ConversationFlow: Resetting flow state for session %s", state.conversation_id)
    state.stage = ConversationStage.NEW
    state.attempt_number = 0
    state.waiting_for_confirmation = False
    state.ticket_created = False
    state.issue_resolved = False
    state.last_question = None
    state.notes = None
