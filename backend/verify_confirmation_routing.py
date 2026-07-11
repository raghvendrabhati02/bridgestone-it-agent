import os
import sys
import uuid
import logging

# Inject mock before importing backend app
import mock_gemini

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "app")))

from app.database.connection import SessionLocal
from app.database.models.session import SessionModel
from app.database.models.conversation import Conversation
from app.database.models.approval_history import ApprovalHistory
from app.database.models.ticket import Ticket
from app.services.conversation_service import handle_chat_turn, conversations

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("verify_confirmation_routing")

def verify_all_scenarios():
    print("=" * 60)
    print("Running verify_confirmation_routing.py (6 Scenario Cases)")
    print("=" * 60)

    db = SessionLocal()
    db.query(Ticket).filter(Ticket.category == "VPN").delete()
    db.commit()
    failures = []

    def check(case_num, description, condition, got_val):
        if condition:
            print(f"  [PASS] Case {case_num}: {description}")
        else:
            print(f"  [FAIL] Case {case_num}: {description} (Got: {got_val})")
            failures.append(f"Case {case_num}: {description}")

    def clean_session(sess_id):
        db.query(Conversation).filter(Conversation.session_id == sess_id).delete()
        db.query(SessionModel).filter(SessionModel.session_id == sess_id).delete()
        db.query(ApprovalHistory).filter(ApprovalHistory.session_id == sess_id).delete()
        db.commit()
        conversations.pop(sess_id, None)

    try:
        # Case 1: New Chat ➔ user says "yes"
        # Expected: No ACCESS_DENIED. AI should ask how it can help.
        print("\n--- Case 1: New Chat ---")
        sess1 = "sess-conf-case-01"
        clean_session(sess1)
        res1 = handle_chat_turn(
            session_id=sess1,
            message="yes",
            user_role="EMPLOYEE",
            username="emp01"
        )
        check(
            1,
            "Generic yes in new chat does not trigger ACCESS_DENIED",
            res1.get("action") != "ACCESS_DENIED",
            res1.get("action")
        )
        check(
            1,
            "Response prompts user for issue context",
            "access is disabled" not in res1.get("response", "").lower(),
            res1.get("response")
        )

        # Case 2: VPN Diagnostic ➔ User says "VPN not working", then says "yes"
        # Expected: Continue VPN diagnosis.
        print("\n--- Case 2: VPN Diagnostic ---")
        sess2 = "sess-conf-case-02"
        clean_session(sess2)
        # Turn 1: user reports vpn issue
        res2_1 = handle_chat_turn(
            session_id=sess2,
            message="My VPN is not working",
            user_role="EMPLOYEE",
            username="emp02"
        )
        # Turn 2: user says "yes" (answering diagnostic question)
        res2_2 = handle_chat_turn(
            session_id=res2_1["session_id"],
            message="yes",
            user_role="EMPLOYEE",
            username="emp02"
        )
        check(
            2,
            "VPN diagnosis yes does not trigger approval node ACCESS_DENIED",
            res2_2.get("action") != "ACCESS_DENIED",
            res2_2.get("action")
        )

        # Case 3: Outlook Diagnostic ➔ User says "Outlook blocked", then says "yes"
        # Expected: Continue Outlook workflow.
        print("\n--- Case 3: Outlook Diagnostic ---")
        sess3 = "sess-conf-case-03"
        clean_session(sess3)
        # Turn 1: user reports outlook issue
        res3_1 = handle_chat_turn(
            session_id=sess3,
            message="My Outlook email client is blocked",
            user_role="EMPLOYEE",
            username="emp03"
        )
        # Turn 2: user says "yes"
        res3_2 = handle_chat_turn(
            session_id=res3_1["session_id"],
            message="yes",
            user_role="EMPLOYEE",
            username="emp03"
        )
        check(
            3,
            "Outlook diagnosis yes does not trigger approval node ACCESS_DENIED",
            res3_2.get("action") != "ACCESS_DENIED",
            res3_2.get("action")
        )

        # Case 4: Manager Approval ➔ Pending approval ➔ Manager says "yes"
        # Expected: Approval executes successfully.
        print("\n--- Case 4: Manager Approval ---")
        sess4 = "sess-conf-case-04"
        clean_session(sess4)
        # Turn 1: report VPN disabled under MANAGER user to initiate approval PENDING
        res4_1 = handle_chat_turn(
            session_id=sess4,
            message="My VPN access is disabled on Pune gateway",
            user_role="MANAGER",
            username="mgr01"
        )
        # Turn 2: manager approves
        res4_2 = handle_chat_turn(
            session_id=res4_1["session_id"],
            message="yes",
            user_role="MANAGER",
            username="mgr01"
        )
        check(
            4,
            "Manager yes executes approved action",
            res4_2.get("action") == "EXECUTE_ACTION",
            res4_2.get("action")
        )

        # Case 5: Employee attempts approval ➔ Pending approval ➔ Employee says "yes"
        # Expected: RBAC denies approval.
        print("\n--- Case 5: Employee attempts approval ---")
        sess5 = "sess-conf-case-05"
        clean_session(sess5)
        # Turn 1: initiate pending approval
        res5_1 = handle_chat_turn(
            session_id=sess5,
            message="My VPN access is disabled on Pune gateway",
            user_role="MANAGER",
            username="mgr01"
        )
        # Turn 2: employee tries to approve
        res5_2 = handle_chat_turn(
            session_id=res5_1["session_id"],
            message="yes",
            user_role="EMPLOYEE",
            username="emp05"
        )
        check(
            5,
            "Employee yes triggers ACCESS_DENIED for approval",
            res5_2.get("action") == "ACCESS_DENIED",
            res5_2.get("action")
        )

        # Case 6: Offer Ticket state ➔ AI cannot solve ➔ Would you like me to create a ticket? ➔ User says "yes"
        # Expected: Incident created.
        print("\n--- Case 6: Offer Ticket state ---")
        sess6 = "sess-conf-case-06"
        clean_session(sess6)
        
        # Manually seed a conversation history turn where agent asks "Would you like me to create a ticket?"
        # Then user replies "yes" to handle_chat_turn
        # This simulates the precise scenario context.
        # We save a previous mock turn directly in DB conversation repo
        from app.database.repositories.conversation_repository import ConversationRepository
        repo = ConversationRepository(db)
        # We start and save the session first
        db_sess = SessionModel(
            session_id=sess6,
            category="VPN",
            status="WAITING_TICKET_CONFIRMATION"
        )
        db.add(db_sess)
        db.commit()
        
        repo.save_turn(
            session_id=sess6,
            user_message="Nothing worked, still offline.",
            agent_response="I've tried standard routing resets. Would you like me to create a ticket for support?",
            category="VPN"
        )
        
        # Trigger next turn with user replying "yes"
        res6 = handle_chat_turn(
            session_id=sess6,
            message="yes",
            user_role="EMPLOYEE",
            username="emp06"
        )
        
        check(
            6,
            "User yes in ticket offer creates ticket",
            res6.get("action") in ("TICKET_CREATED", "CREATE_TICKET"),
            res6.get("action")
        )
        
        clean_session(sess1)
        clean_session(sess2)
        clean_session(sess3)
        clean_session(sess4)
        clean_session(sess5)
        clean_session(sess6)

    finally:
        db.close()

    if failures:
        print(f"\n[FAIL] verify_confirmation_routing.py failed with checks: {failures}")
        sys.exit(1)
    else:
        print("\n[PASS] verify_confirmation_routing.py successfully verified all 6 scenarios!")
        sys.exit(0)

if __name__ == "__main__":
    verify_all_scenarios()
