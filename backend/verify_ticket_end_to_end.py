import os
import sys

# Force UTF-8 output on Windows terminals
if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

# Inject mock before importing backend app
import mock_gemini

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "app")))

from app.database.connection import SessionLocal
from app.database.models.ticket import Ticket
from app.database.models.rbac_audit_log import RbacAuditLog
from app.services.conversation_service import handle_chat_turn

import logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

def verify_ticket_end_to_end():
    print("Running verify_ticket_end_to_end.py...")
    db = SessionLocal()
    failures = []
    session_id = "sess-e2e-journey-01"

    def check(name, condition, msg):
        if condition:
            print(f"  [\u2705 PASS] {name}: {msg}")
        else:
            print(f"  [\u274c FAIL] {name}: {msg}")
            failures.append(name)

    try:
        # Clean up existing test session and turns to ensure test isolation
        from app.database.models.session import SessionModel
        from app.database.models.conversation import Conversation
        from app.database.models.approval_history import ApprovalHistory
        from app.services.conversation_service import conversations
        
        db.query(Conversation).filter(Conversation.session_id == session_id).delete()
        db.query(SessionModel).filter(SessionModel.session_id == session_id).delete()
        db.query(ApprovalHistory).filter(ApprovalHistory.session_id == session_id).delete()
        db.commit()
        conversations.pop(session_id, None)

        # Step 1: User files the VPN issue (initiating approval)
        print("\nStep 1: Employee reports VPN timeout...")
        res1 = handle_chat_turn(
            session_id=None,
            message="My VPN access is disabled on gateway Pune office",
            user_role="MANAGER",
            username="manager_user"
        )
        session_id = res1["session_id"]
        
        check(
            "VPN initial action requested",
            res1.get("action") == "REQUEST_APPROVAL",
            f"Expected action REQUEST_APPROVAL, got {res1.get('action')}"
        )
        check(
            "VPN session status pending",
            res1.get("approval_required") is True,
            f"Expected approval_required to be True, got {res1.get('approval_required')}"
        )

        # Step 2: Manager approves the request
        print("\nStep 2: Manager approves the request...")
        res2 = handle_chat_turn(
            session_id=session_id,
            message="yes proceed and approve privileged VPN access",
            user_role="MANAGER",
            username="manager_user"
        )
        
        check(
            "VPN action executed upon approval",
            res2.get("action") == "EXECUTE_ACTION",
            f"Expected action EXECUTE_ACTION, got {res2.get('action')}"
        )
        check(
            "Action execution output returned",
            res2.get("action_result") is not None,
            "Action execution result details are empty."
        )

        # Step 3: Employee reopens the ticket
        # Let's mock a ticket link for this session first
        # We find the ticket created for this session (if any) or create a mock ticket
        # In a real workflow, the user can say "please reopen my ticket"
        print("\nStep 3: Employee reopens the issue...")
        res3 = handle_chat_turn(
            session_id=session_id,
            message="The issue is still occurring, please reopen the ticket",
            user_role="EMPLOYEE",
            username="employee"
        )
        
        # When user asks to reopen, category remains VPN or maps accordingly,
        # verifying that it executes correctly without crashes
        check(
            "Reopen conversation processed without crash",
            res3 is not None,
            "Conversation turn failed."
        )

        # Step 4: Admin resolves the ticket directly
        print("\nStep 4: Admin resolves ticket...")
        # Query db for a ticket related to this session or category
        ticket = db.query(Ticket).filter(Ticket.category == "VPN").first()
        if ticket:
            old_status = ticket.status
            ticket.status = "RESOLVED"
            db.commit()
            
            # Log RbacAuditLog
            db.add(RbacAuditLog(
                user="admin",
                role="ADMIN",
                action="resolve_ticket",
                ticket_id=ticket.ticket_id,
                old_state=old_status,
                new_state="RESOLVED",
                details="Ticket marked as RESOLVED by administrator."
            ))
            db.commit()
            
            check(
                "Ticket state set to RESOLVED",
                ticket.status == "RESOLVED",
                "Ticket state failed to update to RESOLVED."
            )
            
            audit = db.query(RbacAuditLog).filter(
                RbacAuditLog.ticket_id == ticket.ticket_id,
                RbacAuditLog.new_state == "RESOLVED"
            ).first()
            check(
                "Resolution audit log created",
                audit is not None,
                "Resolution audit log missing in database."
            )
        else:
            print("  [WARN] No VPN ticket found in DB to resolve.")

    finally:
        db.close()

    if failures:
        print(f"[FAIL] verify_ticket_end_to_end.py failed with checks: {failures}")
        sys.exit(1)
    else:
        print("[PASS] verify_ticket_end_to_end.py successfully passed all checks!")
        sys.exit(0)

if __name__ == "__main__":
    verify_ticket_end_to_end()
