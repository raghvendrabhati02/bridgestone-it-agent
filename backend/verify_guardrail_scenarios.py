import os
import sys
from unittest.mock import patch, MagicMock

# Force UTF-8 output on Windows terminals
if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

# Inject mock before importing backend app
import mock_gemini

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "app")))

from app.database.connection import SessionLocal
from app.services.conversation_service import handle_chat_turn, conversations, ConversationPhase, _default_session_mgr
import app.services.orchestrator_service as orchestrator_service

import uuid

def test_guardrails():
    print("Running verify_guardrail_scenarios.py...")
    session_id = f"sess-guardrail-test-{uuid.uuid4()}"
    
    # Ensure clean state
    conversations.pop(session_id, None)

    # Scenario 1: LLM tries to escalate immediately without troubleshooting (Blocked)
    print("\nScenario 1: AI attempts premature escalation (should be blocked)")
    mock_decision = {
        "assistant_message": "I will create a ticket for your printer issue.",
        "intent": "CREATE_TICKET",
        "tool": None,
        "parameters": {},
        "confidence": 0.95,
        "requires_confirmation": False,
        "action_type": "OTHER",
        "escalation_reason": None
    }
    
    with patch("app.services.orchestrator_service.generate_decision", return_value=mock_decision):
        res = handle_chat_turn(
            session_id=session_id,
            message="My printer is not printing anything.",
            user_role="EMPLOYEE",
            username="test_user"
        )
        print(f"Result action: {res.get('action')}")
        print(f"Result status: {res.get('status')}")
        print(f"Result response: {res.get('response')}")
        
        # The phase should not be WAITING_TICKET_CONFIRMATION since it was blocked
        assert res.get("status") == "AI_TROUBLESHOOTING", f"Expected AI_TROUBLESHOOTING, got {res.get('status')}"
        # Phrasing should be stripped or fallback used
        assert "create a ticket" not in res.get("response").lower()
        print("  [✅ PASS] Premature escalation successfully blocked and response cleaned.")

    # Scenario 2: Troubleshooting step suggested, then AI escalates (Allowed)
    print("\nScenario 2: Escalation after troubleshooting (should be allowed)")
    state = conversations.get(session_id)
    # Simulate a step suggested
    state.troubleshooting_steps_suggested = 1
    
    mock_decision_allowed = {
        "assistant_message": "I've tried resolving this but since it failed, let me create a ticket for you.",
        "intent": "CREATE_TICKET",
        "tool": "CREATE_TICKET",
        "parameters": {},
        "confidence": 0.95,
        "requires_confirmation": False,
        "action_type": "OTHER",
        "escalation_reason": "EXHAUSTED"
    }
    
    with patch("app.services.orchestrator_service.generate_decision", return_value=mock_decision_allowed):
        res2 = handle_chat_turn(
            session_id=session_id,
            message="No, that step did not work.",
            user_role="EMPLOYEE",
            username="test_user"
        )
        print(f"Result status: {res2.get('status')}")
        print(f"Result response: {res2.get('response')}")
        
        assert res2.get("status") == "WAITING_TICKET_CONFIRMATION", f"Expected WAITING_TICKET_CONFIRMATION, got {res2.get('status')}"
        print("  [✅ PASS] Escalation allowed after troubleshooting.")

    # Scenario 3: Admin privilege required (Allowed immediately)
    print("\nScenario 3: Escalation due to admin privilege required (should be allowed immediately)")
    conversations.pop(session_id, None) # reset
    
    mock_decision_admin = {
        "assistant_message": "This request requires administrator privileges. I will create a ticket.",
        "intent": "CREATE_TICKET",
        "tool": "CREATE_TICKET",
        "parameters": {},
        "confidence": 0.95,
        "requires_confirmation": False,
        "action_type": "OTHER",
        "escalation_reason": "ADMIN_REQUIRED"
    }
    
    with patch("app.services.orchestrator_service.generate_decision", return_value=mock_decision_admin):
        # We need to transition the session phase to AI_TROUBLESHOOTING first
        # to run the _handle_ai_troubleshooting block (since guardrail is engine-owned in that handler)
        session_id, state = _default_session_mgr.create("GENERAL")
        state.phase = ConversationPhase.AI_TROUBLESHOOTING
        
        res3 = handle_chat_turn(
            session_id=session_id,
            message="I need admin access to install software.",
            user_role="EMPLOYEE",
            username="test_user"
        )
        print(f"Result status: {res3.get('status')}")
        print(f"Result response: {res3.get('response')}")
        
        assert res3.get("status") == "WAITING_TICKET_CONFIRMATION", f"Expected WAITING_TICKET_CONFIRMATION, got {res3.get('status')}"
        print("  [✅ PASS] Escalation allowed immediately for admin privileges.")

    print("\nAll guardrail scenario checks passed successfully!")

if __name__ == "__main__":
    test_guardrails()
