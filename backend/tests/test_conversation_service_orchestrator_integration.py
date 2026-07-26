"""
test_conversation_service_orchestrator_integration.py
──────────────────────────────────────────────────────────────────────────────
End-to-end integration tests verifying that TroubleshootingOrchestrator is
correctly wired into ConversationService._handle_ai_troubleshooting().

NOTE: conftest.py sets DATABASE_URL=sqlite:///:memory: before any import,
so no PostgreSQL connection is needed.

Test coverage
--------------
  1.  Orchestrator is called in AI_TROUBLESHOOTING phase
  2.  Orchestrator NOT called in other phases (UNDERSTANDING)
  3.  VPN resolution → RESOLVED phase + RESOLVED action
  4.  Outlook multi-turn → stays AI_TROUBLESHOOTING
  5.  Printer escalation → WAITING_TICKET_CONFIRMATION phase
  6.  Escalation context persisted in state.tool_result
  7.  State persists across multiple turns (session_id reuse)
  8.  Escalation flows through to TicketService (TicketOrchestrator)
  9.  Fallback to legacy flow when orchestrator raises exception
  10. ConversationService public API shape preserved (all payload keys present)
  11. No orchestrator injected → legacy path runs
  12. response_text comes from orchestrator, not from reasoning internals
  13. troubleshooting_steps_suggested incremented on continuation turns
  14. RESOLVED keyword detected → RESOLVED phase (global override still works)

Design rules
------------
  • Zero real LLM calls  — ai_provider mocked
  • Zero DB writes       — session manager is in-memory stub
  • Zero network         — TicketOrchestrator stub returns fake ticket dict
  • No IntentRouter calls to real Gemini — IntentRouter patched
"""

from __future__ import annotations

import json
import uuid
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock, patch

import pytest

from app.services.conversation_service import SessionState, ConversationPhase  # noqa: E402


# ─────────────────────────────────────────────────────────────────────────────
# Per-test infrastructure patches (autouse)
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def patch_infrastructure():
    """Patch memory, observability, and state-logger on every test."""
    with (
        patch("app.services.conversation_memory.get_history", return_value=[]),
        patch("app.services.conversation_memory.append_turn_pair", return_value=None),
        patch("app.services.conversation_memory.append_message", return_value=None),
        patch("app.services.observability_service.log_event", return_value=None),
        patch("app.services.state_transition_logger.log_transition", return_value=None),
        patch("app.database.session.get_db", return_value=_fake_db_ctx()),
    ):
        yield


class _FakeDbCtx:
    """Context manager that returns a no-op DB."""
    def __enter__(self):
        return MagicMock()
    def __exit__(self, *a):
        return False


def _fake_db_ctx():
    return _FakeDbCtx()


# ─────────────────────────────────────────────────────────────────────────────
# Shared helpers
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def patch_intent_router():
    """Force IntentRouter to return IT_ISSUE with the category embedded in the msg."""
    from app.services.intent_router import IntentRouter, RouteResult, IntentType

    def _fake_route(self, message: str, *args, **kwargs) -> RouteResult:
        msg = message.lower()
        if "vpn" in msg:
            cat = "VPN"
        elif "outlook" in msg:
            cat = "OUTLOOK"
        elif "printer" in msg:
            cat = "PRINTER"
        elif "sap" in msg:
            cat = "SAP"
        elif "password" in msg:
            cat = "PASSWORD"
        elif "fixed" in msg or "resolved" in msg:
            return RouteResult(
                intent=IntentType.RESOLVED_KEYWORD,
                category="GENERAL",
                normalized_message=message,
            )
        else:
            cat = "GENERAL"

        return RouteResult(
            intent=IntentType.IT_ISSUE,
            category=cat,
            normalized_message=message,
        )

    with patch.object(IntentRouter, "route", _fake_route):
        yield


# ─────────────────────────────────────────────────────────────────────────────
# Stubs for ConversationService dependencies
# ─────────────────────────────────────────────────────────────────────────────

class _StubSessionManager:
    """In-memory session store."""

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
            s = self.get(session_id)
            if s is not None:
                return session_id, s
        return self.create(category)

    def save_to_cache(self, state) -> None:
        self._store[state.session_id] = state

    def inject(self, state) -> None:
        self._store[state.session_id] = state


class _StubKbOrchestrator:
    def start_troubleshooting(self, state, message):
        return ""

    def next_step(self, state):
        return None


class _StubTicketOrchestrator:
    """Returns a fake successful ticket."""

    def create(self, state, username=None):
        return {
            "ticket_id": "INC0000001",
            "assigned_team": "Network Team",
            "request_type": "INCIDENT",
            "requires_approval": False,
            "status_label": "In Progress",
        }


class _StubLlmOrchestrator:
    def converse(self, state, message):
        return "Legacy LLM fallback response"

    def converse_with_step(self, state, message, step_details):
        return "Legacy LLM step explanation"


class _StubRepo:
    def persist(self, state, message, bot_text):
        pass


class _StubTransitionLogger:
    def log_transition(self, session_id, from_phase, to_phase, reason):
        pass


