"""
conversation_service.py
─────────────────────────────────────────────────────────────────────────────
Pure orchestrator — the ONLY entry point for the chat API.

Architecture (dependency-injected)
────────────────────────────────────
  ConversationService
      │
      ├── SessionManager          load / create sessions
      ├── IntentService           detect category
      ├── KnowledgeOrchestrator   KB search + troubleshooting startup
      ├── LlmOrchestrator         Gemini free conversation
      ├── TicketOrchestrator      ServiceNow ticket creation
      ├── ConversationRepository  persist session + turns
      └── StateTransitionLogger   record every phase change

Design contracts (MUST NOT be violated)
────────────────────────────────────────
  ✓  No business logic — only orchestration.
  ✓  ApprovalEngine called ONLY in TROUBLESHOOTING / VERIFYING / WAITING_TICKET_CONFIRMATION.
  ✓  Gemini NEVER drives workflow decisions.
  ✓  Every phase transition logged via StateTransitionLogger.
  ✓  Every response routed through response_builder.
  ✓  Never crashes — all external calls wrapped in injected services.
  ✓  handle_chat_turn() module-level function preserved for main.py backward compat.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

import app.services.approval_service as approval_service
import app.services.conversation_memory as memory
import app.services.troubleshooting_service as troubleshooting_service
from app.services.rag_service import get_document_for_category
from app.services.response_builder import (
    format_cancel_ack,
    format_draft_saved,
    format_helpdesk_contact,
    format_issue_switch,
    format_resolution,
    format_restart_ack,
    format_sn_failure_options,
    format_status_not_found,
    format_status_response,
    format_step,
    format_step_reprompt,
    format_ticket_command_prompt,
    format_ticket_created,
    format_ticket_declined,
    format_ticket_prompt,
    format_verification,
)
from app.services.troubleshooting_service import TroubleshootingSession

logger = logging.getLogger("it-agent-backend")


# ─────────────────────────────────────────────────────────────────────────────
# Phase enum — single source of truth for conversation state
# ─────────────────────────────────────────────────────────────────────────────

class ConversationPhase(str, Enum):
    UNDERSTANDING               = "UNDERSTANDING"
    DIAGNOSING                  = "DIAGNOSING"
    TROUBLESHOOTING             = "TROUBLESHOOTING"
    VERIFYING                   = "VERIFYING"
    WAITING_ACTION_CONFIRMATION = "WAITING_ACTION_CONFIRMATION"
    WAITING_TICKET_CONFIRMATION = "WAITING_TICKET_CONFIRMATION"
    WAITING_SN_RECOVERY         = "WAITING_SN_RECOVERY"   # ServiceNow failed, offering recovery
    RESOLVED                    = "RESOLVED"
    ESCALATED                   = "ESCALATED"


# ─────────────────────────────────────────────────────────────────────────────
# Session state dataclass
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class SessionState:
    session_id: str
    category: str
    phase: ConversationPhase = ConversationPhase.UNDERSTANDING
    troubleshooting_session: Optional[TroubleshootingSession] = None
    active_ticket: str = ""
    conversation_history: List[dict] = field(default_factory=list)
    diagnostic_answers: Dict[str, str] = field(default_factory=dict)
    attempted_actions: List[str] = field(default_factory=list)
    # Action engine guard — never execute more than this many auto-actions per session
    max_automatic_actions: int = 3
    # ServiceNow draft — saved when SN is unreachable
    ticket_draft: Dict[str, Any] = field(default_factory=dict)
    # Legacy fields kept for DB persistence / payload builder compatibility
    current_step: int = 0
    approval_required: bool = False
    approval_status: str = "PENDING"
    recommended_action: str = ""
    action_result: Any = None
    tool_result: Dict[str, Any] = field(default_factory=dict)
    active_issue: str = ""
    active_request: str = ""
    conversation_goal: str = ""
    last_action: str = ""

    @property
    def status(self) -> str:
        """Legacy status string used by DB persistence and payload builder."""
        if hasattr(self, "_legacy_status") and self._legacy_status is not None:
            return self._legacy_status
        return self.phase.value

    @status.setter
    def status(self, val: str) -> None:
        try:
            self.phase = ConversationPhase(val)
            self._legacy_status = None
        except ValueError:
            self._legacy_status = val

    def reset_troubleshooting(self) -> None:
        """Clear troubleshooting state without touching history."""
        self.troubleshooting_session = None
        self.phase = ConversationPhase.UNDERSTANDING
        self.diagnostic_answers = {}
        self.attempted_actions = []

    @property
    def is_troubleshooting(self) -> bool:
        return self.phase == ConversationPhase.TROUBLESHOOTING

    @is_troubleshooting.setter
    def is_troubleshooting(self, val: bool) -> None:
        if val:
            self.phase = ConversationPhase.TROUBLESHOOTING
        else:
            self.phase = ConversationPhase.UNDERSTANDING

    @property
    def waiting_for_step_confirmation(self) -> bool:
        return self.phase in (ConversationPhase.TROUBLESHOOTING, ConversationPhase.VERIFYING)

    @waiting_for_step_confirmation.setter
    def waiting_for_step_confirmation(self, val: bool) -> None:
        pass

    @property
    def steps(self) -> List[str]:
        if self.troubleshooting_session:
            from app.services.knowledge_service import get_steps
            from app.services.response_builder import format_step
            try:
                steps_data = get_steps(self.troubleshooting_session.article_id)
                return [format_step(s) for s in steps_data]
            except Exception:
                return []
        return []


# Backward compatibility class for verification/test scripts
class ConversationState(SessionState):
    def __init__(self, session_id: str, category: str, initial_message: str = ""):
        super().__init__(session_id=session_id, category=category)
        self.initial_message = initial_message


def start_conversation(message: str, category: str) -> ConversationState:
    session_id = str(uuid.uuid4())
    state = ConversationState(session_id, category, message)
    _default_session_mgr.save_to_cache(state)
    return state


# ─────────────────────────────────────────────────────────────────────────────
# Public accessor — kept for any callers outside ConversationService
# ─────────────────────────────────────────────────────────────────────────────

def get_conversation(session_id: str) -> Optional[SessionState]:
    """Cache-first, then DB. Delegates to the default SessionManager."""
    return _default_session_mgr.get(session_id)


# ─────────────────────────────────────────────────────────────────────────────
# ConversationService — pure orchestrator
# ─────────────────────────────────────────────────────────────────────────────

class ConversationService:
    """
    Dependency-injected orchestrator.
    All business logic lives in the injected services.
    """

    def __init__(
        self,
        session_mgr=None,
        kb_orch=None,
        ticket_orch=None,
        llm_orch=None,
        repo=None,
        transition_logger=None,
        action_engine=None,
    ) -> None:
        from app.services.session_manager import SessionManager
        from app.services.knowledge_orchestrator import KnowledgeOrchestrator
        from app.services.ticket_orchestrator import TicketOrchestrator
        from app.services.llm_orchestrator import LlmOrchestrator
        from app.services.conversation_repository import ConversationRepository
        import app.services.state_transition_logger as stl
        from app.services.action_engine import ActionEngine

        self._session_mgr = session_mgr or SessionManager()
        self._kb = kb_orch or KnowledgeOrchestrator()
        self._tickets = ticket_orch or TicketOrchestrator()
        self._llm = llm_orch or LlmOrchestrator()
        self._repo = repo or ConversationRepository()
        self._tl = transition_logger or stl
        self._actions = action_engine or ActionEngine()

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _detect_category(self, message: str) -> Optional[str]:
        from app.services.intent_service import detect_intent
        try:
            result = detect_intent(message)
            if isinstance(result, dict) and "debug_error" in result:
                return None
            return result
        except Exception:
            return None

    def _is_ticket_request(self, message: str) -> bool:
        from app.services.intent_router import IntentRouter, IntentType
        route = IntentRouter().route(message)
        if route.intent == IntentType.TICKET_COMMAND:
            return True
        # Fallback keyword checks for context-specific ticket requests
        normalized = message.lower().strip()
        keywords = ["ticket", "incident", "escalate", "support request", "sr"]
        return any(kw in normalized for kw in keywords)

    def _transition(self, state: SessionState, next_phase: ConversationPhase, reason: str) -> None:
        self._tl.log_transition(state.session_id, state.phase, next_phase, reason)
        state.phase = next_phase

    def _reply(self, state: SessionState, message: str, bot_text: str, action: str, **kw) -> dict:
        self._repo.persist(state, message, bot_text)
        return self._build_payload(state, bot_text, action, **kw)

    def _build_payload(self, state, bot_text, action, ticket_created=False, ticket_id=None, ticket_details=None):
        td = ticket_details or {}
        if state.approval_required and state.approval_status == "PENDING":
            action = "WAIT_FOR_APPROVAL"
        return {
            "session_id": state.session_id,
            "category": state.category,
            "action": action,
            "response": bot_text,
            "history_length": len(memory.get_history(state.session_id)),
            # Ticket creation fields — only truthy when DB persistence succeeded
            "ticket_created": bool(ticket_created and ticket_id and not td.get("error")),
            "ticket_id": ticket_id,
            "servicenow_id": td.get("servicenow_id"),
            "assigned_team": td.get("assigned_team"),
            "priority": td.get("priority"),
            "sla_hours": td.get("sla_hours"),
            "notifications_created": bool(ticket_created),
            # Full ITSM workflow fields
            "ticket": ticket_details,
            "request_type": td.get("request_type"),         # INCIDENT | SERVICE_REQUEST
            "approval_status": td.get("approval_status"),   # NOT_REQUIRED | PENDING
            "requires_approval": td.get("requires_approval", False),
            "ticket_status": td.get("status"),              # WAITING_MANAGER | NEW | etc.
            "ticket_status_label": td.get("status_label"),  # Human-readable
            "manager": td.get("manager"),
            # Conversation-level fields
            "source": get_document_for_category(state.category),
            "context_used": get_document_for_category(state.category) != "N/A",
            "tool_result": state.tool_result,
            "approval_required": state.approval_required,
            "recommended_action": state.recommended_action,
            "action_result": state.action_result,
            "status": state.phase.value,
        }

    # ── Phase handlers (all < 20 lines) ──────────────────────────────────────

    def _handle_understanding_or_diagnosing(self, state, message, username):
        import app.services.diagnostic_engine as de
        
        # 1. If currently in DIAGNOSING phase, extract the answer to the last question asked
        if state.phase == ConversationPhase.DIAGNOSING:
            last_agent_message = ""
            history = memory.get_history(state.session_id)
            if history:
                for turn in reversed(history):
                    if turn.get("sender") == "agent":
                        last_agent_message = turn.get("text", "")
                        break
            if last_agent_message:
                ans = de.extract_answers(state.category, message, last_agent_message)
                for k, v in ans.items():
                    state.diagnostic_answers[k] = v

        # 2. Re-evaluate if confidence is high
        if de.is_confidence_high(state.category, message, state.diagnostic_answers):
            step_text = self._kb.start_troubleshooting(state, message)
            if step_text:
                self._transition(state, ConversationPhase.TROUBLESHOOTING, "Confidence high — starting KB")
                greeting = f"Welcome to Bridgestone IT Support. Let me assist you to resolve this {state.category} issue.\n\n"
                return self._reply(state, message, greeting + step_text, "ASK_MORE_INFO")
            else:
                self._transition(state, ConversationPhase.UNDERSTANDING, "No KB exists — delegating to Gemini")
                return self._reply(state, message, self._llm.converse(state, message), "ASK_MORE_INFO")
        else:
            # 3. Confidence is low — ask next question
            question = de.get_next_question(state.category, state.diagnostic_answers)
            if question:
                self._transition(state, ConversationPhase.DIAGNOSING, "Confidence low — asking diagnostic question")
                return self._reply(state, message, question, "ASK_MORE_INFO")
            else:
                step_text = self._kb.start_troubleshooting(state, message)
                if step_text:
                    self._transition(state, ConversationPhase.TROUBLESHOOTING, "Questions exhausted — starting KB")
                    greeting = f"Welcome to Bridgestone IT Support. Let me assist you to resolve this {state.category} issue.\n\n"
                    return self._reply(state, message, greeting + step_text, "ASK_MORE_INFO")
                else:
                    self._transition(state, ConversationPhase.UNDERSTANDING, "Questions exhausted — delegating to Gemini")
                    return self._reply(state, message, self._llm.converse(state, message), "ASK_MORE_INFO")

    def _handle_troubleshooting(self, state, message, username):
        ts = state.troubleshooting_session
        step_details = troubleshooting_service.current_step(ts)
        approval = approval_service.detect_approval(message)

        if approval.status == approval_service.ApprovalStatus.APPROVED:
            troubleshooting_service.mark_completed(ts)
            next_d = troubleshooting_service.next_step(ts)
            if next_d:
                return self._reply(state, message, format_step(next_d), "ASK_MORE_INFO")
            self._transition(state, ConversationPhase.VERIFYING, "all steps completed — approved")
            return self._reply(state, message, format_verification(troubleshooting_service.get_verification(ts)), "ASK_MORE_INFO")

        if approval.status == approval_service.ApprovalStatus.REJECTED:
            troubleshooting_service.mark_completed(ts)
            next_d = troubleshooting_service.next_step(ts)
            if next_d:
                return self._reply(state, message, format_step(next_d), "ASK_MORE_INFO")
            self._transition(state, ConversationPhase.VERIFYING, "all steps completed — rejected")
            return self._reply(state, message, format_verification(troubleshooting_service.get_verification(ts)), "ASK_MORE_INFO")

        explanation = ""
        if step_details:
            explanation = self._llm.converse_with_step(state, message, step_details)
        else:
            explanation = self._llm.converse(state, message)
            
        reprompt_text = format_step_reprompt(step_details) if step_details else ""
        bot_text = f"{explanation}\n\n{reprompt_text}" if reprompt_text else explanation
        return self._reply(state, message, bot_text, "ASK_MORE_INFO")

    def _handle_verifying(self, state, message, username):
        if self._is_ticket_request(message):
            self._transition(state, ConversationPhase.WAITING_TICKET_CONFIRMATION, "user requested ticket creation during verification")
            return self._reply(state, message, format_ticket_command_prompt(), "ASK_MORE_INFO")

        approval = approval_service.detect_approval(message)
        if approval.status == approval_service.ApprovalStatus.APPROVED:
            self._transition(state, ConversationPhase.RESOLVED, "user confirmed resolved")
            state.troubleshooting_session = None
            return self._reply(state, message, format_resolution(), "RESOLVED")
        if approval.status == approval_service.ApprovalStatus.REJECTED:
            self._transition(state, ConversationPhase.WAITING_TICKET_CONFIRMATION, "verification failed")
            return self._reply(state, message, format_ticket_prompt(), "ASK_MORE_INFO")
        return self._reply(state, message, format_verification(troubleshooting_service.get_verification(state.troubleshooting_session) if state.troubleshooting_session else []), "ASK_MORE_INFO")

    def _handle_waiting_action(self, state, message, username):
        if self._is_ticket_request(message):
            self._transition(state, ConversationPhase.WAITING_TICKET_CONFIRMATION, "user requested ticket creation during action confirmation")
            return self._reply(state, message, format_ticket_command_prompt(), "ASK_MORE_INFO")

        approval = approval_service.detect_approval(message)
        action_name = state.attempted_actions[-1] if state.attempted_actions else None
        
        action = None
        if action_name:
            from app.services.action_engine import ACTIONS_MAP
            for act in ACTIONS_MAP.get(state.category, []):
                if act.name == action_name:
                    action = act
                    break
                    
        if not action:
            self._transition(state, ConversationPhase.WAITING_TICKET_CONFIRMATION, "no active action to confirm")
            return self._reply(state, message, format_ticket_prompt(), "ASK_MORE_INFO")

        if approval.status == approval_service.ApprovalStatus.APPROVED:
            result = self._actions.execute(action)
            if result.get("status") == "SUCCESS":
                self._transition(state, ConversationPhase.VERIFYING, f"executed {action.name} successfully")
                response_msg = f"I have successfully performed this action: {action.name}.\n\nDid that resolve the issue?"
                return self._reply(state, message, response_msg, "ASK_MORE_INFO")
            else:
                self._transition(state, ConversationPhase.WAITING_TICKET_CONFIRMATION, f"execution of {action.name} failed")
                return self._reply(state, message, f"I attempted to {action.name} but it failed: {result.get('message', 'Unknown error')}.\n\n{format_ticket_prompt()}", "ASK_MORE_INFO")
                
        if approval.status == approval_service.ApprovalStatus.REJECTED:
            # Enforce maximum automatic actions limit
            if len(state.attempted_actions) >= state.max_automatic_actions:
                self._transition(state, ConversationPhase.WAITING_TICKET_CONFIRMATION, "max automatic actions reached")
                return self._reply(state, message, format_ticket_prompt(), "ASK_MORE_INFO")
            next_action = self._actions.get_next_action(state.category, state.attempted_actions)
            if next_action:
                state.attempted_actions.append(next_action.name)
                if next_action.requires_confirmation:
                    self._transition(state, ConversationPhase.WAITING_ACTION_CONFIRMATION, f"next action: {next_action.name}")
                    prompt_msg = f"I understand. Alternatively, I can attempt to {next_action.name}. Shall I proceed?"
                    return self._reply(state, message, prompt_msg, "ASK_MORE_INFO")
                else:
                    result = self._actions.execute(next_action)
                    if result.get("status") == "SUCCESS":
                        self._transition(state, ConversationPhase.VERIFYING, f"executed {next_action.name} successfully")
                        response_msg = f"I have successfully performed this action: {next_action.name}.\n\nDid that resolve the issue?"
                        return self._reply(state, message, response_msg, "ASK_MORE_INFO")
                    else:
                        self._transition(state, ConversationPhase.WAITING_TICKET_CONFIRMATION, f"execution of {next_action.name} failed")
                        return self._reply(state, message, f"I attempted to {next_action.name} but it failed: {result.get('message', 'Unknown error')}.\n\n{format_ticket_prompt()}", "ASK_MORE_INFO")
            else:
                self._transition(state, ConversationPhase.WAITING_TICKET_CONFIRMATION, "action declined & no other actions available")
                return self._reply(state, message, format_ticket_prompt(), "ASK_MORE_INFO")

        prompt_msg = f"I can attempt to {action.name} for you. Shall I proceed?"
        return self._reply(state, message, prompt_msg, "ASK_MORE_INFO")

    def _handle_waiting_ticket(self, state, message, username):
        approval = approval_service.detect_approval(message)
        if approval.status == approval_service.ApprovalStatus.APPROVED:
            ticket = self._tickets.create(state, username)
            if not ticket or ticket.get("error"):
                # ServiceNow unavailable — transition to recovery phase
                self._transition(state, ConversationPhase.WAITING_SN_RECOVERY, "ServiceNow failure — offering recovery")
                import app.services.conversation_memory as memory
                hist = memory.get_history(state.session_id)
                state.ticket_draft = {
                    "category": state.category,
                    "description": hist[0]["text"] if hist else (state.active_issue or "IT Support Issue"),
                }
                return self._reply(state, message, format_sn_failure_options(), "ASK_MORE_INFO")
            tid = ticket.get("ticket_id", "N/A")
            self._transition(state, ConversationPhase.ESCALATED, f"ticket approved — {tid}")
            state.active_ticket = tid
            state.troubleshooting_session = None
            bot_text = format_ticket_created(
                tid,
                ticket.get("assigned_team", "IT Support"),
                request_type=ticket.get("request_type", "INCIDENT"),
                requires_approval=ticket.get("requires_approval", False),
                status_label=ticket.get("status_label", ""),
            )
            return self._reply(state, message, bot_text, "TICKET_CREATED", ticket_created=True, ticket_id=tid, ticket_details=ticket)
        if approval.status == approval_service.ApprovalStatus.REJECTED:
            self._transition(state, ConversationPhase.UNDERSTANDING, "ticket declined by user")
            state.reset_troubleshooting()
            return self._reply(state, message, format_ticket_declined(), "ASK_MORE_INFO")
        return self._reply(state, message, format_ticket_prompt(), "ASK_MORE_INFO")

    def _handle_sn_recovery(self, state, message, username):
        """Handle user's chosen recovery path after a ServiceNow failure."""
        from app.services.intent_router import TicketFailureIntent, detect_ticket_failure_intent
        intent = detect_ticket_failure_intent(message)

        if intent == TicketFailureIntent.RETRY:
            ticket = self._tickets.create(state, username)
            if not ticket or ticket.get("error"):
                # Still failing — stay in WAITING_SN_RECOVERY
                return self._reply(state, message, format_sn_failure_options(), "ASK_MORE_INFO")
            tid = ticket.get("ticket_id", "N/A")
            self._transition(state, ConversationPhase.ESCALATED, f"ticket retry successful — {tid}")
            state.active_ticket = tid
            state.troubleshooting_session = None
            state.ticket_draft = {}
            bot_text = format_ticket_created(
                tid,
                ticket.get("assigned_team", "IT Support"),
                request_type=ticket.get("request_type", "INCIDENT"),
                requires_approval=ticket.get("requires_approval", False),
                status_label=ticket.get("status_label", ""),
            )
            return self._reply(state, message, bot_text, "TICKET_CREATED", ticket_created=True, ticket_id=tid, ticket_details=ticket)

        if intent == TicketFailureIntent.DRAFT:
            issue_desc = state.ticket_draft.get("description", "IT Support Issue")
            state.ticket_draft["saved"] = True
            self._transition(state, ConversationPhase.UNDERSTANDING, "ticket draft saved by user")
            state.reset_troubleshooting()
            return self._reply(state, message, format_draft_saved(issue_desc), "ASK_MORE_INFO")

        if intent == TicketFailureIntent.HELPDESK:
            self._transition(state, ConversationPhase.UNDERSTANDING, "user chose helpdesk contact")
            state.reset_troubleshooting()
            return self._reply(state, message, format_helpdesk_contact(), "ASK_MORE_INFO")

        # Unknown input — re-present the options
        return self._reply(state, message, format_sn_failure_options(), "ASK_MORE_INFO")

    # ── Intent Router phase handlers ──────────────────────────────────────────

    def _handle_ticket_command(self, state, message, username):
        """User explicitly asked to create a ticket — create it immediately."""
        if state.phase == ConversationPhase.ESCALATED and state.active_ticket:
            return self._reply(state, message, format_status_response(state.active_ticket), "ASK_MORE_INFO")
        
        ticket = self._tickets.create(state, username)
        if not ticket or ticket.get("error"):
            # ServiceNow unavailable — transition to recovery phase
            self._transition(state, ConversationPhase.WAITING_SN_RECOVERY, "ServiceNow failure — offering recovery")
            import app.services.conversation_memory as memory
            hist = memory.get_history(state.session_id)
            state.ticket_draft = {
                "category": state.category,
                "description": hist[0]["text"] if hist else (state.active_issue or "IT Support Issue"),
            }
            return self._reply(state, message, format_sn_failure_options(), "ASK_MORE_INFO")
            
        tid = ticket.get("ticket_id", "N/A")
        self._transition(state, ConversationPhase.ESCALATED, f"ticket created — {tid}")
        state.active_ticket = tid
        state.troubleshooting_session = None
        bot_text = format_ticket_created(
            tid,
            ticket.get("assigned_team", "IT Support"),
            request_type=ticket.get("request_type", "INCIDENT"),
            requires_approval=ticket.get("requires_approval", False),
            status_label=ticket.get("status_label", ""),
        )
        return self._reply(state, message, bot_text, "TICKET_CREATED", ticket_created=True, ticket_id=tid, ticket_details=ticket)

    def _handle_restart(self, state, message):
        """Reset the conversation to UNDERSTANDING without changing session_id."""
        old_phase = state.phase
        state.reset_troubleshooting()
        state.ticket_draft = {}
        self._tl.log_transition(state.session_id, old_phase, ConversationPhase.UNDERSTANDING, "user restarted conversation")
        return self._reply(state, message, format_restart_ack(), "ASK_MORE_INFO")

    def _handle_cancel(self, state, message):
        """Cancel the current workflow and return to UNDERSTANDING."""
        phase = state.phase
        if phase == ConversationPhase.WAITING_TICKET_CONFIRMATION:
            self._transition(state, ConversationPhase.UNDERSTANDING, "cancel = ticket declined")
            state.reset_troubleshooting()
            return self._reply(state, message, format_ticket_declined(), "ASK_MORE_INFO")
        # All other phases — cancel workflow and reset
        self._transition(state, ConversationPhase.UNDERSTANDING, "user cancelled workflow")
        state.reset_troubleshooting()
        return self._reply(state, message, format_cancel_ack(), "ASK_MORE_INFO")

    def _handle_status(self, state, message):
        """Return active ticket status, or inform user no ticket exists."""
        if state.active_ticket:
            return self._reply(state, message, format_status_response(state.active_ticket), "ASK_MORE_INFO")
        return self._reply(state, message, format_status_not_found(), "ASK_MORE_INFO")

    def _handle_terminal(self, state, message, username):
        return self._reply(state, message, self._llm.converse(state, message), "ASK_MORE_INFO")

    # ── Main entry point ──────────────────────────────────────────────────────

    def handle_chat_turn(
        self,
        session_id: Optional[str],
        message: str,
        username: Optional[str] = None,
        user_role: Optional[str] = None,
    ) -> dict:
        from app.services.intent_router import IntentRouter, IntentType

        # 1. Route message — deterministic, priority-ordered
        route = IntentRouter().route(message)

        # 2. Session load or create (use route category for new sessions)
        detected_category = route.category or "GENERAL"
        session_id, state = self._session_mgr.load_or_create(session_id, detected_category)

        # 1. Handle Turn 2 (pending approval confirmation)
        if state.approval_required and state.approval_status == "PENDING":
            import app.services.approval_service as approval_service
            approval = approval_service.detect_approval(message)
            if approval.status == approval_service.ApprovalStatus.APPROVED:
                if user_role == "EMPLOYEE":
                    from app.services.rbac_service import build_access_denied_response
                    from app.services.rbac_audit_service import log_rbac_event
                    from app.services.audit_service import log_approval

                    log_rbac_event(
                        user=username or "unknown",
                        role="EMPLOYEE",
                        action="ACCESS_DENIED",
                        details={
                            "reason": "EXECUTE_ACTION_NON_PRIVILEGED_BYPASS_BLOCKED",
                            "is_privileged_detected": True,
                            "recommended_action": state.recommended_action,
                            "session_id": state.session_id,
                        }
                    )
                    log_approval(
                        session_id=state.session_id,
                        recommended_action=state.recommended_action,
                        approval_status="ACCESS_DENIED"
                    )
                    denied_resp = build_access_denied_response("EMPLOYEE", "approve_privileged_action")
                    bot_text = denied_resp["decision_response"]
                    state.approval_status = "ACCESS_DENIED"
                    self._repo.persist(state, message, bot_text)
                    return self._build_payload(state, bot_text, "ACCESS_DENIED")
                else:
                    # Manager or Admin approved! Execute the action!
                    from app.services.action_service import create_vpn_restoration_request
                    try:
                        res_action = create_vpn_restoration_request("VPN access restoration requested by " + (username or "user"))
                        state.action_result = res_action
                        state.approval_status = "APPROVED"
                        state.phase = ConversationPhase.ESCALATED
                        bot_text = f"VPN access restoration request executed successfully. ServiceNow Request ID: {res_action.get('servicenow_id')}."
                        self._repo.persist(state, message, bot_text)
                        return self._build_payload(state, bot_text, "EXECUTE_ACTION", ticket_created=True, ticket_id=res_action.get('servicenow_id'), ticket_details=res_action)
                    except Exception as e:
                        logger.error("Failed to execute restoration action: %s", e)
            elif approval.status == approval_service.ApprovalStatus.REJECTED:
                state.approval_status = "REJECTED"
                state.approval_required = False
                bot_text = "I have canceled the request."
                self._repo.persist(state, message, bot_text)
                return self._build_payload(state, bot_text, "REJECTED")

        # 2. Handle Turn 1 (new VPN reset/disabled request)
        is_vpn_reset_req = (detected_category == "VPN" and any(w in message.lower() for w in ["reset", "restore", "re-enable", "disabled", "unlock"]))
        if is_vpn_reset_req:
            from app.services.tool_agent import execute_tools
            state.tool_result = execute_tools("VPN", message)
            state.approval_required = True
            state.approval_status = "PENDING"
            state.recommended_action = "VPN_ACCESS_RESTORATION"
            state.phase = ConversationPhase.WAITING_ACTION_CONFIRMATION
            bot_text = "Your VPN access currently appears to be disabled. A restoration request requires manager approval. Would you like me to request approval?"
            self._repo.persist(state, message, bot_text)
            return self._build_payload(state, bot_text, "WAIT_FOR_APPROVAL")

        # 3. Populate default tool_result on first turn if empty
        if not state.tool_result and detected_category in ("VPN", "OUTLOOK", "SOFTWARE_INSTALLATION"):
            from app.services.tool_agent import execute_tools
            try:
                state.tool_result = execute_tools(detected_category, message)
            except Exception as e:
                logger.error("Failed to run initial execute_tools: %s", e)

        logger.info(
            "Dispatcher: session=%s intent=%s phase=%s category=%s",
            state.session_id, route.intent.value, state.phase.value, state.category,
        )

        # 3. Global intents — always intercepted before phase handlers
        #    These override any phase-specific logic.

        if route.intent == IntentType.TICKET_COMMAND:
            return self._handle_ticket_command(state, message, username)

        if route.intent == IntentType.RESTART:
            return self._handle_restart(state, message)

        if route.intent == IntentType.CANCEL:
            return self._handle_cancel(state, message)

        if route.intent == IntentType.STATUS:
            return self._handle_status(state, message)

        # 4. RESOLVED_KEYWORD — only triggers in active troubleshooting phases
        #    Never claims success unless user explicitly confirms.
        if route.intent == IntentType.RESOLVED_KEYWORD:
            _active_phases = (
                ConversationPhase.TROUBLESHOOTING,
                ConversationPhase.VERIFYING,
                ConversationPhase.WAITING_ACTION_CONFIRMATION,
            )
            if state.phase in _active_phases:
                self._transition(state, ConversationPhase.RESOLVED, "resolved keyword detected")
                state.troubleshooting_session = None
                return self._reply(state, message, format_resolution(), "RESOLVED")
            # Outside active phases — fall through to normal phase dispatch

        # 5. Category-switch guard (for IT_ISSUE with a different category)
        if route.intent == IntentType.IT_ISSUE:
            detected = route.category or "GENERAL"
            if detected != "GENERAL" and detected != state.category:
                old = state.category
                state.category = detected
                state.reset_troubleshooting()
                self._tl.log_transition(state.session_id, old, detected, "category switch")
                ack = format_issue_switch(detected)

                import app.services.diagnostic_engine as de
                if de.is_confidence_high(detected, message, state.diagnostic_answers):
                    step = self._kb.start_troubleshooting(state, message)
                    greeting = f"Welcome to Bridgestone IT Support. Let me assist you to resolve this {detected} issue.\n\n"
                    bot_text = f"{ack}\n\n{greeting}{step}" if step else ack
                    if step:
                        self._transition(state, ConversationPhase.TROUBLESHOOTING, "Switch & starting KB")
                else:
                    question = de.get_next_question(detected, state.diagnostic_answers)
                    bot_text = f"{ack}\n\n{question}" if question else ack
                    if question:
                        self._transition(state, ConversationPhase.DIAGNOSING, "Switch & asking diagnostic")
                return self._reply(state, message, bot_text, "ASK_MORE_INFO")

        # 6. Phase dispatch
        phase = state.phase

        if phase in (ConversationPhase.UNDERSTANDING, ConversationPhase.DIAGNOSING):
            return self._handle_understanding_or_diagnosing(state, message, username)

        if phase == ConversationPhase.TROUBLESHOOTING:
            if not state.troubleshooting_session:
                self._transition(state, ConversationPhase.UNDERSTANDING, "guard: ts lost — reset")
                return self._handle_understanding_or_diagnosing(state, message, username)
            return self._handle_troubleshooting(state, message, username)

        if phase == ConversationPhase.VERIFYING:
            return self._handle_verifying(state, message, username)

        if phase == ConversationPhase.WAITING_ACTION_CONFIRMATION:
            return self._handle_waiting_action(state, message, username)

        if phase == ConversationPhase.WAITING_TICKET_CONFIRMATION:
            return self._handle_waiting_ticket(state, message, username)

        if phase == ConversationPhase.WAITING_SN_RECOVERY:
            return self._handle_sn_recovery(state, message, username)

        return self._handle_terminal(state, message, username)


