"""
tests/test_conversation_state_machine.py
─────────────────────────────────────────────────────────────────────────────
Pytest workflow tests for the deterministic state machine.

All external dependencies (DB, Gemini, KB, tickets) are replaced with
lightweight stubs injected via ConversationService.__init__.
No real network calls, no real DB writes.

Scenarios covered:
  1.  VPN troubleshooting — full happy path (UNDERSTANDING → RESOLVED)
  2.  Outlook troubleshooting — multi-step, different category
  3.  Password reset — KB miss → Gemini conversation stays in UNDERSTANDING
  4.  Category switching — mid-TROUBLESHOOTING switch resets workflow
  5.  KB missing — falls through to Gemini
  6.  Ticket creation — VERIFYING → no → WAITING → yes → ESCALATED
  7.  Ticket declined — WAITING → no → UNDERSTANDING
  8.  Restart from DB — cold cache, session reconstructed from DB stub
  9.  Restart from Redis — session in cache, DB never called
  10. Yes in UNDERSTANDING — stays UNDERSTANDING (no approval engine)
  11. Thanks during TROUBLESHOOTING — stays TROUBLESHOOTING (UNKNOWN approval)
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock, patch

import pytest

@pytest.fixture(autouse=True)
def mock_intent_router():
    from app.services.intent_router import IntentRouter, RouteResult, IntentType
    
    def fake_route(self, message: str) -> RouteResult:
        msg_lower = message.lower()
        category = "GENERAL"
        if "vpn" in msg_lower:
            category = "VPN"
        elif "outlook" in msg_lower:
            category = "OUTLOOK"
        elif "printer" in msg_lower:
            category = "PRINTER"
        elif "network" in msg_lower:
            category = "NETWORK"
            
        intent = IntentType.IT_ISSUE
        if "ticket" in msg_lower or "incident" in msg_lower:
            intent = IntentType.TICKET_COMMAND
        elif "fixed" in msg_lower or "resolved" in msg_lower:
            intent = IntentType.RESOLVED_KEYWORD
            
        return RouteResult(intent=intent, category=category, normalized_message=message)
        
    with patch.object(IntentRouter, "route", fake_route):
        yield

# ─────────────────────────────────────────────────────────────────────────────
# Minimal stub implementations injected into ConversationService
# ─────────────────────────────────────────────────────────────────────────────

# ------- TroubleshootingSession stub -----------------------------------------

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

# ------- SessionManager stub -------------------------------------------------

class _StubSessionManager:
    """In-memory session store — no DB, no cache layer."""

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
        """Pre-populate the store for restart-from-X tests."""
        self._store[state.session_id] = state


# ------- KnowledgeOrchestrator stubs -----------------------------------------

class _KbFoundOrchestrator:
    """Always finds an article and starts troubleshooting with 2 steps."""

    def __init__(self, steps=None):
        self._steps = steps or [_STEP1, _STEP2]
        self._step_idx = 0

    def start_troubleshooting(self, state, message):
        # Set troubleshooting_session but NOT phase — ConversationService._transition() does that.
        ts = _FakeTS()
        state.troubleshooting_session = ts
        return f"**Step 1: {self._steps[0]['title']}**\n{self._steps[0]['instruction']}\nHave you completed this step?"


class _KbMissOrchestrator:
    """Never finds an article."""

    def start_troubleshooting(self, state, message):
        return None


# ------- TicketOrchestrator stubs --------------------------------------------

class _StubTicketOrchestrator:
    def create(self, state, username=None):
        return {
            "ticket_id": "INC000099",
            "assigned_team": "Network Team",
            "priority": "HIGH",
            "sla_hours": 4,
            "servicenow_id": "SN0099",
        }


# ------- LlmOrchestrator stub ------------------------------------------------

class _StubLlm:
    def converse(self, state, message):
        return f"[Gemini] I can help with your {state.category} issue."

    def converse_with_step(self, state, message, step_details):
        return f"[Gemini Explanation] The step is: {step_details.get('title')}."


# ------- ConversationRepository stub ----------------------------------------

class _StubRepo:
    def persist(self, state, user_message, bot_text):
        import app.services.conversation_memory as memory
        memory.append_turn_pair(state.session_id, user_message, bot_text, state.category)

    def serialize_ts(self, state):
        pass

    def restore_ts(self, state):
        pass


# ------- StateTransitionLogger stub ------------------------------------------

class _StubTransitionLogger:
    def __init__(self):
        self.records = []

    def log_transition(self, session_id, prev, next_, reason):
        self.records.append({"session_id": session_id, "prev": str(prev), "next": str(next_), "reason": reason})

    def clear(self):
        self.records.clear()


# ------- approval_service stubs ----------------------------------------------

class _ApprovalStub:
    class ApprovalStatus:
        APPROVED = "APPROVED"
        REJECTED = "REJECTED"
        UNKNOWN  = "UNKNOWN"

    @dataclass
    class ApprovalResult:
        status: str
        confidence: float = 1.0
        matched_phrase: str = ""
        reason: str = ""


def _approval_approved():
    s = _ApprovalStub()
    r = s.ApprovalResult(status="APPROVED", matched_phrase="yes")
    return r

def _approval_rejected():
    s = _ApprovalStub()
    r = s.ApprovalResult(status="REJECTED", matched_phrase="no")
    return r

def _approval_unknown():
    s = _ApprovalStub()
    r = s.ApprovalResult(status="UNKNOWN", matched_phrase="thanks")
    return r


# ------- troubleshooting_service stubs ----------------------------------------

class _TsService:
    """Stateless stub — all state lives on the _FakeTS dataclass."""

    def current_step(self, ts):
        idx = ts.current_step - 1
        steps = [_STEP1, _STEP2]
        return steps[idx] if 0 <= idx < len(steps) else None

    def next_step(self, ts):
        steps = [_STEP1, _STEP2]
        if ts.current_step >= len(steps):
            ts.finished = True
            return None
        ts.current_step += 1
        return steps[ts.current_step - 1]

    def mark_completed(self, ts):
        if ts.current_step not in ts.completed_steps:
            ts.completed_steps.append(ts.current_step)

    def is_finished(self, ts):
        return ts.finished

    def get_verification(self, ts):
        return _VERIFICATION


# ─────────────────────────────────────────────────────────────────────────────
# Factory — build a ConversationService with all stubs injected
# ─────────────────────────────────────────────────────────────────────────────

class _StubActionEngine:
    def __init__(self):
        from app.services.action_engine import ActionEngine
        self._real = ActionEngine()

    def get_next_action(self, category: str, attempted: list[str]):
        return self._real.get_next_action(category, attempted)

    def execute(self, action):
        return {"tool": action.tool, "status": "SUCCESS", "data": {}, "message": f"Executed {action.name} successfully."}


class _NoActionEngine:
    def get_next_action(self, category: str, attempted: list[str]):
        return None

    def execute(self, action):
        return {"tool": action.tool, "status": "ERROR", "data": {}, "message": "Failed."}


# ─────────────────────────────────────────────────────────────────────────────
# Factory — build a ConversationService with all stubs injected
# ─────────────────────────────────────────────────────────────────────────────

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


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _phase(sm, sid):
    return sm.get(sid).phase


def _patch_approval(monkeypatch, result_fn):
    """Patch approval_service.detect_approval used inside ConversationService."""
    import app.services.approval_service as asr
    monkeypatch.setattr(asr, "detect_approval", lambda msg: result_fn())
    monkeypatch.setattr(asr, "ApprovalStatus", _ApprovalStub.ApprovalStatus)


def _patch_ts(monkeypatch):
    """Patch troubleshooting_service module-level calls inside ConversationService."""
    import app.services.troubleshooting_service as ts_mod
    stub = _TsService()
    monkeypatch.setattr(ts_mod, "current_step", stub.current_step)
    monkeypatch.setattr(ts_mod, "next_step", stub.next_step)
    monkeypatch.setattr(ts_mod, "mark_completed", stub.mark_completed)
    monkeypatch.setattr(ts_mod, "is_finished", stub.is_finished)
    monkeypatch.setattr(ts_mod, "get_verification", stub.get_verification)


# ─────────────────────────────────────────────────────────────────────────────
# Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestVpnTroubleshootingFullFlow:
    """Scenario 1 — VPN troubleshooting full happy path."""

    def test_full_flow(self, monkeypatch):
        from app.services.conversation_service import ConversationPhase
        _patch_ts(monkeypatch)

        svc, sm, tl = _make_svc()
        # Patch _detect_category once for the whole test — prevents real Gemini intent calls
        monkeypatch.setattr(svc, "_detect_category", lambda msg: "VPN")

        # Turn 1: new session, KB article found → TROUBLESHOOTING
        r1 = svc.handle_chat_turn(None, "vpn not working")
        sid = r1["session_id"]
        assert _phase(sm, sid) == ConversationPhase.TROUBLESHOOTING
        assert "Step 1" in r1["response"]

        # Turn 2: user says yes → advance to step 2
        with patch("app.services.approval_service.detect_approval", return_value=_approval_approved()), \
             patch("app.services.approval_service.ApprovalStatus", _ApprovalStub.ApprovalStatus):
            r2 = svc.handle_chat_turn(sid, "yes done")
        assert _phase(sm, sid) == ConversationPhase.TROUBLESHOOTING
        assert "Step 2" in r2["response"]

        # Turn 3: step 2 didn't work → VERIFYING
        with patch("app.services.approval_service.detect_approval", return_value=_approval_rejected()), \
             patch("app.services.approval_service.ApprovalStatus", _ApprovalStub.ApprovalStatus):
            r3 = svc.handle_chat_turn(sid, "no still broken")
        assert _phase(sm, sid) == ConversationPhase.VERIFYING
        assert any(w in r3["response"].lower() for w in ["vpn", "connected", "resolve", "issue"])

        # Turn 4: issue resolved → RESOLVED
        with patch("app.services.approval_service.detect_approval", return_value=_approval_approved()), \
             patch("app.services.approval_service.ApprovalStatus", _ApprovalStub.ApprovalStatus):
            r4 = svc.handle_chat_turn(sid, "yes it works now")
        assert _phase(sm, sid) == ConversationPhase.RESOLVED
        assert r4["action"] == "RESOLVED"

        # Transition log must include TROUBLESHOOTING and RESOLVED transitions
        all_nexts = [t["next"] for t in tl.records if t["session_id"] == sid]
        assert any("TROUBLESHOOTING" in n for n in all_nexts)
        assert any("RESOLVED" in n for n in all_nexts)


class TestOutlookTroubleshooting:
    """Scenario 2 — Outlook troubleshooting (different category, same flow)."""

    def test_outlook_reaches_verifying(self, monkeypatch):
        from app.services.conversation_service import ConversationPhase
        _patch_ts(monkeypatch)
        svc, sm, tl = _make_svc()

        with patch.object(svc, "_detect_category", return_value="OUTLOOK"):
            r1 = svc.handle_chat_turn(None, "outlook not opening")
        sid = r1["session_id"]
        assert sm.get(sid).category == "OUTLOOK"
        assert _phase(sm, sid) == ConversationPhase.TROUBLESHOOTING

        # Both steps → not resolved
        for msg in ("yes done", "no still not working"):
            approval_fn = _approval_approved if msg == "yes done" else _approval_rejected
            with patch("app.services.approval_service.detect_approval", return_value=approval_fn()), \
                 patch("app.services.approval_service.ApprovalStatus", _ApprovalStub.ApprovalStatus):
                svc.handle_chat_turn(sid, msg)

        assert _phase(sm, sid) == ConversationPhase.VERIFYING


class TestPasswordResetNoKb:
    """Scenario 3 — Password reset, no KB article → Gemini conversation."""

    def test_stays_understanding(self, monkeypatch):
        from app.services.conversation_service import ConversationPhase
        svc, sm, _ = _make_svc(kb=_KbMissOrchestrator())

        with patch.object(svc, "_detect_category", return_value="PASSWORD_RESET"):
            r = svc.handle_chat_turn(None, "I forgot my password")
        sid = r["session_id"]
        assert _phase(sm, sid) == ConversationPhase.UNDERSTANDING
        assert "[Gemini]" in r["response"]

        # Next message also stays in UNDERSTANDING
        with patch.object(svc, "_detect_category", return_value="PASSWORD_RESET"):
            r2 = svc.handle_chat_turn(sid, "still locked out")
        assert _phase(sm, sid) == ConversationPhase.UNDERSTANDING


class TestCategorySwitching:
    """Scenario 4 — Mid-TROUBLESHOOTING category switch resets workflow."""

    def test_switch_resets_troubleshooting(self, monkeypatch):
        from app.services.conversation_service import ConversationPhase
        _patch_ts(monkeypatch)
        svc, sm, tl = _make_svc()

        # Start VPN session
        with patch.object(svc, "_detect_category", return_value="VPN"):
            r1 = svc.handle_chat_turn(None, "vpn not connecting")
        sid = r1["session_id"]
        assert _phase(sm, sid) == ConversationPhase.TROUBLESHOOTING

        # User switches to OUTLOOK mid-flow
        with patch.object(svc, "_detect_category", return_value="OUTLOOK"):
            r2 = svc.handle_chat_turn(sid, "actually outlook is not opening")
        assert sm.get(sid).category == "OUTLOOK"
        assert _phase(sm, sid) in (ConversationPhase.TROUBLESHOOTING, ConversationPhase.UNDERSTANDING)
        assert "Outlook" in r2["response"] or "outlook" in r2["response"].lower()

        # Transition log must show a category switch entry
        switch = [t for t in tl.records if "switch" in t["reason"]]
        assert switch, "Expected a category-switch transition record"


class TestKbMissing:
    """Scenario 5 — KB article not found → falls through to Gemini."""

    def test_gemini_handles_unknown_issue(self):
        from app.services.conversation_service import ConversationPhase
        svc, sm, _ = _make_svc(kb=_KbMissOrchestrator())

        with patch.object(svc, "_detect_category", return_value="GENERAL"):
            r = svc.handle_chat_turn(None, "my screen is flickering")
        sid = r["session_id"]
        assert _phase(sm, sid) == ConversationPhase.UNDERSTANDING
        assert "[Gemini]" in r["response"]


class TestTicketCreation:
    """Scenario 6 — Full path to ticket creation."""

    def test_ticket_created_after_verification_fails(self, monkeypatch):
        from app.services.conversation_service import ConversationPhase
        _patch_ts(monkeypatch)
        svc, sm, _ = _make_svc()

        with patch.object(svc, "_detect_category", return_value="VPN"):
            svc.handle_chat_turn(None, "vpn broken")

        sid = list(sm._store.keys())[0]

        # Complete both steps (rejected = not working)
        for _ in range(2):
            with patch("app.services.approval_service.detect_approval", return_value=_approval_rejected()), \
                 patch("app.services.approval_service.ApprovalStatus", _ApprovalStub.ApprovalStatus):
                svc.handle_chat_turn(sid, "no")

        assert _phase(sm, sid) == ConversationPhase.VERIFYING

        # Verification fails → WAITING_TICKET_CONFIRMATION
        with patch("app.services.approval_service.detect_approval", return_value=_approval_rejected()), \
             patch("app.services.approval_service.ApprovalStatus", _ApprovalStub.ApprovalStatus):
            r_wait = svc.handle_chat_turn(sid, "no still broken")
        assert _phase(sm, sid) == ConversationPhase.WAITING_TICKET_CONFIRMATION
        assert "ticket" in r_wait["response"].lower() or "servicenow" in r_wait["response"].lower()

        # User approves ticket → ESCALATED
        with patch("app.services.approval_service.detect_approval", return_value=_approval_approved()), \
             patch("app.services.approval_service.ApprovalStatus", _ApprovalStub.ApprovalStatus):
            r_ticket = svc.handle_chat_turn(sid, "yes please")
        assert _phase(sm, sid) == ConversationPhase.ESCALATED
        assert r_ticket["ticket_created"] is True
        assert "INC000099" in r_ticket["response"]
        assert r_ticket["ticket_id"] == "INC000099"


class TestTicketDeclined:
    """Scenario 7 — User declines ticket → back to UNDERSTANDING."""

    def test_declined_resets_to_understanding(self, monkeypatch):
        from app.services.conversation_service import ConversationPhase
        _patch_ts(monkeypatch)
        svc, sm, _ = _make_svc()

        with patch.object(svc, "_detect_category", return_value="VPN"):
            svc.handle_chat_turn(None, "vpn broken")
        sid = list(sm._store.keys())[0]

        # Drive to WAITING_TICKET_CONFIRMATION
        for _ in range(2):
            with patch("app.services.approval_service.detect_approval", return_value=_approval_rejected()), \
                 patch("app.services.approval_service.ApprovalStatus", _ApprovalStub.ApprovalStatus):
                svc.handle_chat_turn(sid, "no")

        with patch("app.services.approval_service.detect_approval", return_value=_approval_rejected()), \
             patch("app.services.approval_service.ApprovalStatus", _ApprovalStub.ApprovalStatus):
            svc.handle_chat_turn(sid, "no still broken")

        assert _phase(sm, sid) == ConversationPhase.WAITING_TICKET_CONFIRMATION

        # Decline ticket
        with patch("app.services.approval_service.detect_approval", return_value=_approval_rejected()), \
             patch("app.services.approval_service.ApprovalStatus", _ApprovalStub.ApprovalStatus):
            r = svc.handle_chat_turn(sid, "no thanks")
        assert _phase(sm, sid) == ConversationPhase.UNDERSTANDING
        assert sm.get(sid).troubleshooting_session is None


class TestRestartFromDb:
    """Scenario 8 — Cold cache, session reconstructed from DB."""

    def test_db_restore_resumes_correct_phase(self, monkeypatch):
        from app.services.conversation_service import SessionState, ConversationPhase

        existing_sid = str(uuid.uuid4())
        restored_state = SessionState(
            session_id=existing_sid,
            category="PRINTER",
            phase=ConversationPhase.TROUBLESHOOTING,
        )
        restored_state.troubleshooting_session = _FakeTS(article_id="KB_PRINTER")

        # SessionManager.get() returns None first (cold cache), then loads from "DB"
        sm = _StubSessionManager()

        class _DbFallbackSM(_StubSessionManager):
            def get(self, sid):
                # Simulate cold cache then DB restore
                if sid == existing_sid:
                    self._store[sid] = restored_state
                    return restored_state
                return super().get(sid)

        db_sm = _DbFallbackSM()
        _patch_ts(monkeypatch)
        svc, _, _ = _make_svc(session_mgr=db_sm)

        with patch("app.services.approval_service.detect_approval", return_value=_approval_approved()), \
             patch("app.services.approval_service.ApprovalStatus", _ApprovalStub.ApprovalStatus):
            r = svc.handle_chat_turn(existing_sid, "yes done")

        # Should advance (step 2) — not restart from beginning
        assert "Step 2" in r["response"]
        assert db_sm.get(existing_sid).phase == ConversationPhase.TROUBLESHOOTING


class TestRestartFromRedis:
    """Scenario 9 — Session in cache, no DB call needed."""

    def test_cache_hit_returns_correct_phase(self, monkeypatch):
        from app.services.conversation_service import SessionState, ConversationPhase

        sid = str(uuid.uuid4())
        cached_state = SessionState(
            session_id=sid,
            category="NETWORK",
            phase=ConversationPhase.VERIFYING,
        )

        sm = _StubSessionManager()
        sm.inject(cached_state)

        _patch_ts(monkeypatch)
        svc, _, _ = _make_svc(session_mgr=sm)

        with patch("app.services.approval_service.detect_approval", return_value=_approval_approved()), \
             patch("app.services.approval_service.ApprovalStatus", _ApprovalStub.ApprovalStatus):
            r = svc.handle_chat_turn(sid, "yes works now")

        assert sm.get(sid).phase == ConversationPhase.RESOLVED
        assert r["action"] == "RESOLVED"


class TestYesInUnderstanding:
    """Scenario 10 — 'yes' in UNDERSTANDING must NOT trigger approval engine."""

    def test_yes_handled_by_gemini(self, monkeypatch):
        from app.services.conversation_service import ConversationPhase
        svc, sm, _ = _make_svc(kb=_KbMissOrchestrator())

        with patch.object(svc, "_detect_category", return_value="GENERAL"):
            svc.handle_chat_turn(None, "hello")
        sid = list(sm._store.keys())[0]
        assert _phase(sm, sid) == ConversationPhase.UNDERSTANDING

        # "yes" with no KB article — must go to Gemini, NOT approval engine
        approval_called = []
        real_detect = __import__("app.services.approval_service", fromlist=["detect_approval"]).detect_approval

        def _tracking_detect(msg):
            approval_called.append(msg)
            return real_detect(msg)

        with patch("app.services.approval_service.detect_approval", side_effect=_tracking_detect):
            r = svc.handle_chat_turn(sid, "yes")

        assert _phase(sm, sid) == ConversationPhase.UNDERSTANDING
        assert approval_called == [], "detect_approval must NOT be called in UNDERSTANDING phase"
        assert "[Gemini]" in r["response"]


class TestThanksInTroubleshooting:
    """Scenario 11 — 'thanks' in TROUBLESHOOTING yields UNKNOWN → re-prompt."""

    def test_thanks_reprompts_step(self, monkeypatch):
        from app.services.conversation_service import ConversationPhase
        import app.services.intent_router as ir
        _patch_ts(monkeypatch)
        svc, sm, _ = _make_svc()

        monkeypatch.setattr(ir.IntentRouter, "_classify_category", lambda self, msg: "VPN")
        svc.handle_chat_turn(None, "vpn not connecting")
        sid = list(sm._store.keys())[0]
        assert _phase(sm, sid) == ConversationPhase.TROUBLESHOOTING

        # "thanks" → UNKNOWN → re-prompt same step
        with patch("app.services.approval_service.detect_approval", return_value=_approval_unknown()), \
             patch("app.services.approval_service.ApprovalStatus", _ApprovalStub.ApprovalStatus):
            r = svc.handle_chat_turn(sid, "thanks")

        assert _phase(sm, sid) == ConversationPhase.TROUBLESHOOTING, \
            "UNKNOWN approval must NOT advance the step"
        assert "Step 1" in r["response"] or "complete" in r["response"].lower()


class TestDiagnosticEngine:
    """Tests covering the Diagnostic Engine logic and ConversationService integration."""

    def test_low_confidence_vpn_diagnostic_flow(self, monkeypatch):
        from app.services.conversation_service import ConversationPhase
        import app.services.intent_router as ir
        _patch_ts(monkeypatch)
        svc, sm, tl = _make_svc()

        # Always classify as VPN — prevents real Gemini calls and keyword misclassification
        monkeypatch.setattr(ir.IntentRouter, "_classify_category", lambda self, msg: "VPN")

        # Turn 1: User says "vpn" (very short query → low confidence)
        r1 = svc.handle_chat_turn(None, "vpn")
        sid = r1["session_id"]

        assert _phase(sm, sid) == ConversationPhase.DIAGNOSING
        assert "office WiFi or home WiFi" in r1["response"]

        # Turn 2: User responds "home wifi" — diagnostic engine should extract network_type=home
        r2 = svc.handle_chat_turn(sid, "home wifi")

        assert _phase(sm, sid) == ConversationPhase.TROUBLESHOOTING
        assert "Step 1" in r2["response"]
        assert sm.get(sid).diagnostic_answers.get("network_type") == "home"

    def test_category_switch_mid_diagnosing(self, monkeypatch):
        from app.services.conversation_service import ConversationPhase
        import app.services.intent_router as ir
        _patch_ts(monkeypatch)
        svc, sm, tl = _make_svc()

        # Turn 1: VPN (low confidence) → DIAGNOSING
        monkeypatch.setattr(ir.IntentRouter, "_classify_category", lambda self, msg: "VPN")
        r1 = svc.handle_chat_turn(None, "vpn")
        sid = r1["session_id"]
        assert _phase(sm, sid) == ConversationPhase.DIAGNOSING

        # Turn 2: Switches to OUTLOOK
        monkeypatch.setattr(ir.IntentRouter, "_classify_category", lambda self, msg: "OUTLOOK")
        r2 = svc.handle_chat_turn(sid, "outlook")

        assert sm.get(sid).category == "OUTLOOK"
        assert _phase(sm, sid) == ConversationPhase.DIAGNOSING
        assert "Does Outlook open?" in r2["response"]


class TestActionEngine:
    """Tests covering the new IT Support behavior where automatic actions are bypassed."""

    def test_vpn_action_flow_bypassed_to_ticket(self, monkeypatch):
        from app.services.conversation_service import ConversationPhase
        import app.services.intent_router as ir
        _patch_ts(monkeypatch)
        ae = _StubActionEngine()
        svc, sm, tl = _make_svc(action_engine=ae)
        monkeypatch.setattr(ir.IntentRouter, "_classify_category", lambda self, msg: "VPN")

        # Start VPN troubleshooting (bypass diagnostics with long query)
        r = svc.handle_chat_turn(None, "my vpn is broken at home")
        sid = r["session_id"]
        assert _phase(sm, sid) == ConversationPhase.TROUBLESHOOTING

        # Complete step 1
        with patch("app.services.approval_service.detect_approval", return_value=_approval_approved()), \
             patch("app.services.approval_service.ApprovalStatus", _ApprovalStub.ApprovalStatus):
            svc.handle_chat_turn(sid, "yes")

        # Complete step 2 -> VERIFYING
        with patch("app.services.approval_service.detect_approval", return_value=_approval_rejected()), \
             patch("app.services.approval_service.ApprovalStatus", _ApprovalStub.ApprovalStatus):
            svc.handle_chat_turn(sid, "no")
        assert _phase(sm, sid) == ConversationPhase.VERIFYING

        # Verify fails -> Bypasses Action Engine -> WAITING_TICKET_CONFIRMATION
        with patch("app.services.approval_service.detect_approval", return_value=_approval_rejected()), \
             patch("app.services.approval_service.ApprovalStatus", _ApprovalStub.ApprovalStatus):
            r_action = svc.handle_chat_turn(sid, "no still broken")
        assert _phase(sm, sid) == ConversationPhase.WAITING_TICKET_CONFIRMATION
        assert "ticket" in r_action["response"].lower() or "servicenow" in r_action["response"].lower()

    def test_outlook_action_flow_bypassed_to_ticket(self, monkeypatch):
        from app.services.conversation_service import ConversationPhase
        import app.services.intent_router as ir
        _patch_ts(monkeypatch)
        ae = _StubActionEngine()
        svc, sm, tl = _make_svc(action_engine=ae)
        monkeypatch.setattr(ir.IntentRouter, "_classify_category", lambda self, msg: "OUTLOOK")

        # Start Outlook troubleshooting (bypass diagnostics)
        r = svc.handle_chat_turn(None, "outlook email sync error")
        sid = r["session_id"]
        assert _phase(sm, sid) == ConversationPhase.TROUBLESHOOTING

        # Complete both steps -> VERIFYING
        for _ in range(2):
            with patch("app.services.approval_service.detect_approval", return_value=_approval_approved()), \
                 patch("app.services.approval_service.ApprovalStatus", _ApprovalStub.ApprovalStatus):
                svc.handle_chat_turn(sid, "yes")
        assert _phase(sm, sid) == ConversationPhase.VERIFYING

        # Verify fails -> Bypasses Action Engine -> WAITING_TICKET_CONFIRMATION (even with requires_confirmation=False actions)
        with patch("app.services.approval_service.detect_approval", return_value=_approval_rejected()), \
             patch("app.services.approval_service.ApprovalStatus", _ApprovalStub.ApprovalStatus):
            r_action = svc.handle_chat_turn(sid, "no sync failing")
        assert _phase(sm, sid) == ConversationPhase.WAITING_TICKET_CONFIRMATION
        assert "ticket" in r_action["response"].lower() or "servicenow" in r_action["response"].lower()