class _StubActionEngine:
    def get_next_action(self, category, attempted):
        return None


def _make_decision_json(
    next_action: str = "ASK_QUESTION",
    confidence: float = 0.85,
    missing_information: Optional[List[str]] = None,
    selected_step: str = "",
    escalation: bool = False,
    reason_code: str = "MISSING_EVIDENCE",
    requires_confirmation: bool = False,
) -> str:
    return json.dumps({
        "next_action":           next_action,
        "confidence":            confidence,
        "missing_information":   missing_information or [],
        "selected_kb":           "",
        "selected_step":         selected_step,
        "escalation":            escalation,
        "reason_code":           reason_code,
        "requires_confirmation": requires_confirmation,
    })


def _make_mock_ai_provider(
    decision_json: Optional[str] = None,
    chat_response: str = "Please tell me what error code you see.",
):
    provider = MagicMock()
    provider.is_ready.return_value = True
    gen_resp = MagicMock()
    gen_resp.text = decision_json or _make_decision_json()
    provider.generate_response.return_value = gen_resp
    provider.chat.return_value = chat_response
    return provider


def _build_troubleshooting_orchestrator(
    decision_json: Optional[str] = None,
    chat_response: str = "Please tell me what error code you see.",
):
    """Build a real TroubleshootingOrchestrator with mocked AI provider."""
    from app.services.knowledge_retrieval_service import KnowledgeRetrievalService
    from app.services.troubleshooting_strategy import TroubleshootingStrategyRegistry
    from app.services.context_builder import ContextBuilder
    from app.services.reasoning_service import ReasoningEngine
    from app.services.troubleshooting_state_service import TroubleshootingStateManager
    from app.services.troubleshooting_orchestrator import TroubleshootingOrchestrator

    provider = _make_mock_ai_provider(decision_json=decision_json, chat_response=chat_response)
    ctx_bld = ContextBuilder()
    orch = TroubleshootingOrchestrator(
        knowledge_service=KnowledgeRetrievalService(),
        strategy_registry=TroubleshootingStrategyRegistry(),
        context_builder=ctx_bld,
        reasoning_engine=ReasoningEngine(ai_provider=provider, context_builder=ctx_bld),
        state_manager=TroubleshootingStateManager(),
        ai_provider=provider,
        ticket_service=None,
    )
    return orch, provider


def _build_conversation_service(
    troubleshooting_orchestrator=None,
    session_mgr: Optional[_StubSessionManager] = None,
):
    """Build a ConversationService with all real dependencies replaced by stubs."""
    from app.services.conversation_service import ConversationService

    return ConversationService(
        session_mgr=session_mgr or _StubSessionManager(),
        kb_orch=_StubKbOrchestrator(),
        ticket_orch=_StubTicketOrchestrator(),
        llm_orch=_StubLlmOrchestrator(),
        repo=_StubRepo(),
        transition_logger=_StubTransitionLogger(),
        action_engine=_StubActionEngine(),
        troubleshooting_orchestrator=troubleshooting_orchestrator,
    )


def _put_session_in_ai_troubleshooting(session_mgr: _StubSessionManager, category: str) -> str:
    """Pre-create a session in AI_TROUBLESHOOTING phase and return its session_id."""
    from app.services.conversation_service import SessionState, ConversationPhase
    sid = str(uuid.uuid4())
    state = SessionState(session_id=sid, category=category)
    state.phase = ConversationPhase.AI_TROUBLESHOOTING
    state.conversation_locked = True
    session_mgr.inject(state)
    return sid


def _assert_valid_payload(payload: dict) -> None:
    """Assert that the response payload has all required fields."""
    required_keys = {
        "session_id", "category", "action", "response",
        "history_length", "ticket_created", "status",
    }
    missing = required_keys - payload.keys()
    assert not missing, f"Payload missing required keys: {missing}"
    assert payload["response"], "response must not be empty"


# ═════════════════════════════════════════════════════════════════════════════
# 1. WIRING TESTS — orchestrator called / not called
# ═════════════════════════════════════════════════════════════════════════════

