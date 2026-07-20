"""
tests/test_intent_router.py
─────────────────────────────────────────────────────────────────────────────
Comprehensive tests for the Enterprise Intent Router and its integration
inside ConversationService.

Coverage:
  Unit (IntentRouter.route):
    1.  "create ticket" / "raise ticket" / "open incident"  → TICKET_COMMAND
    2.  "restart" / "start over" / "new issue"              → RESTART
    3.  "cancel" / "abort" / "stop"                         → CANCEL
    4.  "ticket status" / "my ticket"                       → STATUS
    5.  "working" / "fixed" / "solved" / "issue resolved"   → RESOLVED_KEYWORD
    6.  "vpn not working"                                   → IT_ISSUE (VPN)
    7.  "thanks" / "hello"                                  → GENERAL
    8.  Input normalization (uppercase, extra spaces)

  Unit (detect_ticket_failure_intent):
    9.  "retry" / "1"                                       → RETRY
    10. "save draft" / "2"                                  → DRAFT
    11. "helpdesk" / "3"                                    → HELPDESK
    12. random text                                         → UNKNOWN

  Integration (ConversationService):
    13. TICKET_COMMAND from UNDERSTANDING → jumps to WAITING_TICKET_CONFIRMATION
    14. TICKET_COMMAND from TROUBLESHOOTING → jumps to WAITING_TICKET_CONFIRMATION
    15. RESTART mid-TROUBLESHOOTING → resets to UNDERSTANDING
    16. CANCEL in UNDERSTANDING → cancel ack, stays UNDERSTANDING
    17. CANCEL in TROUBLESHOOTING → cancel ack, resets to UNDERSTANDING
    18. CANCEL in WAITING_TICKET_CONFIRMATION → ticket declined, resets to UNDERSTANDING
    19. STATUS with no active ticket → status_not_found response
    20. STATUS with active ticket → status_response with ticket ID
    21. RESOLVED_KEYWORD in TROUBLESHOOTING → immediate RESOLVED
    22. RESOLVED_KEYWORD in UNDERSTANDING (not active) → falls through, no RESOLVED
    23. ServiceNow failure → transitions to WAITING_SN_RECOVERY, offers options
    24. WAITING_SN_RECOVERY + "retry" → retries SN, creates ticket on success
    25. WAITING_SN_RECOVERY + still failing → stays in WAITING_SN_RECOVERY
    26. WAITING_SN_RECOVERY + "2" (draft) → saves draft, resets to UNDERSTANDING
    27. WAITING_SN_RECOVERY + "3" (helpdesk) → helpdesk info, resets to UNDERSTANDING
    28. max_automatic_actions=3 → stops at 3 and offers ticket
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional
from unittest.mock import patch

import pytest

# ─────────────────────────────────────────────────────────────────────────────
# Shared stubs (mirrors those in test_conversation_state_machine.py)
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class _FakeTS:
    article_id: str = "KB0001"
    current_step: int = 1
    completed_steps: List[int] = field(default_factory=list)
    attempts: int = 0
    finished: bool = False
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)


_STEP1 = {"step": 1, "title": "Restart GlobalProtect", "instruction": "Close and reopen it.", "image": "", "caption": ""}
_STEP2 = {"step": 2, "title": "Check credentials", "instruction": "Re-enter credentials.", "image": "", "caption": ""}
_VERIFICATION = ["Is your VPN now connected?"]


class _StubSessionManager:
    def __init__(self) -> None:
        self._store: Dict[str, Any] = {}

    def get(self, session_id: str):
        return self._store.get(session_id)

    def create(self, category: str):
        from app.services.conversation_service import SessionState
        sid = str(uuid.uuid4())
        state = SessionState(session_id=sid, category=category)
        self._store[sid] = state
        return sid, state

    def load_or_create(self, session_id, category):
        if session_id:
            state = self.get(session_id)
            if state is not None:
                return session_id, state
        return self.create(category)

    def save_to_cache(self, state) -> None:
        self._store[state.session_id] = state

    def inject(self, state) -> None:
        self._store[state.session_id] = state


class _KbFoundOrchestrator:
    def start_troubleshooting(self, state, message):
        ts = _FakeTS()
        state.troubleshooting_session = ts
        return f"**Step 1: {_STEP1['title']}**\n{_STEP1['instruction']}\nHave you completed this step?"


class _KbMissOrchestrator:
    def start_troubleshooting(self, state, message):
        return None


class _StubTicketOrchestrator:
    def create(self, state, username=None):
        return {
            "ticket_id": "INC000099",
            "assigned_team": "Network Team",
            "priority": "HIGH",
            "sla_hours": 4,
            "servicenow_id": "SN0099",
        }


class _FailingTicketOrchestrator:
    """Always fails to create a ticket."""
    def create(self, state, username=None):
        return {"error": True, "message": "ServiceNow unavailable"}


class _RetrySuccessTicketOrchestrator:
    """Fails on first attempt, succeeds on second."""
    def __init__(self):
        self._attempt = 0

    def create(self, state, username=None):
        self._attempt += 1
        if self._attempt == 1:
            return {"error": True, "message": "ServiceNow unavailable"}
        return {
            "ticket_id": "INC000099",
            "assigned_team": "Network Team",
            "priority": "HIGH",
            "sla_hours": 4,
            "servicenow_id": "SN0099",
        }


class _StubLlm:
    def converse(self, state, message):
        return f"[Gemini] I can help with your {state.category} issue."

    def converse_with_step(self, state, message, step_details):
        return f"[Gemini Explanation] The step is: {step_details.get('title')}."


class _StubRepo:
    def persist(self, state, user_message, bot_text):
        import app.services.conversation_memory as memory
        memory.append_turn_pair(state.session_id, user_message, bot_text, state.category)

    def serialize_ts(self, state):
        pass

    def restore_ts(self, state):
        pass


class _StubTransitionLogger:
    def __init__(self):
        self.records = []

    def log_transition(self, session_id, prev, next_, reason):
        self.records.append({"session_id": session_id, "prev": str(prev), "next": str(next_), "reason": reason})


class _NoActionEngine:
    def get_next_action(self, category, attempted):
        return None

    def execute(self, action):
        return {"status": "ERROR", "message": "Failed."}


class _CountingActionEngine:
    """Returns dummy actions up to `max_count`, then None."""
    def __init__(self, max_count: int = 5):
        self._max = max_count

    def get_next_action(self, category, attempted):
        from app.services.action_engine import ActionDef
        idx = len(attempted)
        if idx >= self._max:
            return None
        return ActionDef(name=f"Action_{idx}", tool="NOOP", requires_confirmation=False)

    def execute(self, action):
        return {"status": "ERROR", "message": "Failed so ticket is offered."}


@dataclass
class _ApprovalStub:
    class ApprovalStatus:
        APPROVED = "APPROVED"
        REJECTED = "REJECTED"
        UNKNOWN = "UNKNOWN"

    @dataclass
    class ApprovalResult:
        status: str
        confidence: float = 1.0
        matched_phrase: str = ""
        reason: str = ""


def _approval_approved():
    return _ApprovalStub.ApprovalResult(status="APPROVED", matched_phrase="yes")


def _approval_rejected():
    return _ApprovalStub.ApprovalResult(status="REJECTED", matched_phrase="no")


def _approval_unknown():
    return _ApprovalStub.ApprovalResult(status="UNKNOWN", matched_phrase="thanks")


def _make_svc(kb=None, session_mgr=None, ticket=None, llm=None, action_engine=None):
    from app.services.conversation_service import ConversationService
    sm = session_mgr or _StubSessionManager()
    tl = _StubTransitionLogger()
    return (
        ConversationService(
            session_mgr=sm,
            kb_orch=kb or _KbFoundOrchestrator(),
            ticket_orch=ticket or _StubTicketOrchestrator(),
            llm_orch=llm or _StubLlm(),
            repo=_StubRepo(),
            transition_logger=tl,
            action_engine=action_engine or _NoActionEngine(),
        ),
        sm,
        tl,
    )


def _phase(sm, sid):
    return sm.get(sid).phase


def _patch_ts(monkeypatch):
    import app.services.troubleshooting_service as ts_mod
    from tests.test_conversation_state_machine import _TsService
    stub = _TsService()
    monkeypatch.setattr(ts_mod, "current_step", stub.current_step)
    monkeypatch.setattr(ts_mod, "next_step", stub.next_step)
    monkeypatch.setattr(ts_mod, "mark_completed", stub.mark_completed)
    monkeypatch.setattr(ts_mod, "is_finished", stub.is_finished)
    monkeypatch.setattr(ts_mod, "get_verification", stub.get_verification)


# ─────────────────────────────────────────────────────────────────────────────
# Unit tests — IntentRouter.route()
# ─────────────────────────────────────────────────────────────────────────────

class TestIntentRouterUnit:
    """Unit tests for the pure IntentRouter.route() method (no LLM calls)."""

    def _router(self):
        from app.services.intent_router import IntentRouter
        r = IntentRouter()
        # Stub out the LLM classifier so we don't call Gemini
        r._classify_category = lambda msg: "GENERAL"
        return r

    def test_ticket_command_create(self):
        from app.services.intent_router import IntentType
        result = self._router().route("create a ticket")
        assert result.intent == IntentType.TICKET_COMMAND

    def test_ticket_command_raise(self):
        from app.services.intent_router import IntentType
        result = self._router().route("raise an incident please")
        assert result.intent == IntentType.TICKET_COMMAND

    def test_ticket_command_open(self):
        from app.services.intent_router import IntentType
        result = self._router().route("open a support ticket")
        assert result.intent == IntentType.TICKET_COMMAND

    def test_ticket_command_scalate(self):
        from app.services.intent_router import IntentType
        result = self._router().route("please escalate this")
        assert result.intent == IntentType.TICKET_COMMAND

    def test_restart(self):
        from app.services.intent_router import IntentType
        for phrase in ("restart", "start over", "new issue", "fresh start", "reset"):
            assert self._router().route(phrase).intent == IntentType.RESTART, phrase

    def test_password_reset_priority(self):
        from app.services.intent_router import IntentType
        for phrase in ("Reset password", "Reset my password", "Corporate password reset", "Forgot password", "Password expired", "Cannot login", "Change password", "Unlock account", "Temporary password"):
            result = self._router().route(phrase)
            assert result.intent == IntentType.IT_ISSUE, phrase
            assert result.category == "PASSWORD_RESET", phrase

    def test_cancel(self):
        from app.services.intent_router import IntentType
        for phrase in ("cancel", "abort", "stop", "never mind", "forget it", "quit"):
            assert self._router().route(phrase).intent == IntentType.CANCEL, phrase

    def test_status(self):
        from app.services.intent_router import IntentType
        for phrase in ("ticket status", "my ticket", "check ticket", "track ticket"):
            assert self._router().route(phrase).intent == IntentType.STATUS, phrase

    def test_resolved_keyword(self):
        from app.services.intent_router import IntentType
        for phrase in ("working", "fixed", "solved", "issue resolved", "it works", "all good", "sorted"):
            assert self._router().route(phrase).intent == IntentType.RESOLVED_KEYWORD, phrase

    def test_general_thanks(self):
        from app.services.intent_router import IntentType
        result = self._router().route("thanks")
        assert result.intent == IntentType.GENERAL

    def test_general_hello(self):
        from app.services.intent_router import IntentType
        result = self._router().route("hello there")
        assert result.intent == IntentType.GREETING

    def test_priority_ticket_over_restart(self):
        """'create ticket and restart' — TICKET_COMMAND must win."""
        from app.services.intent_router import IntentType
        result = self._router().route("create a ticket and restart")
        assert result.intent == IntentType.TICKET_COMMAND

    def test_priority_restart_over_cancel(self):
        """'restart and cancel' — RESTART must win (higher priority)."""
        from app.services.intent_router import IntentType
        result = self._router().route("restart and cancel")
        assert result.intent == IntentType.RESTART

    def test_input_normalization_uppercase(self):
        """Normalization: 'CREATE A TICKET' should still route correctly."""
        from app.services.intent_router import IntentType
        result = self._router().route("CREATE A TICKET")
        assert result.intent == IntentType.TICKET_COMMAND

    def test_input_normalization_extra_spaces(self):
        """Normalization: '  cancel  ' should still route to CANCEL."""
        from app.services.intent_router import IntentType
        result = self._router().route("  cancel  ")
        assert result.intent == IntentType.CANCEL

    def test_it_issue_vpn(self):
        """When LLM returns VPN, route should be IT_ISSUE with category=VPN."""
        from app.services.intent_router import IntentType, IntentRouter
        r = IntentRouter()
        r._classify_category = lambda msg: "VPN"
        result = r.route("vpn not working")
        assert result.intent == IntentType.IT_ISSUE
        assert result.category == "VPN"

    def test_it_issue_general_stays_general(self):
        """When LLM returns GENERAL, route should be GENERAL fallback."""
        from app.services.intent_router import IntentType, IntentRouter
        r = IntentRouter()
        r._classify_category = lambda msg: "GENERAL"
        result = r.route("I have a question")
        assert result.intent == IntentType.GENERAL


# ─────────────────────────────────────────────────────────────────────────────
# Unit tests — detect_ticket_failure_intent()
# ─────────────────────────────────────────────────────────────────────────────

class TestDetectTicketFailureIntent:
    """Unit tests for the SN recovery intent detector."""

    def test_retry_phrase(self):
        from app.services.intent_router import TicketFailureIntent, detect_ticket_failure_intent
        assert detect_ticket_failure_intent("retry") == TicketFailureIntent.RETRY

    def test_retry_phrase_try_again(self):
        from app.services.intent_router import TicketFailureIntent, detect_ticket_failure_intent
        assert detect_ticket_failure_intent("try again") == TicketFailureIntent.RETRY

    def test_retry_numeric_1(self):
        from app.services.intent_router import TicketFailureIntent, detect_ticket_failure_intent
        assert detect_ticket_failure_intent("1") == TicketFailureIntent.RETRY

    def test_draft_phrase(self):
        from app.services.intent_router import TicketFailureIntent, detect_ticket_failure_intent
        assert detect_ticket_failure_intent("save draft") == TicketFailureIntent.DRAFT

    def test_draft_numeric_2(self):
        from app.services.intent_router import TicketFailureIntent, detect_ticket_failure_intent
        assert detect_ticket_failure_intent("2") == TicketFailureIntent.DRAFT

    def test_helpdesk_phrase(self):
        from app.services.intent_router import TicketFailureIntent, detect_ticket_failure_intent
        assert detect_ticket_failure_intent("contact helpdesk") == TicketFailureIntent.HELPDESK

    def test_helpdesk_numeric_3(self):
        from app.services.intent_router import TicketFailureIntent, detect_ticket_failure_intent
        assert detect_ticket_failure_intent("3") == TicketFailureIntent.HELPDESK

    def test_unknown(self):
        from app.services.intent_router import TicketFailureIntent, detect_ticket_failure_intent
        assert detect_ticket_failure_intent("I don't know") == TicketFailureIntent.UNKNOWN


# ─────────────────────────────────────────────────────────────────────────────
# Integration tests — IntentRouter inside ConversationService
# ─────────────────────────────────────────────────────────────────────────────

class TestTicketCommandIntegration:
    """Scenarios 13–14: TICKET_COMMAND intent."""

    def test_ticket_command_from_understanding(self, monkeypatch):
        """TICKET_COMMAND in UNDERSTANDING → jump to WAITING_TICKET_CONFIRMATION."""
        from app.services.conversation_service import ConversationPhase
        svc, sm, _ = _make_svc()
        # Stub router to return TICKET_COMMAND
        with patch("app.services.intent_router.IntentRouter.route") as mock_route:
            from app.services.intent_router import IntentType, RouteResult
            mock_route.return_value = RouteResult(IntentType.TICKET_COMMAND, None, "create ticket")
            r = svc.handle_chat_turn(None, "create ticket")
        sid = r["session_id"]
        assert _phase(sm, sid) == ConversationPhase.WAITING_TICKET_CONFIRMATION
        assert "ticket" in r["response"].lower()

    def test_ticket_command_from_troubleshooting(self, monkeypatch):
        """TICKET_COMMAND mid-TROUBLESHOOTING → jump to WAITING_TICKET_CONFIRMATION."""
        from app.services.conversation_service import ConversationPhase, SessionState
        _patch_ts(monkeypatch)
        svc, sm, _ = _make_svc()

        # Plant a session already in TROUBLESHOOTING
        sid = str(uuid.uuid4())
        state = SessionState(session_id=sid, category="VPN", phase=ConversationPhase.TROUBLESHOOTING)
        state.troubleshooting_session = _FakeTS()
        sm.inject(state)

        with patch("app.services.intent_router.IntentRouter.route") as mock_route:
            from app.services.intent_router import IntentType, RouteResult
            mock_route.return_value = RouteResult(IntentType.TICKET_COMMAND, None, "create ticket")
            r = svc.handle_chat_turn(sid, "create ticket")

        assert _phase(sm, sid) == ConversationPhase.WAITING_TICKET_CONFIRMATION
        assert "ticket" in r["response"].lower()

    def test_ticket_command_when_already_escalated(self, monkeypatch):
        """TICKET_COMMAND when already ESCALATED → return existing ticket status."""
        from app.services.conversation_service import ConversationPhase, SessionState
        svc, sm, _ = _make_svc()

        sid = str(uuid.uuid4())
        state = SessionState(session_id=sid, category="VPN", phase=ConversationPhase.ESCALATED)
        state.active_ticket = "INC001234"
        sm.inject(state)

        with patch("app.services.intent_router.IntentRouter.route") as mock_route:
            from app.services.intent_router import IntentType, RouteResult
            mock_route.return_value = RouteResult(IntentType.TICKET_COMMAND, None, "create ticket")
            r = svc.handle_chat_turn(sid, "create ticket")

        assert "INC001234" in r["response"]
        # Phase should remain ESCALATED (not reset)
        assert _phase(sm, sid) == ConversationPhase.ESCALATED


class TestRestartIntegration:
    """Scenario 15: RESTART intent."""

    def test_restart_mid_troubleshooting(self, monkeypatch):
        """RESTART mid-TROUBLESHOOTING → resets to UNDERSTANDING."""
        from app.services.conversation_service import ConversationPhase, SessionState
        _patch_ts(monkeypatch)
        svc, sm, tl = _make_svc()

        sid = str(uuid.uuid4())
        state = SessionState(session_id=sid, category="VPN", phase=ConversationPhase.TROUBLESHOOTING)
        state.troubleshooting_session = _FakeTS()
        sm.inject(state)

        with patch("app.services.intent_router.IntentRouter.route") as mock_route:
            from app.services.intent_router import IntentType, RouteResult
            mock_route.return_value = RouteResult(IntentType.RESTART, None, "restart")
            r = svc.handle_chat_turn(sid, "restart")

        assert _phase(sm, sid) == ConversationPhase.UNDERSTANDING
        assert sm.get(sid).troubleshooting_session is None
        # Transition logged
        restart_transitions = [t for t in tl.records if "restart" in t["reason"].lower()]
        assert len(restart_transitions) >= 1


class TestCancelIntegration:
    """Scenarios 16–18: CANCEL intent."""

    def test_cancel_in_understanding(self, monkeypatch):
        """CANCEL in UNDERSTANDING → cancel ack, stays UNDERSTANDING."""
        from app.services.conversation_service import ConversationPhase
        svc, sm, _ = _make_svc()

        with patch("app.services.intent_router.IntentRouter.route") as mock_route:
            from app.services.intent_router import IntentType, RouteResult
            mock_route.return_value = RouteResult(IntentType.CANCEL, None, "cancel")
            r = svc.handle_chat_turn(None, "cancel")
        sid = r["session_id"]
        assert _phase(sm, sid) == ConversationPhase.UNDERSTANDING
        assert any(w in r["response"].lower() for w in ["cancel", "workflow", "anything else"])

    def test_cancel_in_troubleshooting(self, monkeypatch):
        """CANCEL in TROUBLESHOOTING → cancel ack, resets to UNDERSTANDING."""
        from app.services.conversation_service import ConversationPhase, SessionState
        _patch_ts(monkeypatch)
        svc, sm, _ = _make_svc()

        sid = str(uuid.uuid4())
        state = SessionState(session_id=sid, category="VPN", phase=ConversationPhase.TROUBLESHOOTING)
        state.troubleshooting_session = _FakeTS()
        sm.inject(state)

        with patch("app.services.intent_router.IntentRouter.route") as mock_route:
            from app.services.intent_router import IntentType, RouteResult
            mock_route.return_value = RouteResult(IntentType.CANCEL, None, "cancel")
            r = svc.handle_chat_turn(sid, "cancel")

        assert _phase(sm, sid) == ConversationPhase.UNDERSTANDING
        assert sm.get(sid).troubleshooting_session is None

    def test_cancel_in_waiting_ticket(self, monkeypatch):
        """CANCEL in WAITING_TICKET_CONFIRMATION → ticket declined, resets to UNDERSTANDING."""
        from app.services.conversation_service import ConversationPhase, SessionState
        svc, sm, _ = _make_svc()

        sid = str(uuid.uuid4())
        state = SessionState(session_id=sid, category="VPN", phase=ConversationPhase.WAITING_TICKET_CONFIRMATION)
        sm.inject(state)

        with patch("app.services.intent_router.IntentRouter.route") as mock_route:
            from app.services.intent_router import IntentType, RouteResult
            mock_route.return_value = RouteResult(IntentType.CANCEL, None, "cancel")
            r = svc.handle_chat_turn(sid, "cancel")

        assert _phase(sm, sid) == ConversationPhase.UNDERSTANDING
        assert any(w in r["response"].lower() for w in ["won't", "not", "ticket", "reach out"])


class TestStatusIntegration:
    """Scenarios 19–20: STATUS intent."""

    def test_status_no_active_ticket(self, monkeypatch):
        """STATUS with no active ticket → status_not_found response."""
        svc, sm, _ = _make_svc()

        with patch("app.services.intent_router.IntentRouter.route") as mock_route:
            from app.services.intent_router import IntentType, RouteResult
            mock_route.return_value = RouteResult(IntentType.STATUS, None, "ticket status")
            r = svc.handle_chat_turn(None, "ticket status")

        assert "create ticket" in r["response"].lower() or "no active" in r["response"].lower()

    def test_status_with_active_ticket(self, monkeypatch):
        """STATUS with active ticket → returns ticket ID in response."""
        from app.services.conversation_service import ConversationPhase, SessionState
        svc, sm, _ = _make_svc()

        sid = str(uuid.uuid4())
        state = SessionState(session_id=sid, category="VPN", phase=ConversationPhase.ESCALATED)
        state.active_ticket = "INC009876"
        sm.inject(state)

        with patch("app.services.intent_router.IntentRouter.route") as mock_route:
            from app.services.intent_router import IntentType, RouteResult
            mock_route.return_value = RouteResult(IntentType.STATUS, None, "my ticket")
            r = svc.handle_chat_turn(sid, "my ticket")

        assert "INC009876" in r["response"]


class TestResolvedKeywordIntegration:
    """Scenarios 21–22: RESOLVED_KEYWORD intent."""

    def test_resolved_keyword_in_troubleshooting(self, monkeypatch):
        """RESOLVED_KEYWORD in TROUBLESHOOTING → immediate RESOLVED."""
        from app.services.conversation_service import ConversationPhase, SessionState
        _patch_ts(monkeypatch)
        svc, sm, _ = _make_svc()

        sid = str(uuid.uuid4())
        state = SessionState(session_id=sid, category="VPN", phase=ConversationPhase.TROUBLESHOOTING)
        state.troubleshooting_session = _FakeTS()
        sm.inject(state)

        with patch("app.services.intent_router.IntentRouter.route") as mock_route:
            from app.services.intent_router import IntentType, RouteResult
            mock_route.return_value = RouteResult(IntentType.RESOLVED_KEYWORD, None, "it's working now")
            r = svc.handle_chat_turn(sid, "it's working now")

        assert _phase(sm, sid) == ConversationPhase.RESOLVED
        assert r["action"] == "RESOLVED"

    def test_resolved_keyword_in_verifying(self, monkeypatch):
        """RESOLVED_KEYWORD in VERIFYING → immediate RESOLVED."""
        from app.services.conversation_service import ConversationPhase, SessionState
        _patch_ts(monkeypatch)
        svc, sm, _ = _make_svc()

        sid = str(uuid.uuid4())
        state = SessionState(session_id=sid, category="OUTLOOK", phase=ConversationPhase.VERIFYING)
        state.troubleshooting_session = _FakeTS()
        sm.inject(state)

        with patch("app.services.intent_router.IntentRouter.route") as mock_route:
            from app.services.intent_router import IntentType, RouteResult
            mock_route.return_value = RouteResult(IntentType.RESOLVED_KEYWORD, None, "fixed")
            r = svc.handle_chat_turn(sid, "fixed")

        assert _phase(sm, sid) == ConversationPhase.RESOLVED

    def test_resolved_keyword_in_understanding_does_not_resolve(self, monkeypatch):
        """RESOLVED_KEYWORD in UNDERSTANDING → should NOT transition to RESOLVED."""
        from app.services.conversation_service import ConversationPhase
        svc, sm, _ = _make_svc(kb=_KbMissOrchestrator())

        # Patch diagnostic engine for UNDERSTANDING path
        import app.services.diagnostic_engine as de
        monkeypatch.setattr(de, "is_confidence_high", lambda cat, msg, ans: True)

        with patch("app.services.intent_router.IntentRouter.route") as mock_route:
            from app.services.intent_router import IntentType, RouteResult
            mock_route.return_value = RouteResult(IntentType.RESOLVED_KEYWORD, "GENERAL", "it works")
            r = svc.handle_chat_turn(None, "it works")
        sid = r["session_id"]

        # RESOLVED should NOT be set — UNDERSTANDING phase, not an active troubleshooting phase
        assert _phase(sm, sid) != ConversationPhase.RESOLVED


class TestServiceNowFailureRecovery:
    """Scenarios 23–27: ServiceNow failure → WAITING_SN_RECOVERY → recovery paths."""

    def _get_to_sn_failure(self, monkeypatch):
        """Helper: start session, get to WAITING_TICKET_CONFIRMATION, say yes → SN fails."""
        from app.services.conversation_service import ConversationPhase, SessionState
        svc, sm, tl = _make_svc(ticket=_FailingTicketOrchestrator())
        import app.services.approval_service as asr
        monkeypatch.setattr(asr, "detect_approval", lambda msg: _approval_approved())
        monkeypatch.setattr(asr, "ApprovalStatus", _ApprovalStub.ApprovalStatus)

        sid = str(uuid.uuid4())
        state = SessionState(session_id=sid, category="VPN", phase=ConversationPhase.WAITING_TICKET_CONFIRMATION)
        sm.inject(state)

        with patch("app.services.intent_router.IntentRouter.route") as mock_route:
            from app.services.intent_router import IntentType, RouteResult
            mock_route.return_value = RouteResult(IntentType.GENERAL, None, "yes")
            r = svc.handle_chat_turn(sid, "yes")

        assert _phase(sm, sid) == ConversationPhase.WAITING_SN_RECOVERY
        return svc, sm, tl, sid, r

    def test_sn_failure_transitions_to_waiting_sn_recovery(self, monkeypatch):
        """SN failure during ticket creation → WAITING_SN_RECOVERY."""
        from app.services.conversation_service import ConversationPhase
        _, sm, _, sid, r = self._get_to_sn_failure(monkeypatch)
        assert _phase(sm, sid) == ConversationPhase.WAITING_SN_RECOVERY
        assert "retry" in r["response"].lower()
        assert "draft" in r["response"].lower()
        assert "helpdesk" in r["response"].lower()

    def test_retry_success(self, monkeypatch):
        """WAITING_SN_RECOVERY + 'retry' → retries and creates ticket on success."""
        from app.services.conversation_service import ConversationPhase, SessionState
        retry_ticket = _RetrySuccessTicketOrchestrator()
        svc, sm, tl = _make_svc(ticket=retry_ticket)
        import app.services.approval_service as asr
        monkeypatch.setattr(asr, "detect_approval", lambda msg: _approval_approved())
        monkeypatch.setattr(asr, "ApprovalStatus", _ApprovalStub.ApprovalStatus)

        # First call fails → WAITING_SN_RECOVERY
        sid = str(uuid.uuid4())
        state = SessionState(session_id=sid, category="VPN", phase=ConversationPhase.WAITING_TICKET_CONFIRMATION)
        sm.inject(state)

        with patch("app.services.intent_router.IntentRouter.route") as mock_route:
            from app.services.intent_router import IntentType, RouteResult
            mock_route.return_value = RouteResult(IntentType.GENERAL, None, "yes")
            svc.handle_chat_turn(sid, "yes")

        assert _phase(sm, sid) == ConversationPhase.WAITING_SN_RECOVERY

        # Second call: user says retry → success
        with patch("app.services.intent_router.IntentRouter.route") as mock_route:
            from app.services.intent_router import IntentType, RouteResult
            mock_route.return_value = RouteResult(IntentType.GENERAL, None, "retry")
            with patch("app.services.intent_router.detect_ticket_failure_intent") as mock_fi:
                from app.services.intent_router import TicketFailureIntent
                mock_fi.return_value = TicketFailureIntent.RETRY
                r = svc.handle_chat_turn(sid, "retry")

        assert _phase(sm, sid) == ConversationPhase.ESCALATED
        assert r["ticket_created"] is True
        assert "INC000099" in r["response"]

    def test_retry_still_failing(self, monkeypatch):
        """WAITING_SN_RECOVERY + retry → still fails → stays in WAITING_SN_RECOVERY."""
        from app.services.conversation_service import ConversationPhase, SessionState
        svc, sm, _ = _make_svc(ticket=_FailingTicketOrchestrator())

        sid = str(uuid.uuid4())
        state = SessionState(session_id=sid, category="VPN", phase=ConversationPhase.WAITING_SN_RECOVERY)
        sm.inject(state)

        with patch("app.services.intent_router.IntentRouter.route") as mock_route, \
             patch("app.services.intent_router.detect_ticket_failure_intent") as mock_fi:
            from app.services.intent_router import IntentType, RouteResult, TicketFailureIntent
            mock_route.return_value = RouteResult(IntentType.GENERAL, None, "retry")
            mock_fi.return_value = TicketFailureIntent.RETRY
            r = svc.handle_chat_turn(sid, "retry")

        assert _phase(sm, sid) == ConversationPhase.WAITING_SN_RECOVERY
        assert "retry" in r["response"].lower()

    def test_save_draft(self, monkeypatch):
        """WAITING_SN_RECOVERY + '2' (draft) → saves draft, resets to UNDERSTANDING."""
        from app.services.conversation_service import ConversationPhase, SessionState
        svc, sm, _ = _make_svc(ticket=_FailingTicketOrchestrator())

        sid = str(uuid.uuid4())
        state = SessionState(session_id=sid, category="VPN", phase=ConversationPhase.WAITING_SN_RECOVERY)
        state.ticket_draft = {"category": "VPN", "description": "VPN not connecting from home"}
        sm.inject(state)

        with patch("app.services.intent_router.IntentRouter.route") as mock_route, \
             patch("app.services.intent_router.detect_ticket_failure_intent") as mock_fi:
            from app.services.intent_router import IntentType, RouteResult, TicketFailureIntent
            mock_route.return_value = RouteResult(IntentType.GENERAL, None, "2")
            mock_fi.return_value = TicketFailureIntent.DRAFT
            r = svc.handle_chat_turn(sid, "2")

        assert _phase(sm, sid) == ConversationPhase.UNDERSTANDING
        assert "draft" in r["response"].lower() or "saved" in r["response"].lower()

    def test_contact_helpdesk(self, monkeypatch):
        """WAITING_SN_RECOVERY + '3' (helpdesk) → helpdesk info, resets to UNDERSTANDING."""
        from app.services.conversation_service import ConversationPhase, SessionState
        svc, sm, _ = _make_svc(ticket=_FailingTicketOrchestrator())

        sid = str(uuid.uuid4())
        state = SessionState(session_id=sid, category="VPN", phase=ConversationPhase.WAITING_SN_RECOVERY)
        sm.inject(state)

        with patch("app.services.intent_router.IntentRouter.route") as mock_route, \
             patch("app.services.intent_router.detect_ticket_failure_intent") as mock_fi:
            from app.services.intent_router import IntentType, RouteResult, TicketFailureIntent
            mock_route.return_value = RouteResult(IntentType.GENERAL, None, "3")
            mock_fi.return_value = TicketFailureIntent.HELPDESK
            r = svc.handle_chat_turn(sid, "3")

        assert _phase(sm, sid) == ConversationPhase.UNDERSTANDING
        assert any(w in r["response"].lower() for w in ["helpdesk", "email", "phone"])

    def test_unknown_input_in_sn_recovery(self, monkeypatch):
        """WAITING_SN_RECOVERY + unknown → re-presents options, stays in WAITING_SN_RECOVERY."""
        from app.services.conversation_service import ConversationPhase, SessionState
        svc, sm, _ = _make_svc(ticket=_FailingTicketOrchestrator())

        sid = str(uuid.uuid4())
        state = SessionState(session_id=sid, category="VPN", phase=ConversationPhase.WAITING_SN_RECOVERY)
        sm.inject(state)

        with patch("app.services.intent_router.IntentRouter.route") as mock_route, \
             patch("app.services.intent_router.detect_ticket_failure_intent") as mock_fi:
            from app.services.intent_router import IntentType, RouteResult, TicketFailureIntent
            mock_route.return_value = RouteResult(IntentType.GENERAL, None, "hmm")
            mock_fi.return_value = TicketFailureIntent.UNKNOWN
            r = svc.handle_chat_turn(sid, "hmm")

        assert _phase(sm, sid) == ConversationPhase.WAITING_SN_RECOVERY
        assert "retry" in r["response"].lower()


class TestMaxAutomaticActions:
    """Scenario 28: max_automatic_actions enforcement."""

    def test_max_3_actions_then_ticket(self, monkeypatch):
        """After 3 attempted auto-actions, the system must offer a ticket (not more actions)."""
        from app.services.conversation_service import ConversationPhase, SessionState
        _patch_ts(monkeypatch)

        svc, sm, _ = _make_svc(action_engine=_CountingActionEngine(max_count=10))

        sid = str(uuid.uuid4())
        state = SessionState(session_id=sid, category="VPN", phase=ConversationPhase.VERIFYING)
        state.troubleshooting_session = _FakeTS()
        state.max_automatic_actions = 3
        state.attempted_actions = ["Action_0", "Action_1", "Action_2"]  # already 3 attempted
        sm.inject(state)

        import app.services.approval_service as asr
        monkeypatch.setattr(asr, "detect_approval", lambda msg: _approval_rejected())
        monkeypatch.setattr(asr, "ApprovalStatus", _ApprovalStub.ApprovalStatus)

        with patch("app.services.intent_router.IntentRouter.route") as mock_route:
            from app.services.intent_router import IntentType, RouteResult
            mock_route.return_value = RouteResult(IntentType.GENERAL, None, "no")
            r = svc.handle_chat_turn(sid, "no")

        # Must offer ticket, NOT another action
        assert _phase(sm, sid) == ConversationPhase.WAITING_TICKET_CONFIRMATION
        assert "ticket" in r["response"].lower()
        # No new action was added
        assert len(sm.get(sid).attempted_actions) == 3
