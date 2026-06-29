import os
import sys
import json

# Add backend directory and app directory to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "app")))

from app.database.connection import engine
from app.database.base import Base
from app.database.session import get_db
from app.database.repositories.conversation_repository import ConversationRepository
from app.database.repositories.audit_repository import AuditRepository
from app.database.repositories.action_repository import ActionRepository
from app.database.repositories.approval_repository import ApprovalRepository
from app.database.repositories.trace_repository import TraceRepository
from app.database.repositories.ticket_repository import TicketRepository

from app.services.conversation_service import (
    handle_chat_turn,
    get_conversation,
    conversations
)
from app.services.audit_service import (
    get_all_audit_logs,
    get_all_actions_history,
    get_all_approvals_history,
    get_all_agent_traces
)
from app.services.ticket_service import get_all_tickets

def test_persistence_flow():
    print("==================================================")
    print("Testing Production Persistence Layer (PostgreSQL/SQLite)...")
    print("==================================================")
    
    # 1. Initialize Tables
    print("\n[Step 1] Creating database schemas...")
    Base.metadata.create_all(bind=engine)
    print("[OK] Schema generated.")
    
    # 2. Start Conversation (Turn 1: VPN Access disabled)
    print("\n[Step 2] Sending message: 'VPN access is disabled'...")
    res = handle_chat_turn(None, "VPN access is disabled", username="manager_user", user_role="MANAGER")
    session_id = res["session_id"]
    print(f"[OK] Response received. Category: {res.get('category')}, Action: {res.get('action')}, Status: {res.get('approval_status')}")
    assert res.get("action") in ("WAIT_FOR_APPROVAL", "REQUEST_APPROVAL")
    assert res.get("approval_required") is True
    
    # Verify trace logs logged in database
    with get_db() as db:
        trace_repo = TraceRepository(db)
        traces = trace_repo.get_all()
        print(f"[OK] Total agent traces recorded in DB: {len(traces)}")
        assert len(traces) >= 4, "Expected at least 4 node traces (Intent, Knowledge, Tool, Decision)"
        agents = {t.agent_name for t in traces if t.session_id == session_id}
        print(f"Agents traced in DB: {agents}")
        assert "Intent Agent" in agents
        assert "Tool Agent" in agents
        
    # 3. Simulate Backend Restart by Clearing In-Memory Cache
    print("\n[Step 3] Simulating backend restart (clearing memory conversations cache)...")
    conversations.clear()
    assert session_id not in conversations, "Conversations cache should be empty"
    print("[OK] In-memory cache cleared.")
    
    # 4. Recover Conversation State from DB
    print("\n[Step 4] Recovering conversation from database...")
    state = get_conversation(session_id)
    assert state is not None, "Failed to restore conversation state from database"
    print(f"[OK] Conversation restored. Category: {state.category}, Status: {state.status}, History Length: {len(state.conversation_history)}")
    assert state.status == "AWAITING_APPROVAL"
    assert state.approval_required is True
    assert len(state.conversation_history) == 2, "Expected 2 history turns reconstructed"
    
    # 5. Approve Action (Turn 2: YES)
    print("\n[Step 5] Approving action restoration...")
    res2 = handle_chat_turn(session_id, "yes, proceed please", username="manager_user", user_role="MANAGER")
    print(f"[OK] Turn 2 Response. Action: {res2.get('action')}, Status: {res2.get('approval_status')}, Result Status: {(res2.get('action_result') or {}).get('status')}")
    assert res2.get("approval_status") == "APPROVED"
    assert res2.get("action_result") is not None
    assert (res2.get("action_result") or {}).get("servicenow_id") is not None
    
    # 6. Verify Final Persistent Audit Data
    print("\n[Step 6] Verifying records in database tables...")
    
    # Audit Logs
    audit_records = get_all_audit_logs()
    print(f"\n--- Audit Logs count in DB: {len(audit_records)} ---")
    for r in audit_records:
        if r["session_id"] == session_id:
            print(f"  Turn - Decision: {r['decision']}, Category: {r['category']}, ServiceNow ID: {r['servicenow_id']}")
            
    # Action History
    actions_records = get_all_actions_history()
    print(f"\n--- Action History count in DB: {len(actions_records)} ---")
    for a in actions_records:
        print(f"  Action Type: {a['action_type']}, Status: {a['status']}, SNOW Ref: {a['servicenow_id']}, Approved: {a['approved_by_user']}")
        
    # Approval History
    approval_records = get_all_approvals_history()
    print(f"\n--- Approval History count in DB: {len(approval_records)} ---")
    for ap in approval_records:
        if ap["session_id"] == session_id:
            print(f"  Recommended Action: {ap['recommended_action']}, Status: {ap['approval_status']}, Timestamp: {ap['timestamp']}")
            
    # Tickets & Notifications
    tickets_records = get_all_tickets()
    print(f"\n--- Tickets count in DB: {len(tickets_records)} ---")
    for t in tickets_records:
        print(f"  Ticket ID: {t['ticket_id']}, Assigned: {t['assigned_team']}, Priority: {t['priority']}, SLA: {t['sla_hours']} hrs")
        
    print("\n==================================================")
    print("[SUCCESS] Production Persistence Layer successfully verified!")
    print("==================================================")

if __name__ == "__main__":
    test_persistence_flow()