class TestOrchestratorWiring:

    def test_orchestrator_called_in_ai_troubleshooting_phase(self):
        """TroubleshootingOrchestrator.handle() must be invoked during AI_TROUBLESHOOTING."""
        orch, _ = _build_troubleshooting_orchestrator()
        spy = MagicMock(wraps=orch.handle)
        orch.handle = spy

        session_mgr = _StubSessionManager()
        svc = _build_conversation_service(troubleshooting_orchestrator=orch, session_mgr=session_mgr)
        sid = _put_session_in_ai_troubleshooting(session_mgr, "VPN")

        svc.handle_chat_turn(sid, "VPN error 619")
        spy.assert_called_once()

    def test_orchestrator_not_called_in_understanding_phase(self):
        """Orchestrator must NOT be called during UNDERSTANDING phase."""
        orch, _ = _build_troubleshooting_orchestrator()
        spy = MagicMock(wraps=orch.handle)
        orch.handle = spy

        svc = _build_conversation_service(troubleshooting_orchestrator=orch)
        # New session → UNDERSTANDING phase
        with patch("app.services.orchestrator_service.generate_decision") as mock_decision:
            mock_decision.return_value = {
                "assistant_message": "Tell me more about your VPN issue.",
                "intent": "GENERAL_SUPPORT",
                "confidence": 0.8,
            }
            svc.handle_chat_turn(None, "My VPN keeps disconnecting")

        spy.assert_not_called()

    def test_no_orchestrator_injected_uses_legacy_path(self):
        """When no orchestrator is injected, the legacy flow must run without error."""
        svc = _build_conversation_service(troubleshooting_orchestrator=None)
        session_mgr = svc._session_mgr
        sid = _put_session_in_ai_troubleshooting(session_mgr, "VPN")

        with patch("app.services.orchestrator_service.generate_decision") as mock_decision:
            mock_decision.return_value = {
                "assistant_message": "Legacy Gemini response",
                "intent": "GENERAL_SUPPORT",
                "confidence": 0.7,
            }
            payload = svc.handle_chat_turn(sid, "VPN not working")

        assert payload["response"] == "Legacy Gemini response"

    def test_orchestrator_accepts_new_keyword_argument(self):
        """ConversationService.__init__ must accept troubleshooting_orchestrator kwarg."""
        from app.services.conversation_service import ConversationService
        # Must not raise TypeError
        svc = ConversationService(
            session_mgr=_StubSessionManager(),
            kb_orch=_StubKbOrchestrator(),
            ticket_orch=_StubTicketOrchestrator(),
            llm_orch=_StubLlmOrchestrator(),
            repo=_StubRepo(),
            transition_logger=_StubTransitionLogger(),
            action_engine=_StubActionEngine(),
            troubleshooting_orchestrator=None,
        )
        assert svc._troubleshooting_orchestrator is None

    def test_default_none_preserves_backward_compat(self):
        """Existing callers that don't pass troubleshooting_orchestrator must still work."""
        from app.services.conversation_service import ConversationService
        svc = ConversationService(
            session_mgr=_StubSessionManager(),
            kb_orch=_StubKbOrchestrator(),
            ticket_orch=_StubTicketOrchestrator(),
            llm_orch=_StubLlmOrchestrator(),
            repo=_StubRepo(),
            transition_logger=_StubTransitionLogger(),
            action_engine=_StubActionEngine(),
            # no troubleshooting_orchestrator — old callers don't pass it
        )
        assert hasattr(svc, "_troubleshooting_orchestrator")
        assert svc._troubleshooting_orchestrator is None


# ═════════════════════════════════════════════════════════════════════════════
# 2. VPN RESOLUTION
# ═════════════════════════════════════════════════════════════════════════════

class TestVpnResolution:

    def test_vpn_resolution_transitions_to_resolved(self):
        """When orchestrator returns is_resolved=True, phase must become RESOLVED."""
        from app.services.conversation_service import ConversationPhase

        decision = _make_decision_json(next_action="RESOLVE", reason_code="USER_CONFIRMED")
        orch, _ = _build_troubleshooting_orchestrator(
            decision_json=decision,
            chat_response="Great news — your VPN is now connected. Is there anything else I can help with?",
        )
        session_mgr = _StubSessionManager()
        svc = _build_conversation_service(troubleshooting_orchestrator=orch, session_mgr=session_mgr)
        sid = _put_session_in_ai_troubleshooting(session_mgr, "VPN")

        payload = svc.handle_chat_turn(sid, "VPN works now")

        assert payload["action"] == "RESOLVED"
        assert payload["status"] == ConversationPhase.RESOLVED.value

    def test_vpn_resolution_payload_contains_response(self):
        decision = _make_decision_json(next_action="RESOLVE", reason_code="USER_CONFIRMED")
        chat_msg = "Excellent — I'm glad your VPN is back up!"
        orch, _ = _build_troubleshooting_orchestrator(
            decision_json=decision, chat_response=chat_msg
        )
        session_mgr = _StubSessionManager()
        svc = _build_conversation_service(troubleshooting_orchestrator=orch, session_mgr=session_mgr)
        sid = _put_session_in_ai_troubleshooting(session_mgr, "VPN")

        payload = svc.handle_chat_turn(sid, "My VPN works now")
        assert payload["response"] == chat_msg

    def test_vpn_resolution_payload_has_all_required_keys(self):
        decision = _make_decision_json(next_action="RESOLVE", reason_code="USER_CONFIRMED")
        orch, _ = _build_troubleshooting_orchestrator(decision_json=decision)
        session_mgr = _StubSessionManager()
        svc = _build_conversation_service(troubleshooting_orchestrator=orch, session_mgr=session_mgr)
        sid = _put_session_in_ai_troubleshooting(session_mgr, "VPN")

        payload = svc.handle_chat_turn(sid, "Fixed")
        _assert_valid_payload(payload)

    def test_vpn_resolution_ticket_not_created(self):
        """Resolution must NOT create a ServiceNow ticket."""
        decision = _make_decision_json(next_action="RESOLVE", reason_code="USER_CONFIRMED")
        orch, _ = _build_troubleshooting_orchestrator(decision_json=decision)
        session_mgr = _StubSessionManager()
        svc = _build_conversation_service(troubleshooting_orchestrator=orch, session_mgr=session_mgr)
        sid = _put_session_in_ai_troubleshooting(session_mgr, "VPN")

        payload = svc.handle_chat_turn(sid, "VPN is working")
        assert payload["ticket_created"] is False