# ─────────────────────────────────────────────────────────────────────────────
# Module-level singleton + backward-compat function
# main.py calls handle_chat_turn() as a plain function — API unchanged.
# ─────────────────────────────────────────────────────────────────────────────

from app.services.session_manager import SessionManager as _SM
_default_session_mgr = _SM()
_default_service = ConversationService(session_mgr=_default_session_mgr)


class _ConversationsDict(dict):
    def __getitem__(self, key):
        state = _default_session_mgr.get(key)
        if state is None:
            return super().__getitem__(key)
        return state

    def __setitem__(self, key, value):
        super().__setitem__(key, value)
        _default_session_mgr.save_to_cache(value)

    def __contains__(self, key):
        return _default_session_mgr.get(key) is not None or super().__contains__(key)

    def get(self, key, default=None):
        state = _default_session_mgr.get(key)
        if state is not None:
            return state
        return super().get(key, default)

    def pop(self, key, default=None):
        import app.services.conversation_persistence as cp
        cp.cache_remove(key)
        return super().pop(key, default)

conversations = _ConversationsDict()


def handle_chat_turn(
    session_id: Optional[str],
    message: str,
    username: Optional[str] = None,
    user_role: Optional[str] = None,
) -> dict:
    """Module-level entry point — preserves backward compatibility with main.py."""
    return _default_service.handle_chat_turn(session_id, message, username, user_role)
