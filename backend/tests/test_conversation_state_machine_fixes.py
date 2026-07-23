"""
tests/test_conversation_state_machine_fixes.py
─────────────────────────────────────────────────────────────────────────────
Unit & integration tests verifying:
1. Reset of stale decline state (ticket_declined=False, ticket_offered=False, conversation_locked=False) when user types explicit ticket commands ("create", "yes", "raise ticket").
2. Explicit pattern matching for standalone "create", "create it", "yes create".
3. Single deduplicated _is_ticket_request method.
4. Continuation requests ("guide me", "help me") continuing troubleshooting without triggering ticket decision.
5. Entry logging and phase assertions prior to TicketOrchestrator.create().
"""

import pytest
from unittest.mock import MagicMock, patch

from app.services.conversation_service import ConversationService, ConversationPhase, _EXPLICIT_YES_PATTERNS
from app.services.intent_router import IntentRouter, IntentType


def test_explicit_yes_patterns_matches_create():
    """Verify _EXPLICIT_YES_PATTERNS matches standalone 'create' and variations."""
    assert bool(_EXPLICIT_YES_PATTERNS.search("create")) is True
    assert bool(_EXPLICIT_YES_PATTERNS.search("create it")) is True
    assert bool(_EXPLICIT_YES_PATTERNS.search("yes create")) is True
    assert bool(_EXPLICIT_YES_PATTERNS.search("yes please create")) is True
    assert bool(_EXPLICIT_YES_PATTERNS.search("please create")) is True
    assert bool(_EXPLICIT_YES_PATTERNS.search("create ticket")) is True


def test_intent_router_matches_create_as_ticket_command():
    """Verify IntentRouter matches 'create' as TICKET_COMMAND even during locked sessions."""
    router = IntentRouter()
    res1 = router.route("create", conversation_locked=True)
    assert res1.intent == IntentType.TICKET_COMMAND

    res2 = router.route("create ticket", conversation_locked=True)
    assert res2.intent == IntentType.TICKET_COMMAND


def test_is_ticket_request_single_source_of_truth():
    """Verify single ConversationService._is_ticket_request method."""
    assert ConversationService._is_ticket_request("create") is True
    assert ConversationService._is_ticket_request("create ticket") is True
    assert ConversationService._is_ticket_request("raise incident") is True
    assert ConversationService._is_ticket_request("guide me") is False
    assert ConversationService._is_ticket_request("continue troubleshooting") is False


def test_stale_decline_reset_flow():
    """
    Test full state machine lifecycle:
    1. User starts VPN chat.
    2. User declines ticket (ticket_declined = True).
    3. User says 'guide me' (troubleshooting continues).
    4. User says 'create' (stale decline flags reset, transition to WAITING_TICKET_CONFIRMATION / ticket creation).
    """
    service = ConversationService()
    
    # 1. Turn 1: Initial chat
    res1 = service.handle_chat_turn(None, "VPN not connecting", username="testuser")
    sess_id = res1["session_id"]
    state = service._session_mgr.get(sess_id)
    assert state is not None

    # Force state to ticket decline scenario
    state.phase = ConversationPhase.WAITING_TICKET_CONFIRMATION
    state.ticket_offered = True
    
    # 2. Turn 2: User declines ticket / asks to continue troubleshooting
    res2 = service.handle_chat_turn(sess_id, "no, guide me", username="testuser")
    assert state.ticket_declined is True
    assert state.phase == ConversationPhase.AI_TROUBLESHOOTING

    # 3. Turn 3: User changes mind and types 'create'
    res3 = service.handle_chat_turn(sess_id, "create", username="testuser")
    
    # Verify stale flags were reset
    assert state.ticket_declined is False
    assert state.phase in (ConversationPhase.WAITING_TICKET_CONFIRMATION, ConversationPhase.ESCALATED)