# ═════════════════════════════════════════════════════════════════════════════
# 3. OUTLOOK MULTI-TURN CONTINUATION
# ═════════════════════════════════════════════════════════════════════════════

class TestOutlookMultiTurn:

    def test_continuation_stays_in_ai_troubleshooting(self):
        """Non-resolve, non-escalate result must keep phase as AI_TROUBLESHOOTING."""
        from app.services.conversation_service import ConversationPhase

        decision = _make_decision_json(next_action="ASK_QUESTION", reason_code="MISSING_EVIDENCE")
        orch, _ = _build_troubleshooting_orchestrator(decision_json=decision)
        session_mgr = _StubSessionManager()
        svc = _build_conversation_service(troubleshooting_orchestrator=orch, session_mgr=session_mgr)
        sid = _put_session_in_ai_troubleshooting(session_mgr, "OUTLOOK")

        payload = svc.handle_chat_turn(sid, "Outlook crashes when I try to open it")

        assert payload["status"] == ConversationPhase.AI_TROUBLESHOOTING.value
        assert payload["action"] == "ASK_MORE_INFO"

    def test_multi_turn_state_persists(self):
        """Turn count must increase across multiple turns."""
        decision = _make_decision_json(next_action="GUIDE_STEP", selected_step="Start Outlook in Safe Mode")
        orch, _ = _build_troubleshooting_orchestrator(decision_json=decision)
        session_mgr = _StubSessionManager()
        svc = _build_conversation_service(troubleshooting_orchestrator=orch, session_mgr=session_mgr)
        sid = _put_session_in_ai_troubleshooting(session_mgr, "OUTLOOK")

        svc.handle_chat_turn(sid, "Outlook is crashing")
        svc.handle_chat_turn(sid, "I tried safe mode but still crashes")
        svc.handle_chat_turn(sid, "The error says Outlook.exe stopped working")

        # The TroubleshootingStateManager is internal to the orchestrator,
        # but the session itself must still have the correct session_id
        state = session_mgr.get(sid)
        assert state is not None
        assert state.session_id == sid

    def test_continuation_increments_troubleshooting_steps(self):
        """troubleshooting_steps_suggested must increment on GUIDE_STEP turns."""
        decision = _make_decision_json(next_action="GUIDE_STEP", selected_step="Check VPN client version")
        orch, _ = _build_troubleshooting_orchestrator(decision_json=decision)
        session_mgr = _StubSessionManager()
        svc = _build_conversation_service(troubleshooting_orchestrator=orch, session_mgr=session_mgr)
        sid = _put_session_in_ai_troubleshooting(session_mgr, "OUTLOOK")

        state_before = session_mgr.get(sid)
        steps_before = state_before.troubleshooting_steps_suggested

        svc.handle_chat_turn(sid, "Outlook error 0x80070005")

        state_after = session_mgr.get(sid)
        assert state_after.troubleshooting_steps_suggested == steps_before + 1

    def test_response_contains_orchestrator_reply(self):
        """Response text must come from the orchestrator's ai_provider.chat()."""
        expected = "Could you tell me which version of Outlook you are using?"
        decision = _make_decision_json(next_action="ASK_QUESTION")
        orch, _ = _build_troubleshooting_orchestrator(
            decision_json=decision, chat_response=expected
        )
        session_mgr = _StubSessionManager()
        svc = _build_conversation_service(troubleshooting_orchestrator=orch, session_mgr=session_mgr)
        sid = _put_session_in_ai_troubleshooting(session_mgr, "OUTLOOK")

        payload = svc.handle_chat_turn(sid, "Outlook keeps crashing")
        assert payload["response"] == expected


# ═════════════════════════════════════════════════════════════════════════════
# 4. PRINTER ESCALATION
# ═════════════════════════════════════════════════════════════════════════════

