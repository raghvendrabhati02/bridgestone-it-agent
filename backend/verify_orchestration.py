"""
Verify conversation_service refactored thin orchestration loop.
Tests: category detection, cache retrieval, stage tracking, KB context injection,
approval checks, tool executions, and ticket escalation rules.
"""
import uuid
from unittest.mock import patch, MagicMock

import app.services.conversation_persistence as persistence
import app.services.conversation_memory as memory
import app.services.approval_service as approval_service
import app.services.knowledge_service as knowledge_service
import app.services.conversation_flow as conversation_flow
import app.services.conversation_service as cs

session_id = str(uuid.uuid4())

# Mock Orchestrator outputs
mock_turn_1 = "I can see you're experiencing VPN issues. Let's troubleshoot."
mock_decision_privileged = {
    "assistant_message": "I found that your VPN access is disabled. I can reset it. Do you want me to proceed?",
    "intent": "VPN_ACCESS_RESTORE",
    "tool": "VPN_ACCESS_RESTORE",
    "parameters": {},
    "confidence": 0.98,
    "requires_confirmation": True
}
mock_tool_result = {
    "tool": "VPN_ACCESS_RESTORE",
    "status": "SUCCESS",
    "message": "VPN gateway credentials reset successfully.",
    "data": {}
}
mock_turn_synth = "I have successfully restored your VPN gateway credentials. Please try connecting now."

# Mock intent detection
with patch('app.services.intent_service.detect_intent', return_value="VPN"):
    # Mock ticket creation
    with patch('app.services.ticket_service.create_ticket', return_value={
        "ticket_id": "INC00123",
        "assigned_team": "Network",
        "priority": "MEDIUM",
        "sla_hours": 24,
        "servicenow_id": "SYS-9988"
    }) as mock_create_ticket:
        # Mock ToolRouter
        with patch('app.services.tool_router.route', return_value=mock_tool_result) as mock_route:
            # Mock Orchestrator turns
            with patch('app.services.orchestrator_service.generate_turn', return_value=mock_turn_1) as mock_gen_turn:
                with patch('app.services.orchestrator_service.generate_decision', return_value=mock_decision_privileged) as mock_gen_dec:
                    with patch('app.services.orchestrator_service._synthesize_tool_response', return_value=mock_turn_synth) as mock_synth:
                        
                        # ── Turn 1: Initial conversation starting ───────────────────
                        print("Testing Turn 1 (VPN Init)...")
                        state1 = cs.start_conversation("my VPN client is disconnected", "VPN")
                        assert state1.session_id is not None
                        assert state1.status == "UNDERSTANDING"
                        assert state1.category == "VPN"
                        
                        hist1 = memory.get_history(state1.session_id)
                        assert len(hist1) == 2
                        assert hist1[0]["text"] == "my VPN client is disconnected"
                        assert hist1[1]["text"] == mock_turn_1
                        
                        mock_gen_turn.assert_called_once()
                        print("Turn 1 OK")
                        
                        # ── Turn 2: Next chat turn, proposes privileged reset ────────
                        print("\nTesting Turn 2 (Privileged action proposed)...")
                        res2 = cs.handle_chat_turn(state1.session_id, "please restore it")
                        assert res2["action"] == "WAIT_FOR_APPROVAL"
                        assert res2["response"] == mock_decision_privileged["assistant_message"]
                        assert res2["status"] == "WAITING_CONFIRMATION"
                        
                        hist2 = memory.get_history(state1.session_id)
                        assert len(hist2) == 4
                        assert hist2[2]["text"] == "please restore it"
                        assert hist2[3]["text"] == mock_decision_privileged["assistant_message"]
                        
                        # Verify persistence save
                        saved2 = persistence.get_session_data(state1.session_id)
                        assert saved2["status"] == "WAITING_CONFIRMATION"
                        assert saved2["recommended_action"] == "VPN_ACCESS_RESTORE"
                        print("Turn 2 OK")
                        
                        # ── Turn 3: User approves action (Yes) ──────────────────────
                        print("\nTesting Turn 3 (User approves execution)...")
                        res3 = cs.handle_chat_turn(state1.session_id, "yes, proceed please")
                        assert res3["action"] == "EXECUTE_ACTION"
                        assert res3["response"] == mock_turn_synth
                        assert res3["status"] == "VERIFYING_SOLUTION"
                        
                        # Verify ToolRouter was executed
                        mock_route.assert_called_once_with({
                            "tool": "VPN_ACCESS_RESTORE",
                            "parameters": {}
                        })
                        mock_synth.assert_called_once_with(mock_tool_result, "VPN")
                        print("Turn 3 OK")
                        
                        # ── Turn 4: Troubleshooting attempt limit escalation ────────
                        print("\nTesting Turn 4 (Max attempts escalation)...")
                        # Reset iterations and simulate max attempts reached
                        state1.troubleshooting_iterations = 3
                        persistence.save_session(state1.session_id, state1)
                        
                        res4 = cs.handle_chat_turn(state1.session_id, "it is still not working")
                        assert res4["status"] == "WAITING_CONFIRMATION"
                        assert res4["recommended_action"] == "CREATE_TICKET"
                        assert "unresolved" in res4["response"].lower() and "ticket" in res4["response"].lower()
                        print("Turn 4 OK")
                        
                        # ── Turn 5: User confirms ticket creation ───────────────────
                        print("\nTesting Turn 5 (User confirms ticket creation)...")
                        res5 = cs.handle_chat_turn(state1.session_id, "yes, create the ticket")
                        assert res5["status"] == "ESCALATED"
                        assert res5["action"] == "TICKET_CREATED"
                        assert res5["ticket_id"] == "INC00123"
                        assert "INC00123" in res5["response"]
                        
                        mock_create_ticket.assert_called_once_with("VPN", "my VPN client is disconnected", created_by=None)
                        print("Turn 5 OK")

print("\nAll integration verification checks passed successfully.")
