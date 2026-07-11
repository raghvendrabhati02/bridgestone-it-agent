"""
conversation_state.py
─────────────────────────────────────────────────────────────────────────────
Sprint 1 — Step 1

Defines the canonical conversation state model for the Bridgestone IT Agent.

Responsibilities
────────────────
  ✓  ConversationStateEnum  — all valid lifecycle states
  ✓  ConversationContext    — full dataclass for a single conversation session
  ✓  Serialisation helpers  — to_dict() / from_dict()
  ✓  Reset utility          — reset()

Design contract (MUST NOT be violated)
───────────────────────────────────────
  ✗  No business logic
  ✗  No FastAPI / HTTP
  ✗  No database access
  ✗  No LangGraph
  ✗  No external dependencies (stdlib only)
  ✗  Does NOT import any other app module

Only imports: enum, dataclasses, logging, datetime, typing (all stdlib).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger("it-agent-backend")


# ─────────────────────────────────────────────────────────────────────────────
# Conversation lifecycle states
# ─────────────────────────────────────────────────────────────────────────────

class ConversationStateEnum(str, Enum):
    """
    All valid states in the IT Support conversation lifecycle.

    Inherits from ``str`` so instances serialise directly to their string
    value (e.g. in JSON / dict conversions) without extra encoding.

    State Descriptions
    ──────────────────
    NEW_ISSUE
        The session has just started. The issue has been received but not yet
        understood. Initial triage questions should be asked.

    UNDERSTANDING
        The orchestrator is gathering information from the employee through
        targeted follow-up questions to understand the root cause.

    TROUBLESHOOTING
        Sufficient information has been collected. The orchestrator is now
        running diagnostics and suggesting self-service resolution steps.

    READY_FOR_ACTION
        The orchestrator has determined that an automated tool action is
        available and appropriate. Awaiting employee confirmation or auto-execution.

    WAITING_CONFIRMATION
        A tool action has been proposed (e.g. password reset, software install).
        The orchestrator is waiting for the employee to explicitly confirm.

    EXECUTING_ACTION
        ToolRouter has been invoked. The action is currently being executed
        by the enterprise backend service.

    VERIFYING_RESOLUTION
        The tool action completed. The orchestrator is checking whether the
        employee confirms their issue has been resolved.

    RESOLVED
        The employee confirmed the issue is resolved. Session is closing.

    CREATE_TICKET
        Automated resolution was not possible. A ServiceNow ticket should be
        or has been created for human follow-up.

    CLOSED
        The conversation has ended. No further messages will be processed.
    """

    NEW_ISSUE            = "NEW_ISSUE"
    UNDERSTANDING        = "UNDERSTANDING"
    TROUBLESHOOTING      = "TROUBLESHOOTING"
    READY_FOR_ACTION     = "READY_FOR_ACTION"
    WAITING_CONFIRMATION = "WAITING_CONFIRMATION"
    EXECUTING_ACTION     = "EXECUTING_ACTION"
    VERIFYING_RESOLUTION = "VERIFYING_RESOLUTION"
    RESOLVED             = "RESOLVED"
    CREATE_TICKET        = "CREATE_TICKET"
    CLOSED               = "CLOSED"


# ─────────────────────────────────────────────────────────────────────────────
# Conversation context dataclass
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class ConversationContext:
    """
    Complete context for a single IT support conversation session.

    All mutable fields are replaced atomically — no in-place mutation of
    nested collections so that state transitions remain auditable.

    Attributes
    ──────────
    conversation_id : str
        Unique session identifier (UUID string). Set at session creation;
        never modified.

    state : ConversationStateEnum
        Current lifecycle state of the conversation.
        Transitions must follow the defined state machine.

    category : str
        Detected IT issue category (e.g. ``"VPN"``, ``"OUTLOOK"``,
        ``"PASSWORD_RESET"``). Set after initial intent detection.
        Defaults to ``"GENERAL"``.

    kb_article : Optional[str]
        The knowledge base article or context string retrieved for this
        session. ``None`` if no KB lookup has been performed yet.

    last_ai_question : Optional[str]
        The most recent question posed by the AI assistant to the employee.
        Used to avoid asking the same question twice and to build context
        for the next turn.

    pending_tool : Optional[str]
        The tool name that is queued for execution (e.g. ``"INSTALL_SOFTWARE"``).
        Set when the orchestrator decides an action is needed but confirmation
        is still required. ``None`` when no tool is pending.

    pending_parameters : dict[str, Any]
        The parameters associated with ``pending_tool``. Empty dict when no
        tool is pending.

    current_step : int
        Zero-based index of the current troubleshooting step within the
        active KB article or resolution flow.

    attempt_count : int
        Number of troubleshooting attempts made in this session. Incremented
        each time the orchestrator tries a new resolution path. Used to
        decide when to escalate to ticket creation.

    issue_resolved : bool
        ``True`` if the employee has confirmed their issue is resolved.
        ``False`` otherwise.

    ticket_created : bool
        ``True`` if a ServiceNow support ticket has been created for this
        session. ``False`` otherwise.

    created_at : str
        ISO-8601 UTC timestamp when this context was instantiated.
        Set automatically; never modified.

    updated_at : str
        ISO-8601 UTC timestamp of the most recent state change.
        Updated by ``reset()`` and should be updated by the orchestrator
        on each state transition.
    """

    # ── Required fields ──────────────────────────────────────────────────────
    conversation_id: str

    # ── State ────────────────────────────────────────────────────────────────
    state: ConversationStateEnum = ConversationStateEnum.NEW_ISSUE

    # ── Issue context ────────────────────────────────────────────────────────
    category: str = "GENERAL"
    kb_article: Optional[str] = None
    last_ai_question: Optional[str] = None

    # ── Pending tool action ──────────────────────────────────────────────────
    pending_tool: Optional[str] = None
    pending_parameters: dict[str, Any] = field(default_factory=dict)

    # ── Progress tracking ────────────────────────────────────────────────────
    current_step: int = 0
    attempt_count: int = 0

    # ── Resolution flags ─────────────────────────────────────────────────────
    issue_resolved: bool = False
    ticket_created: bool = False

    # ── Timestamps (auto-set) ────────────────────────────────────────────────
    created_at: str = field(default_factory=lambda: _utc_now())
    updated_at: str = field(default_factory=lambda: _utc_now())

    # ── Serialisation ────────────────────────────────────────────────────────

    def to_dict(self) -> dict[str, Any]:
        """
        Serialise this context to a plain Python dictionary.

        All values are JSON-safe primitives (str, int, bool, dict, None).
        ``ConversationStateEnum`` values are stored as their string names.

        Returns
        ───────
        dict[str, Any]
            A complete, JSON-serialisable representation of this context.

        Example
        ───────
        ::

            ctx = ConversationContext(conversation_id="abc-123")
            d = ctx.to_dict()
            # d["state"] == "NEW_ISSUE"
        """
        result = {
            "conversation_id":    self.conversation_id,
            "state":              self.state.value,
            "category":           self.category,
            "kb_article":         self.kb_article,
            "last_ai_question":   self.last_ai_question,
            "pending_tool":       self.pending_tool,
            "pending_parameters": dict(self.pending_parameters),
            "current_step":       self.current_step,
            "attempt_count":      self.attempt_count,
            "issue_resolved":     self.issue_resolved,
            "ticket_created":     self.ticket_created,
            "created_at":         self.created_at,
            "updated_at":         self.updated_at,
        }
        logger.debug(
            "ConversationContext.to_dict: conversation_id=%s state=%s",
            self.conversation_id,
            self.state.value,
        )
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ConversationContext":
        """
        Deserialise a ``ConversationContext`` from a plain dictionary.

        Performs safe type coercion and falls back to defaults for any
        missing or unrecognised field. Never raises on partial data.

        Parameters
        ──────────
        data : dict[str, Any]
            A dictionary previously produced by ``to_dict()``, or any dict
            that contains at least ``conversation_id``.

        Returns
        ───────
        ConversationContext
            A fully populated context instance.

        Raises
        ──────
        ValueError
            If ``conversation_id`` is absent or empty.

        Example
        ───────
        ::

            ctx = ConversationContext.from_dict({
                "conversation_id": "abc-123",
                "state": "TROUBLESHOOTING",
                "category": "VPN",
            })
        """
        conversation_id = str(data.get("conversation_id", "")).strip()
        if not conversation_id:
            raise ValueError("ConversationContext.from_dict: 'conversation_id' is required.")

        # Safe state deserialisation — default to NEW_ISSUE on unknown value.
        raw_state = str(data.get("state", ConversationStateEnum.NEW_ISSUE.value)).upper().strip()
        try:
            state = ConversationStateEnum(raw_state)
        except ValueError:
            logger.warning(
                "ConversationContext.from_dict: unknown state '%s' — defaulting to NEW_ISSUE.",
                raw_state,
            )
            state = ConversationStateEnum.NEW_ISSUE

        pending_parameters = data.get("pending_parameters", {})
        if not isinstance(pending_parameters, dict):
            pending_parameters = {}

        ctx = cls(
            conversation_id   = conversation_id,
            state             = state,
            category          = str(data.get("category", "GENERAL")),
            kb_article        = data.get("kb_article") or None,
            last_ai_question  = data.get("last_ai_question") or None,
            pending_tool      = data.get("pending_tool") or None,
            pending_parameters= pending_parameters,
            current_step      = int(data.get("current_step", 0)),
            attempt_count     = int(data.get("attempt_count", 0)),
            issue_resolved    = bool(data.get("issue_resolved", False)),
            ticket_created    = bool(data.get("ticket_created", False)),
            created_at        = str(data.get("created_at", _utc_now())),
            updated_at        = str(data.get("updated_at", _utc_now())),
        )

        logger.debug(
            "ConversationContext.from_dict: conversation_id=%s state=%s",
            ctx.conversation_id,
            ctx.state.value,
        )
        return ctx

    def reset(self) -> None:
        """
        Reset all mutable fields to their initial defaults.

        ``conversation_id`` and ``created_at`` are preserved.
        ``updated_at`` is refreshed to the current UTC time.

        Use this when the employee starts a new issue within the same
        session without creating a new conversation ID.

        Example
        ───────
        ::

            ctx.reset()
            assert ctx.state == ConversationStateEnum.NEW_ISSUE
            assert ctx.attempt_count == 0
        """
        self.state              = ConversationStateEnum.NEW_ISSUE
        self.category           = "GENERAL"
        self.kb_article         = None
        self.last_ai_question   = None
        self.pending_tool       = None
        self.pending_parameters = {}
        self.current_step       = 0
        self.attempt_count      = 0
        self.issue_resolved     = False
        self.ticket_created     = False
        self.updated_at         = _utc_now()

        logger.info(
            "ConversationContext.reset: conversation_id=%s reset to NEW_ISSUE.",
            self.conversation_id,
        )


# ─────────────────────────────────────────────────────────────────────────────
# Private utilities
# ─────────────────────────────────────────────────────────────────────────────

def _utc_now() -> str:
    """Return the current UTC time as an ISO-8601 string (e.g. '2026-07-07T09:00:00Z')."""
    return datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