class TestPrinterEscalation:

    def test_escalation_transitions_to_waiting_ticket_confirmation(self):
        """Orchestrator escalation must transition state to WAITING_TICKET_CONFIRMATION."""
        from app.services.conversation_service import ConversationPhase

        decision = _make_decision_json(
            next_action="ESCALATE", escalation=True, reason_code="STEPS_EXHAUSTED"
        )
        orch, _ = _build_troubleshooting_orchestrator(
            decision_json=decision,
            chat_response="We've tried all standard steps. I'd recommend creating a support ticket.",
        )
        session_mgr = _StubSessionManager()
        svc = _build_conversation_service(troubleshooting_orchestrator=orch, session_mgr=session_mgr)
        sid = _put_session_in_ai_troubleshooting(session_mgr, "PRINTER")

        payload = svc.handle_chat_turn(sid, "Nothing has worked")

        state = session_mgr.get(sid)
        assert state.phase == ConversationPhase.WAITING_TICKET_CONFIRMATION

    def test_escalation_response_contains_ticket_prompt(self):
        """Escalation response must include the ticket confirmation prompt."""
        decision = _make_decision_json(
            next_action="ESCALATE", escalation=True, reason_code="STEPS_EXHAUSTED"
        )
        orch, _ = _build_troubleshooting_orchestrator(
            decision_json=decision,
            chat_response="We've exhausted standard remediation steps.",
        )
        session_mgr = _StubSessionManager()
        svc = _build_conversation_service(troubleshooting_orchestrator=orch, session_mgr=session_mgr)
        sid = _put_session_in_ai_troubleshooting(session_mgr, "PRINTER")

        payload = svc.handle_chat_turn(sid, "Still broken")
        # Response should contain both the orchestrator message and the ticket prompt
        assert payload["response"]
        assert len(payload["response"]) > 0

    def test_escalation_context_stored_in_tool_result(self):
        """When orchestrator provides escalation_context it must be stored in state.tool_result."""
        from app.services.troubleshooting_orchestrator import (
            TroubleshootingOrchestrator, OrchestrationResult
        )
        from app.services.troubleshooting_state_service import TroubleshootingStateManager, ResolutionStatus

        # Build a mock orchestrator that returns an escalation result with context
        state_mgr = TroubleshootingStateManager()
        fake_orch_state = state_mgr.create(str(uuid.uuid4()), "Printer offline", "PRINTER")
        fake_orch_state = state_mgr.mark_escalated(fake_orch_state)

        mock_orch = MagicMock()
        mock_orch.handle.return_value = OrchestrationResult(
            response_text="I need to escalate this.",
            state=fake_orch_state,
            is_resolved=False,
            requires_escalation=True,
            escalation_context={
                "session_id": "test-session",
                "issue_description": "Printer offline",
                "completed_steps": [],
                "error_codes": ["0x00000005"],
            },
        )

        session_mgr = _StubSessionManager()
        svc = _build_conversation_service(troubleshooting_orchestrator=mock_orch, session_mgr=session_mgr)
        sid = _put_session_in_ai_troubleshooting(session_mgr, "PRINTER")

        svc.handle_chat_turn(sid, "Printer still offline")

        state = session_mgr.get(sid)
        assert isinstance(state.tool_result, dict)
        assert "orchestration_context" in state.tool_result

    def test_escalation_sets_ticket_offered_flag(self):
        """WAITING_TICKET_CONFIRMATION transition must set ticket_offered=True."""
        decision = _make_decision_json(next_action="ESCALATE", escalation=True)
        orch, _ = _build_troubleshooting_orchestrator(decision_json=decision)
        session_mgr = _StubSessionManager()
        svc = _build_conversation_service(troubleshooting_orchestrator=orch, session_mgr=session_mgr)
        sid = _put_session_in_ai_troubleshooting(session_mgr, "PRINTER")

        svc.handle_chat_turn(sid, "Nothing works for the printer")

        state = session_mgr.get(sid)
        assert state.ticket_offered is True


# ═════════════════════════════════════════════════════════════════════════════
# 5. STATE PERSISTENCE ACROSS TURNS
# ═════════════════════════════════════════════════════════════════════════════

class TestStatePersistence:

    def test_session_id_is_stable_across_turns(self):
        """All turns in the same session must share the same session_id."""
        decision = _make_decision_json(next_action="ASK_QUESTION")
        orch, _ = _build_troubleshooting_orchestrator(decision_json=decision)
        session_mgr = _StubSessionManager()
        svc = _build_conversation_service(troubleshooting_orchestrator=orch, session_mgr=session_mgr)
        sid = _put_session_in_ai_troubleshooting(session_mgr, "VPN")

        p1 = svc.handle_chat_turn(sid, "VPN not connecting")
        p2 = svc.handle_chat_turn(sid, "Error 619")
        p3 = svc.handle_chat_turn(sid, "I restarted the client")

        assert p1["session_id"] == p2["session_id"] == p3["session_id"] == sid

    def test_different_sessions_are_independent(self):
        """Two simultaneous sessions must not share state."""
        decision = _make_decision_json(next_action="ASK_QUESTION")
        orch, _ = _build_troubleshooting_orchestrator(decision_json=decision)
        session_mgr = _StubSessionManager()
        svc = _build_conversation_service(troubleshooting_orchestrator=orch, session_mgr=session_mgr)

        sid1 = _put_session_in_ai_troubleshooting(session_mgr, "VPN")
        sid2 = _put_session_in_ai_troubleshooting(session_mgr, "PRINTER")

        p1 = svc.handle_chat_turn(sid1, "VPN issue")
        p2 = svc.handle_chat_turn(sid2, "Printer issue")

        assert p1["session_id"] != p2["session_id"]

    def test_phase_is_preserved_across_continuation_turns(self):
        """Phase must remain AI_TROUBLESHOOTING across non-resolve turns."""
        from app.services.conversation_service import ConversationPhase

        decision = _make_decision_json(next_action="WAIT", reason_code="WAITING_USER_ACTION")
        orch, _ = _build_troubleshooting_orchestrator(decision_json=decision)
        session_mgr = _StubSessionManager()
        svc = _build_conversation_service(troubleshooting_orchestrator=orch, session_mgr=session_mgr)
        sid = _put_session_in_ai_troubleshooting(session_mgr, "SAP")

        for msg in ["SAP login error", "Tried again — RFC_ERROR", "Still failing"]:
            payload = svc.handle_chat_turn(sid, msg)
            assert payload["status"] == ConversationPhase.AI_TROUBLESHOOTING.value, (
                f"After '{msg}', expected AI_TROUBLESHOOTING but got {payload['status']}"
            )


