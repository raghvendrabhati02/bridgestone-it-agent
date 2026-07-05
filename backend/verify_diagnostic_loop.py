import os
import sys
import uuid
import logging

# Ensure mock is active for API calls
import mock_gemini

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "app")))

from app.database.connection import SessionLocal
from app.database.models.session import SessionModel
from app.database.models.conversation import Conversation
from app.database.models.ticket import Ticket
from app.services.conversation_service import handle_chat_turn, conversations

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("verify_diagnostic_loop")

def clean_session(sess_id):
    db = SessionLocal()
    db.query(Conversation).filter(Conversation.session_id == sess_id).delete()
    db.query(SessionModel).filter(SessionModel.session_id == sess_id).delete()
    db.query(Ticket).filter(Ticket.created_by == "emp_loop_test").delete()
    db.commit()
    db.close()
    conversations.pop(sess_id, None)

def run_tests():
    print("=" * 70)
    print("Starting Diagnostic Interview Loop Verification Suite")
    print("=" * 70)
    
    failures = []

    # ----------------------------------------------------
    # SCENARIO 1: Outlook -> mobile -> no -> yes
    # ----------------------------------------------------
    print("\n--- Running Scenario 1: Outlook locked loop protection ---")
    sess1 = f"sess-loop-outlook-{uuid.uuid4().hex[:4]}"
    clean_session(sess1)
    
    # Turn 1
    t1 = handle_chat_turn(session_id=None, message="Outlook account locked", user_role="EMPLOYEE", username="emp_loop_test")
    sess_id = t1.get("session_id")
    print(f"Turn 1 Response: {t1.get('response')}\nAction: {t1.get('action')}")
    
    # Turn 2
    t2 = handle_chat_turn(session_id=sess_id, message="mobile", user_role="EMPLOYEE", username="emp_loop_test")
    print(f"Turn 2 Response: {t2.get('response')}\nAction: {t2.get('action')}")
    
    # Turn 3
    t3 = handle_chat_turn(session_id=sess_id, message="no", user_role="EMPLOYEE", username="emp_loop_test")
    print(f"Turn 3 Response: {t3.get('response')}\nAction: {t3.get('action')}")
    
    # Turn 4
    t4 = handle_chat_turn(session_id=sess_id, message="yes", user_role="EMPLOYEE", username="emp_loop_test")
    print(f"Turn 4 Response: {t4.get('response')}\nAction: {t4.get('action')}")
    
    # Verify that the VPN leak question is NOT asked
    asked_vpn_leak = "vpn issue begin" in t3.get('response', '').lower() or "vpn issue begin" in t4.get('response', '').lower()
    if asked_vpn_leak:
        failures.append("Scenario 1 Failed: VPN leak question asked in Outlook category context.")
        print("[FAIL] VPN question leaked into Outlook issue!")
    else:
        print("[PASS] VPN question leakage prevented.")

    # Verify that Turn 4 doesn't ask the same question or loop infinitely
    is_looping = t3.get('response') == t4.get('response')
    if is_looping:
        failures.append("Scenario 1 Failed: Infinite loop detected. Repeating identical follow-up question.")
        print("[FAIL] Repeating identical questions!")
    else:
        print("[PASS] Repeating questions prevented.")

    # Ensure that it eventually escalated or progressed
    has_escalated = t4.get('action') == "CREATE_TICKET" or "ticket" in t4.get('response', '').lower()
    if not has_escalated:
        failures.append("Scenario 1 Failed: Interview failed to escalate or complete after multiple turns.")
        print(f"[FAIL] Final state is still in loop: {t4.get('action')}")
    else:
        print("[PASS] Escalation triggered successfully after questions exhausted.")

    # ----------------------------------------------------
    # SCENARIO 2: VPN -> Answer multiple questions
    # ----------------------------------------------------
    print("\n--- Running Scenario 2: VPN Question Limit Escalate ---")
    
    t2_1 = handle_chat_turn(session_id=None, message="I have a VPN connection error", user_role="EMPLOYEE", username="emp_loop_test")
    sess_id2 = t2_1.get("session_id")
    print(f"Turn 1 Response: {t2_1.get('response')}\nAction: {t2_1.get('action')}")
    
    t2_2 = handle_chat_turn(session_id=sess_id2, message="Connection Timeout", user_role="EMPLOYEE", username="emp_loop_test")
    print(f"Turn 2 Response: {t2_2.get('response')}\nAction: {t2_2.get('action')}")
    
    t2_3 = handle_chat_turn(session_id=sess_id2, message="Wi-Fi", user_role="EMPLOYEE", username="emp_loop_test")
    print(f"Turn 3 Response: {t2_3.get('response')}\nAction: {t2_3.get('action')}")
    
    t2_4 = handle_chat_turn(session_id=sess_id2, message="working remotely", user_role="EMPLOYEE", username="emp_loop_test")
    print(f"Turn 4 Response: {t2_4.get('response')}\nAction: {t2_4.get('action')}")
    
    # Turn 4 should escalate because it hit the question limit
    if t2_4.get('action') not in ("CREATE_TICKET", "TICKET_CREATED"):
        failures.append(f"Scenario 2 Failed: Expected action CREATE_TICKET/TICKET_CREATED after 3 follow-up questions, got {t2_4.get('action')}")
        print("[FAIL] VPN diagnostic did not escalate automatically after question limit.")
    else:
        print("[PASS] VPN diagnostic escalated successfully after 3 follow-ups.")

    # ----------------------------------------------------
    # SCENARIO 3: Password Reset
    # ----------------------------------------------------
    print("\n--- Running Scenario 3: Password Reset natural completion ---")
    
    t3_1 = handle_chat_turn(session_id=None, message="Forgot my AD password", user_role="EMPLOYEE", username="emp_loop_test")
    sess_id3 = t3_1.get("session_id")
    print(f"Turn 1 Response: {t3_1.get('response')}\nAction: {t3_1.get('action')}")
    
    t3_2 = handle_chat_turn(session_id=sess_id3, message="Windows domain login", user_role="EMPLOYEE", username="emp_loop_test")
    print(f"Turn 2 Response: {t3_2.get('response')}\nAction: {t3_2.get('action')}")
    
    # Turn 3 (Answer 1st follow-up)
    t3_3 = handle_chat_turn(session_id=sess_id3, message="yes", user_role="EMPLOYEE", username="emp_loop_test")
    print(f"Turn 3 Response: {t3_3.get('response')}\nAction: {t3_3.get('action')}")
    
    # Turn 4 (Answer 2nd follow-up)
    t3_4 = handle_chat_turn(session_id=sess_id3, message="today", user_role="EMPLOYEE", username="emp_loop_test")
    print(f"Turn 4 Response: {t3_4.get('response')}\nAction: {t3_4.get('action')}")
    
    if t3_4.get('action') not in ("CREATE_TICKET", "TICKET_CREATED", "EXECUTE_ACTION"):
        failures.append(f"Scenario 3 Failed: Password reset didn't terminate, got {t3_4.get('action')}")
        print("[FAIL] Password reset failed to terminate.")
    else:
        print("[PASS] Password reset terminated successfully.")

    print("\n" + "=" * 70)
    if failures:
        print(f"VERIFICATION FAILED: {len(failures)} failures detected.")
        for f in failures:
            print(f" - {f}")
        sys.exit(1)
    else:
        print("ALL DIAGNOSTIC LOOP SCENARIOS PASSED SUCCESSFULLY!")
        print("=" * 70)
        sys.exit(0)

if __name__ == "__main__":
    run_tests()
