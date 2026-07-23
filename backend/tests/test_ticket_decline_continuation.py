"""
tests/test_ticket_decline_continuation.py
─────────────────────────────────────────────────────────────────────────────
Tests for ticket decline and continuation workflow:
When a user declines ticket creation, subsequent messages like "guide me",
"help me", "continue", "another solution", "what else", "keep troubleshooting"
resume troubleshooting without prompting for a ticket. Only explicit ticket
decisions (yes, create ticket, no, don't create) trigger ticket creation/decline.
"""

from __future__ import annotations
from unittest.mock import MagicMock, patch
import pytest

from app.services.conversation_service import ConversationService, ConversationPhase, SessionState
import app.services.approval_service as approval_service


def test_approval_service_does_not_treat_continue_as_approval():
    """Verify 'continue' is not treated as APPROVED by detect_approval."""
    res = approval_service.detect_approval("continue")
    assert res.status != approval_service.ApprovalStatus.APPROVED


def test_ticket_decline_continuation_phrases():
    """
    Test that after ticket decline, continuation phrases ("guide me", "help me",
    "continue", "another solution", "what else", "keep troubleshooting") do NOT
    trigger ticket prompts or ticket creation, and instead resume AI troubleshooting.
    """
    service = ConversationService()
    
    # Mock Gemini decision generation
    mock_decision = {
        "assistant_message": "Let me help you troubleshoot your VPN connection. Have you checked your wifi?",
        "intent": "GENERAL_SUPPORT",
        "confidence": 0.95,
        "action_type": "QUESTION"
    }

    continuation_phrases = [
        "guide me",
        "help me",
        "continue",
        "another solution",
        "what else",
        "keep troubleshooting",
    ]

    with patch("app.services.orchestrator_service.generate_decision", return_value=mock_decision), \
         patch("app.services.ai_provider.get_ai_provider") as mock_ai:
        mock_provider = MagicMock()
        mock_provider.generate_response.return_value = '{"intent": "GENERAL_SUPPORT", "assistant_message": "Let me help you."}'
        mock_ai.return_value = mock_provider

        for phrase in continuation_phrases:
            state = SessionState(session_id=f"test_session_{phrase.replace(' ', '_')}", category="VPN")
            state.phase = ConversationPhase.WAITING_TICKET_CONFIRMATION
            state.ticket_offered = True
            service._session_mgr.save_to_cache(state)

            # User sends continuation phrase instead of ticket decision
            res = service.handle_chat_turn(state.session_id, phrase)
            
            # Verify response is NOT asking for ticket creation
            bot_text = res.get("message", "")
            assert "ServiceNow" not in bot_text or "created" not in bot_text
            assert "Would you like me to go ahead and create a ServiceNow ticket" not in bot_text
            
            # Verify state phase transitioned to AI_TROUBLESHOOTING and ticket_declined is True
            curr_state = service._session_mgr.get(state.session_id)
            assert curr_state.phase in (ConversationPhase.AI_TROUBLESHOOTING, ConversationPhase.UNDERSTANDING)
            assert curr_state.ticket_declined is True


def test_explicit_ticket_decisions():
    """
    Test that explicit YES/NO decisions properly create or decline tickets.
    """
    mock_ticket_res = {
        "ticket_id": "INC0000123",
        "assigned_team": "Network Team",
        "request_type": "INCIDENT",
        "requires_approval": False,
        "status_label": "NEW",
    }
    
    service = ConversationService()
    
    # Test explicit YES creates ticket
    state1 = SessionState(session_id="test_explicit_yes", category="VPN")
    state1.phase = ConversationPhase.WAITING_TICKET_CONFIRMATION
    service._session_mgr.save_to_cache(state1)
    
    with patch.object(service._tickets, "create", return_value=mock_ticket_res):
        res1 = service.handle_chat_turn(state1.session_id, "yes create ticket")
        assert res1.get("ticket_created") is True
        assert res1.get("ticket_id") == "INC0000123"

    # Test explicit NO declines ticket
    state2 = SessionState(session_id="test_explicit_no", category="VPN")
    state2.phase = ConversationPhase.WAITING_TICKET_CONFIRMATION
    service._session_mgr.save_to_cache(state2)
    
    res2 = service.handle_chat_turn(state2.session_id, "no don't create")
    curr_state2 = service._session_mgr.get(state2.session_id)
    assert curr_state2.ticket_declined is True
    assert curr_state2.phase in (ConversationPhase.AI_TROUBLESHOOTING, ConversationPhase.UNDERSTANDING)
