import os
import sys

# Add app directory to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "app")))

from app.database.connection import SessionLocal
from app.services.conversation_service import handle_chat_turn
from app.database.models.service_request import ServiceRequest

def verify_workflow():
    print("=== Service Request AI Workflow Verification ===")
    failures = []
    
    def check(name, condition, message):
        if condition:
            print(f"  [PASS] {name}: {message}")
        else:
            print(f"  [FAIL] {name}: {message}")
            failures.append(name)

    db = SessionLocal()
    try:
        # Start a new conversation for request
        # Step 1: User requests SAP Access
        print("  Sending: 'I want to request SAP access'")
        res = handle_chat_turn(None, "I want to request SAP access", "employee", "EMPLOYEE")
        session_id = res.get("session_id")
        check("Session ID Created", session_id is not None, "Session created successfully.")
        check("Slot filling prompt", "SAP system" in res.get("response", "") or "details" in res.get("response", ""), "Slot filling prompt for SAP system received.")
        
        # Step 2: User provides SAP system (PRD)
        print("  Sending: 'PRD'")
        res = handle_chat_turn(session_id, "PRD", "employee", "EMPLOYEE")
        check("Slot filling prompt 2", "role" in res.get("response", "") or "details" in res.get("response", ""), "Slot filling prompt for role received.")
        
        # Step 3: User provides Role (FICO Analyst)
        print("  Sending: 'FICO Analyst'")
        res = handle_chat_turn(session_id, "FICO Analyst", "employee", "EMPLOYEE")
        check("Slot filling prompt 3", "justification" in res.get("response", "") or "reason" in res.get("response", "") or "details" in res.get("response", ""), "Slot filling prompt for justification received.")
        
        # Step 4: User provides Justification (Monthly audit reconciliation)
        print("  Sending: 'Monthly audit reconciliation'")
        res = handle_chat_turn(session_id, "Monthly audit reconciliation", "employee", "EMPLOYEE")
        check("Service Request Created", "created" in res.get("response", "").lower() or "success" in res.get("response", "").lower() or "REQ" in res.get("response", ""), f"Service Request created confirmation response received.")
        
        # Verify request exists in database
        latest_req = db.query(ServiceRequest).order_by(ServiceRequest.id.desc()).first()
        check("Database Entry Created", latest_req is not None, "Request entry found in database.")
        if latest_req:
            check("Database Item Matches", latest_req.service_name == "SAP Account Access", f"Seeded item matches 'SAP Account Access'.")
            check("Database Item Status", latest_req.status == "PENDING_APPROVAL", f"Status matches PENDING_APPROVAL.")


        print("\n" + "="*55)
        if len(failures) == 0:
            print("  ALL SERVICE REQUEST AI WORKFLOW CHECKS PASSED [OK]")
        else:
            print(f"  VERIFICATION FAILED: {len(failures)} checks failed [ERROR]")
        print("="*55)
        
    finally:
        db.close()

if __name__ == "__main__":
    verify_workflow()