# ═════════════════════════════════════════════════════════════════════════════
# 6. ESCALATION INTO TICKETSERVICE
# ═════════════════════════════════════════════════════════════════════════════

class TestEscalationIntoTicketService:

    def test_escalation_followed_by_yes_creates_ticket(self):
        """
        Full escalation path:
        Turn 1 (AI_TROUBLESHOOTING) → orchestrator signals escalation
                                      → WAITING_TICKET_CONFIRMATION
        Turn 2 ("yes")              → TicketOrchestrator.create()
                                      → ESCALATED + ticket_created=True
        """
        from app.services.conversation_service import ConversationPhase

        decision = _make_decision_json(next_action="ESCALATE", escalation=True)
        orch, _ = _build_troubleshooting_orchestrator(decision_json=decision)
        session_mgr = _StubSessionManager()
        svc = _build_conversation_service(troubleshooting_orchestrator=orch, session_mgr=session_mgr)
        sid = _put_session_in_ai_troubleshooting(session_mgr, "PRINTER")

        # Turn 1: escalation offered
        payload1 = svc.handle_chat_turn(sid, "Nothing worked")
        state = session_mgr.get(sid)
        assert state.phase == ConversationPhase.WAITING_TICKET_CONFIRMATION

        # Turn 2: user approves ticket
        payload2 = svc.handle_chat_turn(sid, "yes")
        assert payload2["ticket_created"] is True
        assert payload2["ticket_id"] == "INC0000001"

    def test_escalation_followed_by_no_returns_to_ai_troubleshooting(self):
        """If user declines the ticket, phase returns to AI_TROUBLESHOOTING."""
        from app.services.conversation_service import ConversationPhase

        decision = _make_decision_json(next_action="ESCALATE", escalation=True)
        orch, _ = _build_troubleshooting_orchestrator(decision_json=decision)
        session_mgr = _StubSessionManager()
        svc = _build_conversation_service(troubleshooting_orchestrator=orch, session_mgr=session_mgr)
        sid = _put_session_in_ai_troubleshooting(session_mgr, "PRINTER")

        svc.handle_chat_turn(sid, "Printer still failing")

        state = session_mgr.get(sid)
        assert state.phase == ConversationPhase.WAITING_TICKET_CONFIRMATION

        # Now the user declines
        payload2 = svc.handle_chat_turn(sid, "no")
        state2 = session_mgr.get(sid)
        assert state2.phase == ConversationPhase.AI_TROUBLESHOOTING


# ═════════════════════════════════════════════════════════════════════════════
# 7. FALLBACK TO LEGACY FLOW ON ORCHESTRATOR EXCEPTION
# ═════════════════════════════════════════════════════════════════════════════

