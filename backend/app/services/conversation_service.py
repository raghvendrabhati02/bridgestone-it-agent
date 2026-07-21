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


def _contains_category_keyword(message: str, category: str) -> bool:
    text = message.lower()
    category = category.upper()
    if category == "VPN":
        return any(kw in text for kw in ["vpn", "globalprotect", "global protect", "remote access", "anyconnect", "cisco"])
    if category == "OUTLOOK":
        return any(kw in text for kw in ["outlook", "email", "mail", "exchange", "mailbox", "calendar"])
    if category == "PRINTER":
        return any(kw in text for kw in ["printer", "printing", "print", "scanner", "spooler"])
    if category == "TEAMS":
        return any(kw in text for kw in ["teams", "microsoft teams", "teams call", "teams meeting", "teams chat"])
    if category == "WIFI":
        return any(kw in text for kw in ["wifi", "wi-fi", "wireless", "bs-guest", "bsguest", "guest wifi"])
    if category == "PASSWORD_RESET":
        return any(kw in text for kw in ["password", "reset", "forgot", "expired", "unlock", "account locked"])
    if category == "SOFTWARE_INSTALLATION":
        return any(kw in text for kw in ["software", "install", "application", "setup", "uninstall", "download", "adobe", "citrix", "vs code", "vscode"])
    if category == "SAP":
        return "sap" in text
    if category == "DEVICE_HEALTH":
        return any(kw in text for kw in ["slow", "sluggish", "lagging", "freezing", "frozen", "hang", "cpu", "memory", "performance", "disk"])
    if category == "IT_ASSET_ALLOCATION":
        return any(kw in text for kw in ["laptop", "hardware request", "asset", "joining kit"])
    return False


# ─────────────────────────────────────────────────────────────────────────────
# Phase enum — single source of truth for conversation state
# ─────────────────────────────────────────────────────────────────────────────