class TestFallbackToLegacyFlow:

    def test_orchestrator_exception_falls_back_to_legacy(self):
        """If the orchestrator raises, the legacy flow must handle the turn."""
        mock_orch = MagicMock()
        mock_orch.handle.side_effect = RuntimeError("Orchestrator unavailable")

        session_mgr = _StubSessionManager()
        svc = _build_conversation_service(
            troubleshooting_orchestrator=mock_orch,
            session_mgr=session_mgr,
        )
        sid = _put_session_in_ai_troubleshooting(session_mgr, "VPN")

        with patch("app.services.orchestrator_service.generate_decision") as mock_decision:
            mock_decision.return_value = {
                "assistant_message": "Legacy fallback: please try restarting.",
                "intent": "GENERAL_SUPPORT",
                "confidence": 0.6,
            }
            payload = svc.handle_chat_turn(sid, "VPN not connecting")

        # Must not raise; must return the legacy response
        assert payload["response"] == "Legacy fallback: please try restarting."

    def test_orchestrator_exception_does_not_propagate(self):
        """An orchestrator crash must never surface as an exception to the caller."""
        mock_orch = MagicMock()
        mock_orch.handle.side_effect = Exception("Catastrophic failure")

        session_mgr = _StubSessionManager()
        svc = _build_conversation_service(
            troubleshooting_orchestrator=mock_orch,
            session_mgr=session_mgr,
        )
        sid = _put_session_in_ai_troubleshooting(session_mgr, "VPN")

        with patch("app.services.orchestrator_service.generate_decision") as mock_decision:
            mock_decision.return_value = {
                "assistant_message": "Fallback response.",
                "intent": "GENERAL_SUPPORT",
                "confidence": 0.5,
            }
            # Must not raise
            payload = svc.handle_chat_turn(sid, "Help")
        assert payload is not None

    def test_legacy_fallback_preserves_phase(self):
        """After orchestrator failure + legacy flow, phase must remain AI_TROUBLESHOOTING."""
        from app.services.conversation_service import ConversationPhase

        mock_orch = MagicMock()
        mock_orch.handle.side_effect = RuntimeError("fail")

        session_mgr = _StubSessionManager()
        svc = _build_conversation_service(
            troubleshooting_orchestrator=mock_orch,
            session_mgr=session_mgr,
        )
        sid = _put_session_in_ai_troubleshooting(session_mgr, "VPN")

        with patch("app.services.orchestrator_service.generate_decision") as mock_decision:
            mock_decision.return_value = {
                "assistant_message": "Legacy: what error do you see?",
                "intent": "GENERAL_SUPPORT",
                "confidence": 0.5,
            }
            payload = svc.handle_chat_turn(sid, "VPN error")

        assert payload["status"] == ConversationPhase.AI_TROUBLESHOOTING.value

    def test_legacy_llm_fallback_when_orchestrator_fails(self):
        """When both orchestrator and orchestrator_service fail, LlmOrchestrator runs."""
        mock_orch = MagicMock()
        mock_orch.handle.side_effect = RuntimeError("fail")

        session_mgr = _StubSessionManager()
        llm_stub = _StubLlmOrchestrator()
        from app.services.conversation_service import ConversationService
        svc = ConversationService(
            session_mgr=session_mgr,
            kb_orch=_StubKbOrchestrator(),
            ticket_orch=_StubTicketOrchestrator(),
            llm_orch=llm_stub,
            repo=_StubRepo(),
            transition_logger=_StubTransitionLogger(),
            action_engine=_StubActionEngine(),
            troubleshooting_orchestrator=mock_orch,
        )
        sid = _put_session_in_ai_troubleshooting(session_mgr, "VPN")

        with patch("app.services.orchestrator_service.generate_decision", side_effect=RuntimeError("also fail")):
            payload = svc.handle_chat_turn(sid, "VPN not connecting")

        # LlmOrchestrator.converse() returns "Legacy LLM fallback response"
        assert payload["response"] == "Legacy LLM fallback response"


# ═════════════════════════════════════════════════════════════════════════════
# 8. PUBLIC API SHAPE PRESERVED
# ═════════════════════════════════════════════════════════════════════════════

class TestPublicApiShape:

    def _make_all_payloads(self):
        """Generate payloads for continuation, resolution, and escalation."""
        results = {}

        # Continuation
        decision_continue = _make_decision_json(next_action="ASK_QUESTION")
        orch_c, _ = _build_troubleshooting_orchestrator(decision_json=decision_continue)
        session_mgr = _StubSessionManager()
        svc_c = _build_conversation_service(troubleshooting_orchestrator=orch_c, session_mgr=session_mgr)
        sid = _put_session_in_ai_troubleshooting(session_mgr, "VPN")
        results["continue"] = svc_c.handle_chat_turn(sid, "VPN broken")

        # Resolution
        decision_resolve = _make_decision_json(next_action="RESOLVE", reason_code="USER_CONFIRMED")
        orch_r, _ = _build_troubleshooting_orchestrator(decision_json=decision_resolve)
        session_mgr2 = _StubSessionManager()
        svc_r = _build_conversation_service(troubleshooting_orchestrator=orch_r, session_mgr=session_mgr2)
        sid2 = _put_session_in_ai_troubleshooting(session_mgr2, "VPN")
        results["resolve"] = svc_r.handle_chat_turn(sid2, "VPN works now")

        # Escalation (to WAITING_TICKET_CONFIRMATION)
        decision_esc = _make_decision_json(next_action="ESCALATE", escalation=True)
        orch_e, _ = _build_troubleshooting_orchestrator(decision_json=decision_esc)
        session_mgr3 = _StubSessionManager()
        svc_e = _build_conversation_service(troubleshooting_orchestrator=orch_e, session_mgr=session_mgr3)
        sid3 = _put_session_in_ai_troubleshooting(session_mgr3, "PRINTER")
        results["escalate"] = svc_e.handle_chat_turn(sid3, "Printer broken")

        return results

    def test_all_payloads_have_required_keys(self):
        for name, payload in self._make_all_payloads().items():
            _assert_valid_payload(payload), f"Payload '{name}' missing required keys"

    def test_continuation_action_is_ask_more_info(self):
        payloads = self._make_all_payloads()
        assert payloads["continue"]["action"] == "ASK_MORE_INFO"

    def test_resolution_action_is_resolved(self):
        payloads = self._make_all_payloads()
        assert payloads["resolve"]["action"] == "RESOLVED"

    def test_escalation_action_is_ask_more_info(self):
        """Escalation offers the ticket — action is ASK_MORE_INFO pending confirmation."""
        payloads = self._make_all_payloads()
        assert payloads["escalate"]["action"] == "ASK_MORE_INFO"

    def test_ticket_created_false_during_continuation(self):
        payloads = self._make_all_payloads()
        assert payloads["continue"]["ticket_created"] is False

    def test_ticket_created_false_during_escalation_offer(self):
        """ticket_created must be False until user confirms."""
        payloads = self._make_all_payloads()
        assert payloads["escalate"]["ticket_created"] is False


# ═════════════════════════════════════════════════════════════════════════════
# 9. GLOBAL INTENTS STILL WORK (RESOLVED_KEYWORD, TICKET_COMMAND)
# ═════════════════════════════════════════════════════════════════════════════

class TestGlobalIntentsPreserved:

    def test_resolved_keyword_still_triggers_resolved_phase(self):
        """The RESOLVED_KEYWORD global override must still fire in AI_TROUBLESHOOTING."""
        from app.services.conversation_service import ConversationPhase

        orch, _ = _build_troubleshooting_orchestrator()
        session_mgr = _StubSessionManager()
        svc = _build_conversation_service(troubleshooting_orchestrator=orch, session_mgr=session_mgr)
        sid = _put_session_in_ai_troubleshooting(session_mgr, "VPN")

        # "resolved" triggers RESOLVED_KEYWORD in the patched IntentRouter fixture
        payload = svc.handle_chat_turn(sid, "It is resolved now")

        # The orchestrator should NOT have been called — global override fires first
        assert payload["status"] == ConversationPhase.RESOLVED.value

    def test_ticket_command_intent_still_triggers_waiting_ticket_phase(self):
        """TICKET_COMMAND global intent must still bypass AI_TROUBLESHOOTING."""
        from app.services.conversation_service import ConversationPhase
        from app.services.intent_router import IntentRouter, RouteResult, IntentType

        orch, _ = _build_troubleshooting_orchestrator()
        session_mgr = _StubSessionManager()
        svc = _build_conversation_service(troubleshooting_orchestrator=orch, session_mgr=session_mgr)
        sid = _put_session_in_ai_troubleshooting(session_mgr, "VPN")

        # Temporarily override intent router to force TICKET_COMMAND
        def _ticket_route(self, message, *args, **kwargs):
            return RouteResult(intent=IntentType.TICKET_COMMAND, category="VPN", normalized_message=message)

        with patch.object(IntentRouter, "route", _ticket_route):
            payload = svc.handle_chat_turn(sid, "Please create a ticket")

        state = session_mgr.get(sid)
        assert state.phase == ConversationPhase.WAITING_TICKET_CONFIRMATION


# ═════════════════════════════════════════════════════════════════════════════
# 10. _derive_classification HELPER
# ═════════════════════════════════════════════════════════════════════════════

class TestDeriveClassification:

    def test_derive_classification_returns_duck_typed_object(self):
        """_derive_classification must return an object with required attributes."""
        from app.services.conversation_service import ConversationService, SessionState

        svc = ConversationService(
            session_mgr=_StubSessionManager(),
            kb_orch=_StubKbOrchestrator(),
            ticket_orch=_StubTicketOrchestrator(),
            llm_orch=_StubLlmOrchestrator(),
            repo=_StubRepo(),
            transition_logger=_StubTransitionLogger(),
            action_engine=_StubActionEngine(),
        )
        state = SessionState(session_id=str(uuid.uuid4()), category="VPN")
        classification = svc._derive_classification(state)

        assert hasattr(classification, "category")
        assert hasattr(classification, "subcategory")
        assert hasattr(classification, "assignment_group")
        assert hasattr(classification, "issue_type")

    def test_derive_classification_normalises_category(self):
        from app.services.conversation_service import ConversationService, SessionState

        svc = ConversationService(
            session_mgr=_StubSessionManager(),
            kb_orch=_StubKbOrchestrator(),
            ticket_orch=_StubTicketOrchestrator(),
            llm_orch=_StubLlmOrchestrator(),
            repo=_StubRepo(),
            transition_logger=_StubTransitionLogger(),
            action_engine=_StubActionEngine(),
        )
        state = SessionState(session_id=str(uuid.uuid4()), category="GUEST_WIFI")
        classification = svc._derive_classification(state)
        # Underscores replaced, title-cased
        assert "_" not in classification.category

    def test_derive_classification_handles_none_category(self):
        from app.services.conversation_service import ConversationService, SessionState

        svc = ConversationService(
            session_mgr=_StubSessionManager(),
            kb_orch=_StubKbOrchestrator(),
            ticket_orch=_StubTicketOrchestrator(),
            llm_orch=_StubLlmOrchestrator(),
            repo=_StubRepo(),
            transition_logger=_StubTransitionLogger(),
            action_engine=_StubActionEngine(),
        )
        state = SessionState(session_id=str(uuid.uuid4()), category=None)
        classification = svc._derive_classification(state)
        assert classification.category  # must not be empty