class ConversationPhase(str, Enum):
    UNDERSTANDING               = "UNDERSTANDING"
    DIAGNOSING                  = "DIAGNOSING"
    AI_TROUBLESHOOTING          = "AI_TROUBLESHOOTING"    # Gemini-driven multi-turn troubleshooting (NEW)
    TROUBLESHOOTING             = "TROUBLESHOOTING"       # KB-step troubleshooting (privileged operations)
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
    clarifying_questions_asked: int = 0
    troubleshooting_steps_suggested: int = 0
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
        if self.phase == ConversationPhase.ESCALATED:
            return "TICKET_CREATED"
        if self.phase in (ConversationPhase.UNDERSTANDING, ConversationPhase.DIAGNOSING):
            return "ACTIVE"
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
        self.clarifying_questions_asked = 0
        self.troubleshooting_steps_suggested = 0
        self.ticket_offered = False
        self.ticket_declined = False
        self.conversation_locked = False

    @property
    def ticket_offered(self) -> bool:
        if not isinstance(self.tool_result, dict):
            self.tool_result = {}
        return self.tool_result.get("ticket_offered", False)

    @ticket_offered.setter
    def ticket_offered(self, val: bool) -> None:
        if not isinstance(self.tool_result, dict):
            self.tool_result = {}
        self.tool_result["ticket_offered"] = val

    @property
    def ticket_declined(self) -> bool:
        if not isinstance(self.tool_result, dict):
            self.tool_result = {}
        return self.tool_result.get("ticket_declined", False)

    @ticket_declined.setter
    def ticket_declined(self, val: bool) -> None:
        if not isinstance(self.tool_result, dict):
            self.tool_result = {}
        self.tool_result["ticket_declined"] = val

    @property
    def conversation_locked(self) -> bool:
        if not isinstance(self.tool_result, dict):
            self.tool_result = {}
        return self.tool_result.get("conversation_locked", False)

    @conversation_locked.setter
    def conversation_locked(self, val: bool) -> None:
        if not isinstance(self.tool_result, dict):
            self.tool_result = {}
        self.tool_result["conversation_locked"] = val

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
        return self.phase == ConversationPhase.TROUBLESHOOTING

    @waiting_for_step_confirmation.setter
    def waiting_for_step_confirmation(self, val: bool) -> None:
        if val:
            self.phase = ConversationPhase.TROUBLESHOOTING
        else:
            if self.phase == ConversationPhase.TROUBLESHOOTING:
                self.phase = ConversationPhase.UNDERSTANDING

    @property
    def waiting_for_solution_verification(self) -> bool:
        return self.phase == ConversationPhase.VERIFYING

    @waiting_for_solution_verification.setter
    def waiting_for_solution_verification(self, val: bool) -> None:
        if val:
            self.phase = ConversationPhase.VERIFYING
        else:
            if self.phase == ConversationPhase.VERIFYING:
                self.phase = ConversationPhase.UNDERSTANDING

    @property
    def waiting_for_ticket_confirmation(self) -> bool:
        return self.phase == ConversationPhase.WAITING_TICKET_CONFIRMATION

    @waiting_for_ticket_confirmation.setter
    def waiting_for_ticket_confirmation(self, val: bool) -> None:
        if val:
            self.phase = ConversationPhase.WAITING_TICKET_CONFIRMATION
        else:
            if self.phase == ConversationPhase.WAITING_TICKET_CONFIRMATION:
                self.phase = ConversationPhase.UNDERSTANDING

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
    # Automatically execute the first turn to populate initial response and transitions
    _default_service.handle_chat_turn(session_id, message)
    return _default_session_mgr.get(session_id)


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

    def _save_category_state(self, state) -> None:
        if not isinstance(state.tool_result, dict):
            state.tool_result = {}
        if "_category_states" not in state.tool_result:
            state.tool_result["_category_states"] = {}
            
        current_step = 1
        if state.troubleshooting_session:
            current_step = state.troubleshooting_session.current_step
            
        state.tool_result["_category_states"][state.category] = {
            "phase": state.phase.value if hasattr(state.phase, 'value') else state.phase,
            "active_issue": state.active_issue or "",
            "current_step": current_step,
            "ticket_offered": state.ticket_offered,
            "ticket_declined": state.ticket_declined,
            "conversation_locked": state.conversation_locked,
        }

    def _restore_category_state(self, state, category: str) -> bool:
        if not isinstance(state.tool_result, dict):
            return False
        states = state.tool_result.get("_category_states", {})
        cached = states.get(category)
        if not cached:
            state.reset_troubleshooting()
            return False
            
        try:
            state.phase = ConversationPhase(cached["phase"])
        except ValueError:
            state.phase = ConversationPhase.UNDERSTANDING
            
        state.active_issue = cached.get("active_issue", "")
        state.ticket_offered = cached.get("ticket_offered", False)
        state.ticket_declined = cached.get("ticket_declined", False)
        state.conversation_locked = cached.get("conversation_locked", False)
        
        step = cached.get("current_step", 1)
        from app.services.knowledge_service import search_by_category
        article = search_by_category(category)
        if article:
            from app.services.troubleshooting_service import start
            session = start(article.get("article_id"))
            if session:
                session.current_step = step
                state.troubleshooting_session = session
            else:
                state.troubleshooting_session = None
        else:
            state.troubleshooting_session = None
            
        return True

    def _transition(self, state: SessionState, next_phase: ConversationPhase, reason: str) -> None:
        self._tl.log_transition(state.session_id, state.phase, next_phase, reason)
        state.phase = next_phase
        from app.services.observability_service import log_event
        p_val = next_phase.value if hasattr(next_phase, 'value') else str(next_phase)
        log_event("Conversation phase transition", phase=p_val, escalation_reason=reason)
        
        # State machine flag updates
        if next_phase in (ConversationPhase.TROUBLESHOOTING, ConversationPhase.AI_TROUBLESHOOTING):
            state.conversation_locked = True
        elif next_phase == ConversationPhase.WAITING_TICKET_CONFIRMATION:
            state.ticket_offered = True
        elif next_phase in (ConversationPhase.RESOLVED, ConversationPhase.ESCALATED):
            state.conversation_locked = False
            state.ticket_offered = False
            state.ticket_declined = False

        if p_val in ("RESOLVED", "ESCALATED"):
            log_event("Conversation completed", category=state.category, phase=p_val, ticket_id=state.active_ticket)

    def _reply(self, state: SessionState, message: str, bot_text: str, action: str, **kw) -> dict:
        self._repo.persist(state, message, bot_text)
        return self._build_payload(state, bot_text, action, **kw)

    def _build_payload(self, state, bot_text, action, ticket_created=False, ticket_id=None, ticket_details=None):
        td = ticket_details or {}
        if state.approval_required and state.approval_status == "PENDING":
            action = "WAIT_FOR_APPROVAL"
        
        resolved_ticket_id = ticket_id or state.active_ticket
        return {
            "session_id": state.session_id,
            "category": state.category,
            "action": action,
            "response": bot_text,
            "history_length": len(memory.get_history(state.session_id)),
            # Ticket creation fields — only truthy when DB persistence succeeded
            "ticket_created": bool(ticket_created and resolved_ticket_id and not td.get("error")),
            "ticket_id": resolved_ticket_id,
            "servicenow_id": td.get("servicenow_id") or (resolved_ticket_id if resolved_ticket_id and resolved_ticket_id.startswith("REQ") or resolved_ticket_id.startswith("INC") else None),
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

    # ── Intent classification sets (class-level) ───────────────────────────────
    # Controls which Gemini intents trigger which conversation phases.
    _DIAGNOSABLE_INTENTS: frozenset = frozenset({
        "GENERAL_SUPPORT", "CHECK_VPN_STATUS", "CHECK_OUTLOOK",
        "CHECK_DEVICE_STATUS", "CHECK_DEVICE_HEALTH", "RESTART_SERVICE",
        "SEARCH_KNOWLEDGE_BASE", "UNKNOWN",
    })
    _PRIVILEGED_INTENTS: frozenset = frozenset({"VPN_ACCESS_RESTORE", "INSTALL_SOFTWARE"})
    _TICKET_INTENTS: frozenset = frozenset({"CREATE_TICKET", "ESCALATE_TO_HUMAN"})



    def _handle_understanding_or_diagnosing(self, state, message, username):
        if state.ticket_declined:
            # User previously declined a ticket, but the issue still exists.
            bot_text = (
                f"I understand the {state.category} issue still exists. "
                f"However, we have exhausted all recommended troubleshooting steps and you previously declined creating a ticket. "
                f"Would you like me to go ahead and create a ServiceNow ticket now, or is there anything else I can assist you with?"
            )
            self._transition(state, ConversationPhase.WAITING_TICKET_CONFIRMATION, "offering ticket again after decline")
            return self._reply(state, message, bot_text, "ASK_MORE_INFO")

        """
        Gemini-first reasoning handler (UNDERSTANDING / DIAGNOSING phases).

        Flow:
          1. Call generate_decision() — Gemini reasons as IT engineer, KB injected via RAG.
          2. If privileged intent → enter KB TROUBLESHOOTING phase (LAPS/approval flow).
          3. If ticket intent → transition to WAITING_TICKET_CONFIRMATION.
          4. If diagnosable intent → transition to AI_TROUBLESHOOTING (multi-turn).
          5. Fallback: DiagnosticEngine if Gemini unavailable.
        """
        import app.services.orchestrator_service as orchestrator_service
        import app.services.conversation_memory as mem

        history = mem.get_history(state.session_id)

        try:
            decision = orchestrator_service.generate_decision(
                category=state.category,
                history=history,
                user_message=message,
            )
            gemini_response = decision.get("assistant_message", "")
            intent = decision.get("intent", "GENERAL_SUPPORT")
            requires_confirmation = decision.get("requires_confirmation", False)
            
            from app.services.observability_service import log_event
            log_event(
                "Intent detected",
                intent=intent,
                category=state.category,
                phase=state.phase.value,
                llm_confidence=decision.get("confidence", 0.0),
                model_name=decision.get("model_name")
            )
            log_event(
                "Category detected",
                category=state.category,
                phase=state.phase.value
            )
        except Exception as exc:
            logger.warning(
                "ConversationService: Gemini decision failed (%s) — falling back to DiagnosticEngine.",
                exc,
            )
            gemini_response = ""
            intent = "GENERAL_SUPPORT"
            requires_confirmation = False
            
            from app.services.observability_service import log_event
            log_event(
                "Intent detected",
                intent="GENERAL_SUPPORT",
                category=state.category,
                phase=state.phase.value,
                llm_confidence=0.0
            )
            log_event(
                "Category detected",
                category=state.category,
                phase=state.phase.value
            )

        # ── Privileged operation → KB TROUBLESHOOTING (LAPS / approval) ─────────
        if intent in self._PRIVILEGED_INTENTS and not requires_confirmation:
            step_text = self._kb.start_troubleshooting(state, message)
            if step_text:
                self._transition(
                    state, ConversationPhase.TROUBLESHOOTING,
                    f"Privileged intent {intent} — starting KB troubleshooting",
                )
                from app.services.observability_service import log_event
                log_event("Troubleshooting step suggested", category=state.category, phase=state.phase.value)
                greeting = (
                    f"I understand you need assistance with this {state.category} issue. "
                    f"Let me guide you through the required steps.\n\n"
                )
                return self._reply(state, message, greeting + step_text, "ASK_MORE_INFO")

        # ── Ticket intent → offer ticket creation ────────────────────────────────
        if intent in self._TICKET_INTENTS:
            escalation_reason = decision.get("escalation_reason", "")
            
            is_justified = (
                state.troubleshooting_steps_suggested > 0
                or escalation_reason in ("ADMIN_REQUIRED", "HARDWARE_FAILURE", "USER_REQUESTED", "POLICY_REQUIRED")
                or self._is_ticket_request(message)
            )



            from app.services.observability_service import log_event
            log_event(
                "Ticket recommendation generated",
                intent=intent,
                category=state.category,
                phase=state.phase.value,
                escalation_reason=escalation_reason,
                escalation_blocked=not is_justified
            )

            if not is_justified:
                logger.info("Blocked premature escalation in understanding phase. Insufficient evidence of troubleshooting.")
                intent = "GENERAL_SUPPORT"
                
                log_event(
                    "Premature escalation blocked",
                    intent=intent,
                    category=state.category,
                    phase=state.phase.value,
                    escalation_reason=escalation_reason,
                    escalation_blocked=True
                )
                
                # Context-Preserving Response Modification
                import re
                ticket_phrases = r"(?i)\b(I (will|can) (create|raise|open|submit) a ticket|Let me (create|raise|open) a ticket|I'm going to escalate|I'll escalate|I'll raise a support request|Would you like me to create a ticket)\b[^.]*\.?"
                cleaned_response = re.sub(ticket_phrases, "", gemini_response).strip()
                
                if cleaned_response and len(cleaned_response.split()) > 5:
                    gemini_response = cleaned_response
                else:
                    gemini_response = "I need to ask a few more questions to diagnose this properly before we escalate. Could you provide a bit more detail about what you're experiencing?"
            else:
                self._transition(state, ConversationPhase.WAITING_TICKET_CONFIRMATION,
                                 f"Gemini signalled {intent} — offering ticket")
                prompt = format_ticket_prompt()
                if gemini_response:
                    has_ticket_offering = any(kw in gemini_response.lower() for kw in ["create a ticket", "create a servicenow ticket", "open a ticket", "escalate to", "support ticket", "raise a ticket", "would you like me to"])
                    if has_ticket_offering:
                        prompt = gemini_response
                    else:
                        prompt = f"{gemini_response}\n\n{format_ticket_prompt()}"
                return self._reply(state, message, prompt, "ASK_MORE_INFO")

        # Log questions/steps if any
        if 'decision' in locals() and decision:
            act_type = decision.get("action_type", "")
            from app.services.observability_service import log_event
            if act_type == "QUESTION" and "?" in gemini_response:
                log_event("Clarifying question asked", clarifying_questions_asked=state.clarifying_questions_asked, troubleshooting_steps_suggested=state.troubleshooting_steps_suggested)
            elif act_type == "STEP":
                log_event("Troubleshooting step suggested", clarifying_questions_asked=state.clarifying_questions_asked, troubleshooting_steps_suggested=state.troubleshooting_steps_suggested)

        # ── Diagnosable intent → AI_TROUBLESHOOTING multi-turn ───────────────────
        # Gemini's first response is already a good opening — show it and enter session.
        if gemini_response and intent in self._DIAGNOSABLE_INTENTS:
            self._transition(
                state, ConversationPhase.AI_TROUBLESHOOTING,
                f"Diagnosable intent {intent} — entering AI multi-turn troubleshooting",
            )
            return self._reply(state, message, gemini_response, "ASK_MORE_INFO")

        # ── Any other Gemini response — show it and stay in UNDERSTANDING ────────
        if gemini_response:
            return self._reply(state, message, gemini_response, "ASK_MORE_INFO")

        # ── Gemini unavailable — DiagnosticEngine fallback ───────────────────────
        import app.services.diagnostic_engine as de

        if state.phase == ConversationPhase.DIAGNOSING:
            last_agent_message = ""
            history_turns = mem.get_history(state.session_id)
            for turn in reversed(history_turns):
                if turn.get("sender") == "agent":
                    last_agent_message = turn.get("text", "")
                    break
            if last_agent_message:
                ans = de.extract_answers(state.category, message, last_agent_message)
                for k, v in ans.items():
                    state.diagnostic_answers[k] = v

        if de.is_confidence_high(state.category, message, state.diagnostic_answers):
            step_text = self._kb.start_troubleshooting(state, message)
            if step_text:
                self._transition(state, ConversationPhase.TROUBLESHOOTING, "Fallback: confidence high — starting KB")
                greeting = f"Let me assist you with your {state.category} issue.\n\n"
                return self._reply(state, message, greeting + step_text, "ASK_MORE_INFO")
            return self._reply(state, message, self._llm.converse(state, message), "ASK_MORE_INFO")

        question = de.get_next_question(state.category, state.diagnostic_answers)
        if question:
            self._transition(state, ConversationPhase.DIAGNOSING, "Fallback: asking diagnostic question")
            return self._reply(state, message, question, "ASK_MORE_INFO")

        step_text = self._kb.start_troubleshooting(state, message)
        if step_text:
            self._transition(state, ConversationPhase.TROUBLESHOOTING, "Fallback: questions exhausted — starting KB")
            greeting = f"Let me assist you with your {state.category} issue.\n\n"
            return self._reply(state, message, greeting + step_text, "ASK_MORE_INFO")

        return self._reply(state, message, self._llm.converse(state, message), "ASK_MORE_INFO")

    def _handle_ai_troubleshooting(self, state, message, username):
        """
        Multi-turn AI-guided troubleshooting handler (AI_TROUBLESHOOTING phase).

        Called on every turn after the initial UNDERSTANDING→AI_TROUBLESHOOTING transition.

        Behaviour:
          - Injects a continuation instruction so Gemini knows it's mid-session.
          - Gemini reviews full history, does NOT repeat previous steps.
          - Adapts its next step to the user's latest response.
          - Escalates to WAITING_TICKET_CONFIRMATION when CREATE_TICKET signalled.
          - Transitions to TROUBLESHOOTING (KB+LAPS) for privileged intent mid-session.
          - Falls back to LlmOrchestrator.converse() if Gemini unavailable.
        """
        import app.services.orchestrator_service as orchestrator_service
        import app.services.conversation_memory as mem
        from app.services.prompt_builder import build_troubleshooting_continuation_prompt

        history = mem.get_history(state.session_id)

        # Build continuation instruction — tells Gemini it's mid-session
        continuation_msg = build_troubleshooting_continuation_prompt(
            state.category,
            message,
            clarifying_questions_asked=state.clarifying_questions_asked,
            troubleshooting_steps_suggested=state.troubleshooting_steps_suggested,
        )

        try:
            decision = orchestrator_service.generate_decision(
                category=state.category,
                history=history,
                user_message=continuation_msg,
            )
            intent = decision.get("intent", "GENERAL_SUPPORT")
            response = decision.get("assistant_message", "")
            requires_confirmation = decision.get("requires_confirmation", False)
            
            from app.services.observability_service import log_event
            log_event(
                "Intent detected",
                intent=intent,
                category=state.category,
                phase=state.phase.value,
                llm_confidence=decision.get("confidence", 0.0),
                model_name=decision.get("model_name")
            )
            log_event(
                "Category detected",
                category=state.category,
                phase=state.phase.value
            )
        except Exception as exc:
            logger.warning("ConversationService: AI troubleshooting decision failed: %s — using LLM fallback.", exc)
            from app.services.observability_service import log_event
            log_event(
                "Intent detected",
                intent="GENERAL_SUPPORT",
                category=state.category,
                phase=state.phase.value,
                llm_confidence=0.0
            )
            log_event(
                "Category detected",
                category=state.category,
                phase=state.phase.value
            )
            return self._reply(state, message, self._llm.converse(state, message), "ASK_MORE_INFO")

        # Extract engine-validated metadata
        action_type = decision.get("action_type", "")
        if action_type == "QUESTION" and "?" in response:
            state.clarifying_questions_asked += 1
            from app.services.observability_service import log_event
            log_event("Clarifying question asked", clarifying_questions_asked=state.clarifying_questions_asked, troubleshooting_steps_suggested=state.troubleshooting_steps_suggested)
        elif action_type == "STEP":
            state.troubleshooting_steps_suggested += 1
            from app.services.observability_service import log_event
            log_event("Troubleshooting step suggested", clarifying_questions_asked=state.clarifying_questions_asked, troubleshooting_steps_suggested=state.troubleshooting_steps_suggested)

        if intent in self._TICKET_INTENTS:
            escalation_reason = decision.get("escalation_reason", "")
            
            is_justified = (
                state.troubleshooting_steps_suggested > 0
                or escalation_reason in ("ADMIN_REQUIRED", "HARDWARE_FAILURE", "USER_REQUESTED", "POLICY_REQUIRED")
                or self._is_ticket_request(message)
            )



            from app.services.observability_service import log_event
            log_event(
                "Ticket recommendation generated",
                intent=intent,
                category=state.category,
                phase=state.phase.value,
                escalation_reason=escalation_reason,
                escalation_blocked=not is_justified
            )

            if not is_justified:
                logger.info("Blocked premature escalation. Insufficient evidence of troubleshooting.")
                intent = "GENERAL_SUPPORT"
                
                log_event(
                    "Premature escalation blocked",
                    intent=intent,
                    category=state.category,
                    phase=state.phase.value,
                    escalation_reason=escalation_reason,
                    escalation_blocked=True
                )
                
                # Context-Preserving Response Modification
                import re
                # Strip out ticket creation phrasing but preserve troubleshooting context
                ticket_phrases = r"(?i)\b(I (will|can) (create|raise|open|submit) a ticket|Let me (create|raise|open) a ticket|I'm going to escalate|I'll escalate|I'll raise a support request|Would you like me to create a ticket)\b[^.]*\.?"
                cleaned_response = re.sub(ticket_phrases, "", response).strip()
                
                if cleaned_response and len(cleaned_response.split()) > 5:
                    response = cleaned_response
                else:
                    # Fallback only if the entire message was about a ticket
                    response = "I need to ask a few more questions to diagnose this properly before we escalate. Could you provide a bit more detail about what you're experiencing?"

        # ── Escalation: Gemini signals ticket creation ────────────────────────
        if intent in self._TICKET_INTENTS:
            self._transition(
                state, ConversationPhase.WAITING_TICKET_CONFIRMATION,
                f"AI troubleshooting: Gemini signalled {intent} — offering ticket",
            )
            ticket_prompt = format_ticket_prompt()
            if response:
                has_ticket_offering = any(kw in response.lower() for kw in ["create a ticket", "create a servicenow ticket", "open a ticket", "escalate to", "support ticket", "raise a ticket", "would you like me to"])
                if has_ticket_offering:
                    ticket_prompt = response
                else:
                    ticket_prompt = f"{response}\n\n{format_ticket_prompt()}"
            return self._reply(state, message, ticket_prompt, "ASK_MORE_INFO")

        # ── Privileged operation detected mid-troubleshooting ─────────────────
        if intent in self._PRIVILEGED_INTENTS and not requires_confirmation:
            step_text = self._kb.start_troubleshooting(state, message)
            if step_text:
                self._transition(
                    state, ConversationPhase.TROUBLESHOOTING,
                    f"Privileged intent {intent} detected during AI troubleshooting",
                )
                from app.services.observability_service import log_event
                log_event("Troubleshooting step suggested", category=state.category, phase=state.phase.value)
                return self._reply(state, message, step_text, "ASK_MORE_INFO")

        # ── Continue troubleshooting ──────────────────────────────────────────
        if response:
            return self._reply(state, message, response, "ASK_MORE_INFO")

        # ── LLM fallback ──────────────────────────────────────────────────────
        return self._reply(state, message, self._llm.converse(state, message), "ASK_MORE_INFO")


    def _handle_troubleshooting(self, state, message, username):
        ts = state.troubleshooting_session
        step_details = troubleshooting_service.current_step(ts)
        approval = approval_service.detect_approval(message)

        if approval.status == approval_service.ApprovalStatus.APPROVED:
            troubleshooting_service.mark_completed(ts)
            next_d = troubleshooting_service.next_step(ts)
            if next_d:
                from app.services.observability_service import log_event
                log_event("Troubleshooting step suggested", category=state.category, phase=state.phase.value)
                return self._reply(state, message, format_step(next_d), "ASK_MORE_INFO")
            self._transition(state, ConversationPhase.VERIFYING, "all steps completed — approved")
            return self._reply(state, message, format_verification(troubleshooting_service.get_verification(ts)), "ASK_MORE_INFO")

        if approval.status == approval_service.ApprovalStatus.REJECTED:
            troubleshooting_service.mark_completed(ts)
            next_d = troubleshooting_service.next_step(ts)
            if next_d:
                from app.services.observability_service import log_event
                log_event("Troubleshooting step suggested", category=state.category, phase=state.phase.value)
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
        logger.info(
            ">>> ENTRY [ConversationService._handle_waiting_ticket]: "
            "session=%s, username=%s, category=%s, phase=%s, "
            "user_message='%s', approval_status=%s",
            state.session_id,
            username,
            state.category,
            getattr(state.phase, 'value', str(state.phase)),
            message,
            approval.status,
        )
        if approval.status == approval_service.ApprovalStatus.APPROVED:
            logger.info(">>> APPROVED BRANCH: Proceeding with ticket creation for session=%s (username=%s, category=%s)", state.session_id, username, state.category)
            try:
                ticket = self._tickets.create(state, username)
                logger.info("<<< EXIT [ConversationService._handle_waiting_ticket]: Ticket creation returned: %s", ticket)
            except Exception as exc:
                import traceback
                logger.error("!!! ERROR [ConversationService._handle_waiting_ticket]: Ticket creation failed with exception: %s\n%s", exc, traceback.format_exc())
                raise

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
            req_type = ticket.get("request_type", "INCIDENT")
            from app.services.observability_service import log_event
            if req_type == "SERVICE_REQUEST":
                log_event("Service request created", category=state.category, phase=state.phase.value, ticket_id=tid)
            else:
                log_event("Ticket created", category=state.category, phase=state.phase.value, ticket_id=tid)
            if ticket.get("requires_approval") or req_type == "SERVICE_REQUEST":
                log_event("Manager approval requested", category=state.category, phase=state.phase.value, ticket_id=tid)

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
            state.ticket_declined = True
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
            req_type = ticket.get("request_type", "INCIDENT")
            from app.services.observability_service import log_event
            if req_type == "SERVICE_REQUEST":
                log_event("Service request created", category=state.category, phase=state.phase.value, ticket_id=tid)
            else:
                log_event("Ticket created", category=state.category, phase=state.phase.value, ticket_id=tid)
            if ticket.get("requires_approval") or req_type == "SERVICE_REQUEST":
                log_event("Manager approval requested", category=state.category, phase=state.phase.value, ticket_id=tid)

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
        """User explicitly asked to create a ticket — prompt for confirmation or create it."""
        if state.phase == ConversationPhase.ESCALATED and state.active_ticket:
            return self._reply(state, message, format_status_response(state.active_ticket), "ASK_MORE_INFO")

        if state.phase in (
            ConversationPhase.UNDERSTANDING,
            ConversationPhase.DIAGNOSING,
            ConversationPhase.AI_TROUBLESHOOTING,
            ConversationPhase.TROUBLESHOOTING,
        ):
            self._transition(state, ConversationPhase.WAITING_TICKET_CONFIRMATION, "user requested ticket creation")
            return self._reply(state, message, format_ticket_prompt(), "ASK_MORE_INFO")

        logger.info(">>> ENTRY [ConversationService._handle_ticket_command]: Creating ticket for session=%s (username=%s, category=%s)", state.session_id, username, state.category)
        try:
            ticket = self._tickets.create(state, username)
            logger.info("<<< EXIT [ConversationService._handle_ticket_command]: Ticket creation returned: %s", ticket)
        except Exception as exc:
            import traceback
            logger.error("!!! ERROR [ConversationService._handle_ticket_command]: Ticket creation failed with exception: %s\n%s", exc, traceback.format_exc())
            raise

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
        req_type = ticket.get("request_type", "INCIDENT")
        from app.services.observability_service import log_event
        if req_type == "SERVICE_REQUEST":
            log_event("Service request created", category=state.category, phase=state.phase.value, ticket_id=tid)
        else:
            log_event("Ticket created", category=state.category, phase=state.phase.value, ticket_id=tid)
        if ticket.get("requires_approval") or req_type == "SERVICE_REQUEST":
            log_event("Manager approval requested", category=state.category, phase=state.phase.value, ticket_id=tid)

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

    def _handle_greeting(self, state, message):
        """Handle a greeting by resetting troubleshooting context and responding naturally."""
        state.category = "GENERAL"
        state.reset_troubleshooting()
        self._transition(state, ConversationPhase.UNDERSTANDING, "user greeted agent")
        greeting_text = (
            "Hello! 👋 How can I help you today?\n\n"
            "Examples:\n"
            "• VPN not connecting\n"
            "• Outlook not opening\n"
            "• Need software installation\n"
            "• Printer issue"
        )
        return self._reply(state, message, greeting_text, "ASK_MORE_INFO")

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

    # ── Execution time estimates per category ────────────────────────────────
    _EXEC_TIME: dict = {
        "VPN": "5–10 minutes",
        "Driver": "10–15 minutes",
        "Software": "10–20 minutes",
        "SAP": "5–10 minutes",
        "Printer": "5–10 minutes",
        "Registry": "5 minutes",
        "Service": "2–5 minutes",
        "Adobe": "15–20 minutes",
        "Citrix": "10–15 minutes",
        "PowerBI": "10–15 minutes",
        "Office": "15–25 minutes",
        "Outlook": "5–10 minutes",
        "Network": "5–10 minutes",
        "Password": "2–5 minutes",
        "Hardware": "varies — contact IT",
    }

    @staticmethod
    def _get_exec_time(category: str) -> str:
        """Return estimated execution time for a given category."""
        for key, val in ConversationService._EXEC_TIME.items():
            if key.lower() in (category or "").lower():
                return val
        return "10–15 minutes"

    @staticmethod
    def _compute_confidence(message: str, keywords_hit: list[str]) -> tuple[int, str]:
        """Return (confidence_pct, reasoning_sentence) based on matched keywords."""
        n = len(keywords_hit)
        if n >= 4:
            pct = 97
        elif n == 3:
            pct = 93
        elif n == 2:
            pct = 87
        elif n == 1:
            pct = 79
        else:
            pct = 72

        # Build human-readable reasoning
        if keywords_hit:
            kw_str = ", ".join(f'"{k}"' for k in keywords_hit[:3])
            reasoning = (
                f"Detected privileged operation indicator{'s' if n > 1 else ''} "
                f"({kw_str}) — this action requires system-level privilege elevation "
                f"beyond standard user permissions."
            )
        else:
            reasoning = (
                "Based on the request category and description, this action is likely "
                "to require administrator access to complete successfully."
            )
        return pct, reasoning

    def handle_chat_turn(
        self,
        session_id: Optional[str],
        message: str,
        username: Optional[str] = None,
        user_role: Optional[str] = None,
    ) -> dict:
        import time
        from app.core.logging_context import request_id_ctx
        t0 = time.time()
        req_id = request_id_ctx.get() or "N/A"
        logger.info(">>> TRACE PIPELINE START: ConversationService.handle_chat_turn | Request ID: %s | Session ID: %s | Msg: %s", req_id, session_id, message)
        try:
            res = self._handle_chat_turn_internal(session_id, message, username, user_role)
            
            # Log conversation state after the turn
            try:
                state = self._session_mgr.get(res.get("session_id"))
                if state:
                    ts = state.troubleshooting_session
                    logger.info(
                        "\n=== Conversation State ===\n"
                        "Issue: %s\n"
                        "Playbook: %s\n"
                        "Step: %s\n"
                        "Workflow: %s\n"
                        "Locked: %s\n"
                        "Ticket Offered: %s\n"
                        "Ticket Declined: %s\n"
                        "==========================",
                        state.active_issue or "GENERAL",
                        f"{state.category.lower()}_guide" if state.category else "N/A",
                        ts.current_step if ts else "N/A",
                        state.phase.value if hasattr(state.phase, 'value') else state.phase,
                        state.conversation_locked,
                        state.ticket_offered,
                        state.ticket_declined
                    )
            except Exception as dbg_ex:
                logger.warning("Debug logging conversation state failed: %s", dbg_ex)

            elapsed = (time.time() - t0) * 1000
            logger.info("<<< TRACE PIPELINE END: ConversationService.handle_chat_turn | Request ID: %s | Session ID: %s | Elapsed: %.2f ms", req_id, res.get("session_id"), elapsed)
            return res
        except Exception as exc:
            elapsed = (time.time() - t0) * 1000
            logger.error("!!! TRACE PIPELINE ERROR: ConversationService.handle_chat_turn | Request ID: %s | Session ID: %s | Elapsed: %.2f ms | Error: %s", req_id, session_id, elapsed, exc, exc_info=True)
            raise

    def _handle_chat_turn_internal(
        self,
        session_id: Optional[str],
        message: str,
        username: Optional[str] = None,
        user_role: Optional[str] = None,
    ) -> dict:
        import time
        from app.core.logging_context import session_id_ctx, user_ctx, role_ctx, turn_start_time_ctx
        from app.services.observability_service import log_event

        # Track start time for latency calculations
        turn_start_time_ctx.set(time.time())

        from app.services.intent_router import IntentRouter, IntentType

        # 1. Route message — deterministic, priority-ordered
        logger.info(">>> TRACE STAGE: Message Routing Start")
        t_route = time.time()
        
        conversation_locked = False
        current_cat = None
        if session_id:
            state_temp = self._session_mgr.get(session_id)
            if state_temp:
                conversation_locked = state_temp.conversation_locked
        router = IntentRouter()
        try:
            route = router.route(message, conversation_locked, current_cat)
        except TypeError:
            route = router.route(message)
        logger.info("<<< TRACE STAGE: Message Routing End | Category: %s | Intent: %s | Elapsed: %.2f ms", route.category, route.intent.value, (time.time() - t_route) * 1000)

        # 2. Session load or create (use route category for new sessions)
        detected_category = route.category or "GENERAL"
        logger.info(">>> TRACE STAGE: Session Load/Create Start | Detected Category: %s", detected_category)
        t_session = time.time()
        session_id, state = self._session_mgr.load_or_create(session_id, detected_category)
        logger.info("<<< TRACE STAGE: Session Load/Create End | Session ID: %s | Phase: %s | Elapsed: %.2f ms", session_id, state.phase.value, (time.time() - t_session) * 1000)



        # Set thread/async context variables
        session_id_ctx.set(session_id or "")
        user_ctx.set(username or "anonymous")
        role_ctx.set(user_role or "anonymous")

        # Telemetry logs
        is_new_conversation = len(state.conversation_history) == 0
        if is_new_conversation:
            log_event("Conversation started", category=detected_category, phase=state.phase.value)

        log_event("Intent detected", intent=route.intent.value, category=detected_category, phase=state.phase.value)
        log_event("Category detected", category=detected_category, phase=state.phase.value)

        # ── LAPS active ticket chat workflow & Admin privilege check ──────────
        from app.database.session import get_db
        
        # Helper check for admin privileges
        def requires_admin_privileges(category: str, msg: str) -> bool:
            m_l = msg.lower()
            keywords = [
                # Core admin terms
                "admin", "administrator", "elevate", "elevation", "privilege",
                # Registry
                "registry", "regedit", "regedit.exe", "hkey",
                # Drivers
                "driver", "install driver", "update driver", "device driver",
                "uninstall driver",
                # Services
                "spooler", "service restart", "restart service", "start service",
                "stop service", "sc start", "sc stop", "net start", "net stop",
                # Windows system locations / tools
                "system32", "syswow64", "group policy", "gpupdate", "gpedit",
                "msc", "mmc",
                # Security features
                "uac", "user account control", "run as administrator",
                "elevated", "elevated prompt", "elevated command",
                # Software installation (requiring elevation)
                "software requiring elevation", "msi install", ".msi",
                "setup.exe", "installer.exe",
                # Uninstall operations
                "uninstall", "remove software", "remove program",
            ]
            if any(kw in m_l for kw in keywords):
                return True
            return False

        if state.active_ticket:
            with get_db() as db:
                from app.database.models.ticket import Ticket
                from app.services.rbac_audit_service import log_rbac_event
                db_ticket = db.query(Ticket).filter(Ticket.ticket_id == state.active_ticket).first()
                if db_ticket:
                    # If ticket is resolved/closed/rejected, clear it
                    if db_ticket.status in ("CLOSED", "RESOLVED", "FULFILLED", "REJECTED"):
                        state.active_ticket = ""
                        state.phase = ConversationPhase.UNDERSTANDING
                    else:
                        if db_ticket.status in ("WAITING_MANAGER_APPROVAL", "WAITING_MANAGER"):
                            mgr = db_ticket.manager or "your manager"
                            bot_text = (
                                f"I've already escalated ticket **{db_ticket.ticket_id}** to **{mgr}** for sign-off — "
                                f"no action needed from you right now. \n\n"
                                f"The moment your manager approves, I'll automatically route this to the IT Admin Queue "
                                f"and guide you through the next steps. Is there anything else I can help you with in the meantime?"
                            )
                            return self._build_payload(state, bot_text, "WAITING_MANAGER")
                        elif db_ticket.status in ("WAITING_ADMIN_APPROVAL", "WAITING_ADMIN"):
                            bot_text = (
                                f"Good news — your manager has signed off on ticket **{db_ticket.ticket_id}**. \n\n"
                                f"It's now sitting in the **IT Admin Queue** for final credential approval. "
                                f"Once an IT admin grants access, your temporary LAPS password will appear in "
                                f"**My Tickets → Ticket Details** and I'll walk you through the exact steps to use it."
                            )
                            return self._build_payload(state, bot_text, "WAITING_ADMIN")
                        elif db_ticket.status == "TEMP_ADMIN_GRANTED":
                            m_l = message.lower()
                            if any(w in m_l for w in ["yes", "done", "completed", "worked", "it worked", "success"]):
                                db_ticket.status = "CLOSED"
                                db_ticket.laps_active = False
                                db_ticket.laps_password = None
                                db_ticket.closed_at = datetime.utcnow()
                                db.commit()
                                
                                from app.services.timeline_service import TimelineService
                                TimelineService.log_event(
                                    db=db,
                                    ticket_id=db_ticket.ticket_id,
                                    event_type="LAPS_REVOKED",
                                    actor="system",
                                    action="revoke laps",
                                    description="Temporary privilege revoked upon user completion."
                                )
                                TimelineService.log_event(
                                    db=db,
                                    ticket_id=db_ticket.ticket_id,
                                    event_type="TICKET_CLOSED",
                                    actor="system",
                                    action="close ticket",
                                    description="Ticket successfully closed and verified by user."
                                )
                                log_rbac_event(
                                    user=username or "Employee",
                                    role="EMPLOYEE",
                                    action="update_ticket_lifecycle",
                                    ticket_id=db_ticket.ticket_id,
                                    old_state="TEMP_ADMIN_GRANTED",
                                    new_state="CLOSED",
                                    details={"action": "user_completed", "note": "Temporary LAPS privileges revoked."}
                                )
                                db.commit()
                                
                                old_tid = db_ticket.ticket_id
                                state.active_ticket = ""
                                state.phase = ConversationPhase.RESOLVED
                                self._repo.persist(state, message, "Privileges revoked and ticket closed.")
                                bot_text = f"Excellent! I have successfully verified completion of the task, revoked your temporary administrative privileges, and closed Ticket **{old_tid}**. An audit log has been filed. Let me know if you need help with anything else!"
                                return self._build_payload(state, bot_text, "RESOLVED")
                            
                            elif any(w in m_l for w in ["no", "failed", "did not work", "error", "broken"]):
                                db_ticket.status = "CLOSED"
                                db_ticket.laps_active = False
                                db_ticket.laps_password = None
                                db_ticket.closed_at = datetime.utcnow()
                                db.commit()
                                
                                from app.services.timeline_service import TimelineService
                                TimelineService.log_event(
                                    db=db,
                                    ticket_id=db_ticket.ticket_id,
                                    event_type="LAPS_REVOKED",
                                    actor="system",
                                    action="revoke laps",
                                    description="Temporary privilege revoked due to execution failure."
                                )
                                TimelineService.log_event(
                                    db=db,
                                    ticket_id=db_ticket.ticket_id,
                                    event_type="TICKET_CLOSED",
                                    actor="system",
                                    action="close ticket",
                                    description="Ticket closed due to troubleshooting failure."
                                )
                                log_rbac_event(
                                    user=username or "Employee",
                                    role="EMPLOYEE",
                                    action="update_ticket_lifecycle",
                                    ticket_id=db_ticket.ticket_id,
                                    old_state="TEMP_ADMIN_GRANTED",
                                    new_state="CLOSED",
                                    details={"action": "user_failed", "note": "Temporary LAPS privileges revoked after failure."}
                                )
                                db.commit()
                                
                                old_tid = db_ticket.ticket_id
                                state.active_ticket = ""
                                state.phase = ConversationPhase.UNDERSTANDING
                                self._repo.persist(state, message, "Privileges revoked after failure.")
                                bot_text = f"I'm sorry to hear that the fix didn't work. For security, I have revoked the temporary administrator privileges and closed Ticket **{old_tid}**. Would you like me to start a new troubleshooting session or escalate this to manual support?"
                                return self._build_payload(state, bot_text, "PLAIN")
                            
                            else:
                                cat = (db_ticket.category or "").lower()
                                est = self._get_exec_time(db_ticket.category or "")
                                tid_ref = db_ticket.ticket_id

                                # Build category-aware execution guide
                                if any(k in cat for k in ["driver", "device"]):
                                    steps = (
                                        "1. Open **Device Manager** → right-click the device → *Update Driver*\n"
                                        "2. Choose **Browse my computer** → point to the driver folder\n"
                                        "3. Click **Install** — enter the LAPS password when UAC prompts\n"
                                        "4. Wait for the installation to complete and verify the device is working"
                                    )
                                elif any(k in cat for k in ["software", "install", "adobe", "citrix"]):
                                    steps = (
                                        "1. Locate the installer (e.g., `setup.exe` or `.msi` file)\n"
                                        "2. **Right-click → Run as Administrator** — enter the LAPS password when prompted\n"
                                        "3. Follow the installation wizard to completion\n"
                                        "4. Launch the application to confirm it installed successfully"
                                    )
                                elif any(k in cat for k in ["registry", "regedit"]):
                                    steps = (
                                        "1. Press **Win + R**, type `regedit`, press Enter\n"
                                        "2. Enter the LAPS password at the UAC prompt\n"
                                        "3. Navigate to the key specified in your ticket description\n"
                                        "4. Make the required change and close Registry Editor"
                                    )
                                elif any(k in cat for k in ["service", "spooler"]):
                                    steps = (
                                        "1. Press **Win + R**, type `services.msc`, press Enter\n"
                                        "2. Enter the LAPS password at the UAC prompt\n"
                                        "3. Locate the service in the list → right-click → **Restart**\n"
                                        "4. Verify the service status shows **Running**"
                                    )
                                elif any(k in cat for k in ["vpn"]):
                                    steps = (
                                        "1. Open the **VPN client** → Settings\n"
                                        "2. If prompted for elevation, enter the LAPS password\n"
                                        "3. Re-configure the connection profile as needed\n"
                                        "4. Attempt to connect and confirm the VPN tunnel establishes"
                                    )
                                elif any(k in cat for k in ["printer"]):
                                    steps = (
                                        "1. Go to **Settings → Bluetooth & devices → Printers & scanners**\n"
                                        "2. Click **Add device** or select the existing printer\n"
                                        "3. If a driver install prompt appears, enter the LAPS password\n"
                                        "4. Print a test page to confirm the printer is working"
                                    )
                                else:
                                    steps = (
                                        "1. Open the relevant application or tool\n"
                                        "2. Enter the LAPS password at any **UAC** / administrator prompts\n"
                                        "3. Complete the required action\n"
                                        "4. Verify the issue is resolved"
                                    )

                                bot_text = (
                                    f"🔐 **Your temporary admin credentials are ready** for ticket **{tid_ref}**.\n\n"
                                    f"Open **My Tickets → Ticket Details** to reveal and copy the LAPS password. "
                                    f"You have **15 minutes** before it expires — estimated task time: **{est}**.\n\n"
                                    f"**Here's exactly what to do:**\n{steps}\n\n"
                                    f"⚠️ Do not share the password. Once you're finished, reply **'done'** and I'll "
                                    f"immediately revoke the credentials and close the ticket with a full audit trail."
                                )
                                return self._build_payload(state, bot_text, "TEMP_ADMIN_GRANTED")

        # ── Turn 1 check for required admin privileges ───────────────────────
        if state.phase in (ConversationPhase.UNDERSTANDING, ConversationPhase.DIAGNOSING):
            from app.services.itsm_classifier import classify_request
            classification = classify_request(detected_category, message)
            
            if classification.request_type == "SERVICE_REQUEST":
                ticket = self._tickets.create(state, username)
                if not ticket or ticket.get("error"):
                    self._transition(state, ConversationPhase.WAITING_SN_RECOVERY, "ServiceNow failure")
                    bot_text = "Ticketing system is currently unavailable. Please try again later."
                    self._repo.persist(state, message, bot_text)
                    return self._build_payload(state, bot_text, "ERROR")
                    
                tid = ticket.get("ticket_id", "N/A")
                from app.services.observability_service import log_event
                log_event("Service request created", category=detected_category, phase=state.phase.value, ticket_id=tid)
                log_event("Manager approval requested", category=detected_category, phase=state.phase.value, ticket_id=tid)

                with get_db() as db:
                    from app.database.models.ticket import Ticket
                    db_ticket = db.query(Ticket).filter(Ticket.ticket_id == tid).first()
                    if db_ticket:
                        db_ticket.status = "WAITING_MANAGER"
                        db_ticket.approval_status = "PENDING"
                        db.commit()

                        # Log the service request creation in the timeline
                        from app.services.timeline_service import TimelineService
                        est_sr = self._get_exec_time(detected_category)
                        TimelineService.log_event(
                            db=db,
                            ticket_id=tid,
                            event_type="SERVICE_REQUEST_CREATED",
                            actor="AI Agent",
                            action="service_request_created",
                            description=(
                                f"Service Request raised for '{detected_category}'. "
                                f"AI Confidence: 92%. "
                                f"Requires dual approval (Manager → IT Admin) per Bridgestone IT policy. "
                                f"Estimated installation time: {est_sr}."
                            )
                        )
                        db.commit()
                        
                self._transition(state, ConversationPhase.ESCALATED, f"service request created — {tid}")
                state.active_ticket = tid
                self._repo.persist(state, message, f"Service Request ticket {tid} created.")
                est = self._get_exec_time(detected_category)
                mgr_name = "your manager"
                bot_text = (
                    f"I've identified this as a **software installation / access request** for "
                    f"**{detected_category}** — per Bridgestone IT policy, this requires "
                    f"manager and IT admin approval before I can provision access.\n\n"
                    f"I've opened Service Request **{tid}** and routed it directly to "
                    f"{mgr_name} for sign-off. No action needed from you right now. \n\n"
                    f"Once both approvals are in, I'll walk you through the installation "
                    f"step-by-step. Estimated setup time once approved: **{est}**."
                )

                payload = self._build_payload(state, bot_text, "TICKET_CREATED")
                payload.update({
                    "ticket_created": True,
                    "ticket_id": tid,
                    "ticket": ticket,
                    "request_type": "SERVICE_REQUEST",
                    "ticket_status": "WAITING_MANAGER",
                    "estimated_minutes": est,
                    "ai_confidence": 92,
                    "ai_reasoning": f"Request category '{detected_category}' matched enterprise software installation policy — requires dual approval (Manager + IT Admin) before privileged access is granted.",
                })
                return payload
            
            elif requires_admin_privileges(detected_category, message):
                ticket = self._tickets.create(state, username)
                if not ticket or ticket.get("error"):
                    self._transition(state, ConversationPhase.WAITING_SN_RECOVERY, "ServiceNow failure")
                    bot_text = "Ticketing system is currently unavailable. Please try again later."
                    self._repo.persist(state, message, bot_text)
                    return self._build_payload(state, bot_text, "ERROR")
                    
                tid = ticket.get("ticket_id", "N/A")
                from app.services.observability_service import log_event
                log_event("Ticket created", category=detected_category, phase=state.phase.value, ticket_id=tid)
                log_event("Manager approval requested", category=detected_category, phase=state.phase.value, ticket_id=tid)

                with get_db() as db:
                    from app.database.models.ticket import Ticket
                    db_ticket = db.query(Ticket).filter(Ticket.ticket_id == tid).first()
                    if db_ticket:
                        db_ticket.status = "WAITING_MANAGER_APPROVAL"
                        db_ticket.approval_status = "PENDING"
                        db_ticket.request_type = "PRIVILEGED_ACTION"
                        db_ticket.manager = "manager"
                        db.commit()

                        # Log AI diagnosis in the timeline immediately at ticket creation
                        # Note: hits and confidence_pct are computed below; use a placeholder here
                        # The full AI_DIAGNOSIS event is logged after confidence is computed

                        
                self._transition(state, ConversationPhase.ESCALATED, f"incident requires admin privileges — {tid}")
                state.active_ticket = tid
                self._repo.persist(state, message, f"Incident ticket {tid} created.")

                # Compute confidence from matched keywords
                m_lower = message.lower()
                priv_keywords = [
                    "admin", "administrator", "elevate", "elevation", "privilege",
                    "registry", "regedit", "driver", "install driver", "update driver",
                    "spooler", "service restart", "restart service",
                    "system32", "group policy", "gpupdate",
                    "uac", "user account control", "run as administrator",
                    "elevated", ".msi", "setup.exe", "uninstall",
                ]
                hits = [kw for kw in priv_keywords if kw in m_lower]
                confidence_pct, reasoning = self._compute_confidence(message, hits)
                est = self._get_exec_time(detected_category)

                # Log the AI diagnosis decision in the timeline now that we have confidence
                try:
                    with get_db() as db_log:
                        from app.services.timeline_service import TimelineService
                        TimelineService.log_event(
                            db=db_log,
                            ticket_id=tid,
                            event_type="AI_DIAGNOSIS",
                            actor="AI Agent",
                            action="privileged_action_detected",
                            description=(
                                f"AI Confidence: {confidence_pct}%. {reasoning} "
                                f"Estimated execution time: {est}. "
                                f"Ticket routed to Manager → IT Admin approval chain."
                            )
                        )
                        db_log.commit()
                except Exception:
                    pass  # Don't fail ticket creation if timeline logging fails

                bot_text = (
                    f"After reviewing your case, I've flagged this as a **privileged operation**. \n\n"
                    f"**AI Assessment** (confidence: {confidence_pct}%): {reasoning}\n\n"
                    f"I've opened Incident **{tid}** and sent it through the privileged access "
                    f"approval chain (Manager → IT Admin). Estimated resolution time once approved: **{est}**.\n\n"
                    f"I'll automatically resume guiding you through the fix the moment your credentials are ready — "
                    f"just keep this chat open."
                )

                payload = self._build_payload(state, bot_text, "TICKET_CREATED")
                payload.update({
                    "ticket_created": True,
                    "ticket_id": tid,
                    "ticket": ticket,
                    "request_type": "PRIVILEGED_ACTION",
                    "ticket_status": "WAITING_MANAGER_APPROVAL",
                    "ai_confidence": confidence_pct,
                    "ai_reasoning": reasoning,
                    "estimated_minutes": est,
                })
                return payload

        # Check if the active troubleshooting step requires admin privileges
        if state.phase == ConversationPhase.TROUBLESHOOTING:
            ts = state.troubleshooting_session
            step_details = troubleshooting_service.current_step(ts) if ts else None
            t_l = step_details.get("title", "").lower() if step_details else ""
            i_l = step_details.get("instruction", "").lower() if step_details else ""
            step_req_admin = any(kw in t_l or kw in i_l for kw in ["admin", "administrator", "elevate", "elevation", "privilege", "registry", "regedit", "driver", "install driver", "spooler", "service restart"])
            
            if requires_admin_privileges(state.category, message) or step_req_admin:
                ticket = self._tickets.create(state, username)
                if not ticket or ticket.get("error"):
                    self._transition(state, ConversationPhase.WAITING_SN_RECOVERY, "ServiceNow failure")
                    bot_text = "Ticketing system is currently unavailable. Please try again later."
                    self._repo.persist(state, message, bot_text)
                    return self._build_payload(state, bot_text, "ERROR")
                    
                tid = ticket.get("ticket_id", "N/A")
                from app.services.observability_service import log_event
                log_event("Ticket created", category=state.category, phase=state.phase.value, ticket_id=tid)
                log_event("Manager approval requested", category=state.category, phase=state.phase.value, ticket_id=tid)

                with get_db() as db:
                    from app.database.models.ticket import Ticket
                    db_ticket = db.query(Ticket).filter(Ticket.ticket_id == tid).first()
                    if db_ticket:
                        db_ticket.status = "WAITING_MANAGER_APPROVAL"
                        db_ticket.approval_status = "PENDING"
                        db_ticket.request_type = "PRIVILEGED_ACTION"
                        db_ticket.manager = "manager"
                        db.commit()
                        
                self._transition(state, ConversationPhase.ESCALATED, f"troubleshooting step requires admin — {tid}")
                state.active_ticket = tid
                self._repo.persist(state, message, f"Incident ticket {tid} created.")

                m_lower = message.lower()
                priv_kws = [
                    "admin", "administrator", "elevate", "elevation", "privilege",
                    "registry", "regedit", "driver", "install driver", "update driver",
                    "spooler", "service restart", "restart service",
                    "system32", "group policy", "gpupdate",
                    "uac", "user account control", "run as administrator",
                    "elevated", ".msi", "setup.exe", "uninstall",
                ]
                hits = [kw for kw in priv_kws if kw in m_lower]
                confidence_pct, reasoning = self._compute_confidence(message, hits)
                est = self._get_exec_time(state.category or detected_category or "")

                bot_text = (
                    f"I've hit a step in the troubleshooting process that requires **elevated privileges** "
                    f"to continue. \n\n"
                    f"**AI Assessment** (confidence: {confidence_pct}%): {reasoning}\n\n"
                    f"I've opened Incident **{tid}** and routed it through the privileged access workflow "
                    f"(Manager → IT Admin approval). Estimated fix time once approved: **{est}**.\n\n"
                    f"Keep this chat open — as soon as your credentials are ready I'll pick up right where we left off."
                )

                payload = self._build_payload(state, bot_text, "TICKET_CREATED")
                payload.update({
                    "ticket_created": True,
                    "ticket_id": tid,
                    "ticket": ticket,
                    "request_type": "PRIVILEGED_ACTION",
                    "ticket_status": "WAITING_MANAGER_APPROVAL",
                    "ai_confidence": confidence_pct,
                    "ai_reasoning": reasoning,
                    "estimated_minutes": est,
                })
                return payload


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
            from app.services.observability_service import log_event
            log_event("Manager approval requested", category=state.category, phase=state.phase.value)
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

        if route.intent == IntentType.GREETING:
            return self._handle_greeting(state, message)

        # 4. RESOLVED_KEYWORD — only triggers in active troubleshooting phases
        #    Never claims success unless user explicitly confirms.
        if route.intent == IntentType.RESOLVED_KEYWORD:
            _active_phases = (
                ConversationPhase.TROUBLESHOOTING,
                ConversationPhase.AI_TROUBLESHOOTING,
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
                should_switch = False
                if not state.conversation_locked:
                    should_switch = True
                else:
                    from app.services.intent_router import _is_generic_followup
                    is_generic = _is_generic_followup(message)
                    if not is_generic and _contains_category_keyword(message, detected):
                        should_switch = True

                if should_switch:
                    old = state.category
                    self._save_category_state(state)
                    state.category = detected
                    state.active_issue = detected
                    self._restore_category_state(state, detected)
                    self._tl.log_transition(state.session_id, old, detected, "category switch")
                    
                    if state.phase == ConversationPhase.UNDERSTANDING or not state.troubleshooting_session:
                        self._transition(state, ConversationPhase.UNDERSTANDING, "Category switch — reset to UNDERSTANDING")
                        return self._handle_understanding_or_diagnosing(state, message, username)
                        
                    # Immediately return the restored troubleshooting step to avoid executing
                    # the phase handler on the correction message itself
                    ts = state.troubleshooting_session
                    step_details = troubleshooting_service.current_step(ts)
                    if step_details:
                        return self._reply(state, message, format_step(step_details), "ASK_MORE_INFO")


        # 6. Phase dispatch
        phase = state.phase
        logger.info(">>> TRACE STAGE: Phase Dispatch Start | Phase: %s", phase.value if hasattr(phase, 'value') else phase)
        t_phase = time.time()
        try:
            if phase in (ConversationPhase.UNDERSTANDING, ConversationPhase.DIAGNOSING):
                res = self._handle_understanding_or_diagnosing(state, message, username)
            elif phase == ConversationPhase.AI_TROUBLESHOOTING:
                res = self._handle_ai_troubleshooting(state, message, username)
            elif phase == ConversationPhase.TROUBLESHOOTING:
                if not state.troubleshooting_session:
                    self._transition(state, ConversationPhase.UNDERSTANDING, "guard: ts lost — reset")
                    res = self._handle_understanding_or_diagnosing(state, message, username)
                else:
                    res = self._handle_troubleshooting(state, message, username)
            elif phase == ConversationPhase.VERIFYING:
                res = self._handle_verifying(state, message, username)
            elif phase == ConversationPhase.WAITING_ACTION_CONFIRMATION:
                res = self._handle_waiting_action(state, message, username)
            elif phase == ConversationPhase.WAITING_TICKET_CONFIRMATION:
                res = self._handle_waiting_ticket(state, message, username)
            elif phase == ConversationPhase.WAITING_SN_RECOVERY:
                res = self._handle_sn_recovery(state, message, username)
            else:
                res = self._handle_terminal(state, message, username)
            logger.info("<<< TRACE STAGE: Phase Dispatch End | Phase: %s | Elapsed: %.2f ms", phase.value if hasattr(phase, 'value') else phase, (time.time() - t_phase) * 1000)
            return res
        except Exception as exc:
            logger.error("!!! TRACE STAGE ERROR: Phase Dispatch Failed | Phase: %s | Elapsed: %.2f ms | Error: %s", phase.value if hasattr(phase, 'value') else phase, (time.time() - t_phase) * 1000, exc, exc_info=True)
            raise


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
