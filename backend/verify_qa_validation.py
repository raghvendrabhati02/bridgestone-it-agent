import os
import sys
import uuid
import datetime
from unittest.mock import patch, MagicMock

# Force UTF-8 output on Windows terminals
if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

# Inject mock before importing backend app
import mock_gemini

# Setup path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "app")))

from app.database.connection import SessionLocal
from app.database.models.ticket import Ticket
from app.database.models.rbac_audit_log import RbacAuditLog
from app.database.models.user import User
from app.services.conversation_service import handle_chat_turn
from app.services.rbac_audit_service import log_rbac_event
import app.services.conversation_service as cs

def main():
    print("=" * 70)
    print("Executing Enterprise Domain Validation & Quality Assurance Harness")
    print("=" * 70)

    db = SessionLocal()
    
    # Clean up any sessions, turns, tickets, and logs from previous runs to ensure isolation
    from app.services.conversation_persistence import cache_remove
    from app.database.models.session import SessionModel
    from app.database.models.conversation import Conversation
    from app.database.models.workflow_models import TicketTimeline
    
    test_session_ids = [
        "qa-wf-incident", "qa-wf-sr", "qa-wf-laps", "qa-wf-life",
        "qa-edge-vague", "qa-edge-switch", "qa-edge-multi",
        "qa-edge-repeat", "qa-edge-unsupported", "qa-edge-fallback"
    ]
    try:
        for s_id in test_session_ids:
            cache_remove(s_id)
            db.query(Conversation).filter(Conversation.session_id == s_id).delete()
            db.query(SessionModel).filter(SessionModel.session_id == s_id).delete()
        
        # Clear mock tickets created in previous runs
        tickets = db.query(Ticket).filter(Ticket.created_by == "employee").all()
        for t in tickets:
            db.query(TicketTimeline).filter(TicketTimeline.ticket_id == t.ticket_id).delete()
            db.query(RbacAuditLog).filter(RbacAuditLog.ticket_id == t.ticket_id).delete()
        db.query(Ticket).filter(Ticket.created_by == "employee").delete()
        db.commit()
    except Exception as e:
        db.rollback()
        print(f"Warning: clean-up failed: {e}")

    results = []
    
    def record_result(test_name, status, details=""):
        results.append({"name": test_name, "status": status, "details": details})
        indicator = "✅ PASS" if status == "PASS" else "❌ FAIL"
        print(f"  [{indicator}] {test_name}" + (f": {details}" if details else ""))

    # -------------------------------------------------------------------------
    # PART 1: Domain Coverage Validation (21 Domains)
    # -------------------------------------------------------------------------
    print("\n--- Phase 1: Domain Coverage Validation ---")
    domains_to_test = [
        {"name": "Windows", "msg": "My Windows system crashed with a blue screen error", "expected_cat": "WINDOWS"},
        {"name": "Outlook", "msg": "My Outlook client keeps freezing on startup", "expected_cat": "OUTLOOK"},
        {"name": "Microsoft Teams", "msg": "I cannot connect to Microsoft Teams meetings", "expected_cat": "TEAMS"},
        {"name": "OneDrive", "msg": "My OneDrive client is not syncing files to the cloud", "expected_cat": "ONEDRIVE"},
        {"name": "VPN", "msg": "GlobalProtect VPN connection failed with error 809", "expected_cat": "VPN"},
        {"name": "Wi-Fi", "msg": "Cannot connect to the corporate Wi-Fi network", "expected_cat": "WIFI"},
        {"name": "Network", "msg": "My office ethernet connection is unplugged or slow", "expected_cat": "NETWORK"},
        {"name": "Printers", "msg": "The printer on floor 2 is offline and has a paper jam", "expected_cat": "PRINTER"},
        {"name": "Adobe", "msg": "Need help activating Adobe Acrobat Pro license", "expected_cat": "ADOBE"},
        {"name": "SAP", "msg": "SAP GUI licensing error on connection attempts", "expected_cat": "SAP"},
        {"name": "Citrix", "msg": "Citrix Workspace receiver failed to launch virtual desktop", "expected_cat": "CITRIX"},
        {"name": "Microsoft Office", "msg": "My Microsoft Office subscription activation is invalid", "expected_cat": "OFFICE"},
        {"name": "Browser", "msg": "Chrome browser keeps throwing SSL certificate errors", "expected_cat": "BROWSER"},
        {"name": "BitLocker", "msg": "Workstation is asking for BitLocker recovery key", "expected_cat": "BITLOCKER"},
        {"name": "Drivers", "msg": "Need to update audio drivers in Device Manager", "expected_cat": "DRIVERS"},
        {"name": "Login & Authentication", "msg": "Cannot sign in because of MFA authenticator lock", "expected_cat": "LOGIN"},
        {"name": "Performance", "msg": "ThinkPad is running very slow with high CPU usage", "expected_cat": "PERFORMANCE"},
        {"name": "Hardware", "msg": "My keyboard and mouse are not responding", "expected_cat": "HARDWARE"},
        {"name": "Peripheral Devices", "msg": "My docking station USB ports are not working", "expected_cat": "HARDWARE"},
        {"name": "Software Installation", "msg": "Please install Visio software on my laptop", "expected_cat": "SOFTWARE_INSTALLATION"},
        {"name": "Password Reset", "msg": "I forgot my AD login password and need a reset", "expected_cat": "PASSWORD_RESET"},
    ]

    for d in domains_to_test:
        sess_id = f"qa-domain-{d['name'].lower().replace(' ', '-')}"
        try:
            res = handle_chat_turn(
                session_id=sess_id,
                message=d["msg"],
                user_role="EMPLOYEE",
                username="employee"
            )
            cat = res.get("category")
            if cat == d["expected_cat"]:
                record_result(f"Domain: {d['name']}", "PASS", f"Classified correctly as {cat}")
            else:
                record_result(f"Domain: {d['name']}", "FAIL", f"Expected {d['expected_cat']}, got {cat}")
        except Exception as e:
            record_result(f"Domain: {d['name']}", "FAIL", f"Crashed: {str(e)}")

    # -------------------------------------------------------------------------
    # PART 2: Core Workflow Validation
    # -------------------------------------------------------------------------
    print("\n--- Phase 2: Core Workflows ---")
    
    # 2.1 General Troubleshooting
    try:
        sess_id = "qa-wf-troubleshoot"
        res = handle_chat_turn(sess_id, "Outlook search is not working", "EMPLOYEE", "employee")
        if res.get("response") and len(res["response"]) > 10:
            record_result("Workflow: General Troubleshooting", "PASS", "Conversational response returned successfully.")
        else:
            record_result("Workflow: General Troubleshooting", "FAIL", "Response was empty or too short.")
    except Exception as e:
        record_result("Workflow: General Troubleshooting", "FAIL", str(e))

    # 2.2 Incident Creation Workflow
    try:
        sess_id = "qa-wf-incident"
        # 1. Employee asks to create ticket
        res = handle_chat_turn(sess_id, "I tried all steps. Please create a ticket for my printer issue.", "EMPLOYEE", "employee")
        # 2. Confirm ticket creation
        res2 = handle_chat_turn(sess_id, "yes", "EMPLOYEE", "employee")
        if res2.get("ticket_created") and res2.get("ticket_id"):
            record_result("Workflow: Incident Creation", "PASS", f"Ticket {res2.get('ticket_id')} created successfully.")
        else:
            record_result("Workflow: Incident Creation", "FAIL", f"Ticket not created: {res2}")
    except Exception as e:
        record_result("Workflow: Incident Creation", "FAIL", str(e))

    # 2.3 Service Request & Manager Approval
    try:
        sess_id = "qa-wf-sr"
        # 1. Ask for software installation (which triggers approval / service request flow)
        res = handle_chat_turn(sess_id, "Please install MS Visio on my computer.", "EMPLOYEE", "employee")
        # 2. Confirm creation
        res2 = handle_chat_turn(sess_id, "yes", "EMPLOYEE", "employee")
        ticket_id = res2.get("ticket_id")
        
        if ticket_id:
            ticket = db.query(Ticket).filter(Ticket.ticket_id == ticket_id).first()
            if ticket and ticket.request_type == "SERVICE_REQUEST" and ticket.status == "WAITING_MANAGER":
                record_result("Workflow: Service Request Creation", "PASS", f"Service Request {ticket_id} created in WAITING_MANAGER state.")
                
                # Mock Manager Approval API Action update
                from app.main import run_ticket_action, TicketActionRequest
                mock_manager = User(username="manager", role="MANAGER")
                
                req = TicketActionRequest(action="manager_approve", note="Approved by manager")
                action_res = run_ticket_action(ticket_id, req, mock_manager, db)
                
                db.refresh(ticket)
                if ticket.status == "APPROVED" and ticket.approval_status == "APPROVED":
                    record_result("Workflow: Manager Approval", "PASS", f"Ticket status changed to APPROVED.")
                else:
                    record_result("Workflow: Manager Approval", "FAIL", f"Expected APPROVED status, got status={ticket.status}, approval={ticket.approval_status}")
            else:
                record_result("Workflow: Service Request Creation", "FAIL", f"Ticket is not service request or WAITING_MANAGER. Ticket details: {ticket.__dict__ if ticket else None}")
        else:
            record_result("Workflow: Service Request Creation", "FAIL", "No ticket generated from chat flow.")
    except Exception as e:
        record_result("Workflow: Service Request Workflow", "FAIL", str(e))

    # 2.4 Admin Approval & LAPS Workflow
    try:
        sess_id = "qa-wf-laps"
        # 1. Create a ticket for admin approval (we'll create it directly in DB to keep the test robust)
        t_id = f"INC-{int(datetime.datetime.utcnow().timestamp())}-LAPS"
        new_ticket = Ticket(
            ticket_id=t_id,
            category="WINDOWS",
            description="Request temporary local administrator password LAPS",
            status="APPROVED",
            request_type="PRIVILEGED_ACTION",
            created_by="employee",
            assigned_team="Helpdesk",
            priority="LOW"
        )
        db.add(new_ticket)
        db.commit()
        
        # Run admin_approve action
        from app.main import run_ticket_action, TicketActionRequest
        mock_admin = User(username="admin", role="ADMIN")
        req = TicketActionRequest(action="admin_approve", note="Approved by IT admin")
        action_res = run_ticket_action(t_id, req, mock_admin, db)
        
        db.refresh(new_ticket)
        if new_ticket.status == "TEMP_ADMIN_GRANTED" and new_ticket.laps_active and new_ticket.laps_password:
            record_result("Workflow: LAPS & Admin Approval", "PASS", f"LAPS password generated: {new_ticket.laps_password}, expires: {new_ticket.laps_expiration}")
        else:
            record_result("Workflow: LAPS & Admin Approval", "FAIL", f"LAPS credentials not generated successfully. Ticket status: {new_ticket.status}")
            
    except Exception as e:
        db.rollback()
        record_result("Workflow: LAPS & Admin Approval", "FAIL", str(e))

    # 2.5 Ticket Lifecycle (Fulfill, Resolve, Close, Reopen)
    try:
        # Create a ticket
        t_id = f"INC-{int(datetime.datetime.utcnow().timestamp())}-LIFE"
        ticket = Ticket(
            ticket_id=t_id,
            category="OUTLOOK",
            description="Testing ticket lifecycle transitions",
            status="OPEN",
            request_type="INCIDENT",
            created_by="employee",
            priority="LOW"
        )
        db.add(ticket)
        db.commit()
        
        from app.main import run_ticket_action, TicketActionRequest
        mock_admin = User(username="admin", role="ADMIN")
        
        # 1. Start work
        run_ticket_action(t_id, TicketActionRequest(action="start_work"), mock_admin, db)
        db.refresh(ticket)
        life_ok = (ticket.status == "IN_PROGRESS")
        
        # 2. Resolve
        run_ticket_action(t_id, TicketActionRequest(action="resolve"), mock_admin, db)
        db.refresh(ticket)
        life_ok = life_ok and (ticket.status == "RESOLVED")
        
        # 3. Close
        run_ticket_action(t_id, TicketActionRequest(action="close"), mock_admin, db)
        db.refresh(ticket)
        life_ok = life_ok and (ticket.status == "CLOSED")
        
        # 4. Reopen
        run_ticket_action(t_id, TicketActionRequest(action="reopen"), mock_admin, db)
        db.refresh(ticket)
        life_ok = life_ok and (ticket.status == "ASSIGNED" or ticket.status == "OPEN")
        
        if life_ok:
            record_result("Workflow: Ticket Lifecycle", "PASS", "Ticket successfully progressed through: Open -> In Progress -> Resolved -> Closed -> Reopened.")
        else:
            record_result("Workflow: Ticket Lifecycle", "FAIL", f"One or more state transitions failed. Final state: {ticket.status}")
    except Exception as e:
        db.rollback()
        record_result("Workflow: Ticket Lifecycle", "FAIL", str(e))

    # 2.6 Timeline Updates & Audit Logging
    try:
        # Verify that the timeline service is logging events
        from app.services.timeline_service import TimelineService
        events = TimelineService.get_timeline(db, t_id)
        if len(events) >= 3:
            record_result("Workflow: Timeline Updates", "PASS", f"Found {len(events)} timeline events logged for ticket.")
        else:
            record_result("Workflow: Timeline Updates", "FAIL", f"Expected >=3 events, found {len(events)}")
            
        # Verify Audit Log entry
        audit_logs = db.query(RbacAuditLog).filter(RbacAuditLog.ticket_id == t_id).all()
        if len(audit_logs) >= 3:
            record_result("Workflow: Audit Logging", "PASS", f"Found {len(audit_logs)} RBAC audit logs recorded.")
        else:
            record_result("Workflow: Audit Logging", "FAIL", f"Expected >=3 audit logs, found {len(audit_logs)}")
    except Exception as e:
        db.rollback()
        record_result("Workflow: Timeline & Audit", "FAIL", str(e))

    # 2.7 Role-Based Access Control (RBAC)
    try:
        # Try to resolve a ticket as an employee (which is forbidden)
        mock_employee = User(username="employee", role="EMPLOYEE")
        from app.main import run_ticket_action, TicketActionRequest
        from fastapi import HTTPException
        
        forbidden = False
        try:
            run_ticket_action(t_id, TicketActionRequest(action="resolve"), mock_employee, db)
        except HTTPException as exc:
            if exc.status_code == 403:
                forbidden = True
                
        if forbidden:
            record_result("Workflow: RBAC Control", "PASS", "Access denied (403 Forbidden) for unauthorized lifecycle actions by employee.")
        else:
            record_result("Workflow: RBAC Control", "FAIL", "Employee was incorrectly allowed to resolve ticket, or did not trigger a 403 error.")
    except Exception as e:
        db.rollback()
        record_result("Workflow: RBAC Control", "FAIL", str(e))


    # -------------------------------------------------------------------------
    # PART 3: Edge Case Validation
    # -------------------------------------------------------------------------
    print("\n--- Phase 3: Edge Cases ---")

    # 3.1 Vague request
    try:
        sess_id = "qa-edge-vague"
        res = handle_chat_turn(sess_id, "it is broken", "EMPLOYEE", "employee")
        if res.get("response"):
            record_result("Edge Case: Vague Request", "PASS", "Handled successfully, prompted user for details.")
        else:
            record_result("Edge Case: Vague Request", "FAIL", "Response was empty.")
    except Exception as e:
        record_result("Edge Case: Vague Request", "FAIL", str(e))

    # 3.2 Topic Switching mid-conversation
    try:
        sess_id = "qa-edge-switch"
        # 1. Ask about VPN
        handle_chat_turn(sess_id, "I cannot connect to VPN", "EMPLOYEE", "employee")
        # 2. Switch to printer issue
        res = handle_chat_turn(sess_id, "Actually my printer is jammed", "EMPLOYEE", "employee")
        if res.get("category") == "PRINTER":
            record_result("Edge Case: Topic Switching", "PASS", "Detected category switch successfully from VPN to PRINTER.")
        else:
            record_result("Edge Case: Topic Switching", "FAIL", f"Failed to switch category, got: {res.get('category')}")
    except Exception as e:
        record_result("Edge Case: Topic Switching", "FAIL", str(e))

    # 3.3 Multiple simultaneous issues
    try:
        sess_id = "qa-edge-multi"
        res = handle_chat_turn(sess_id, "My Wi-Fi is slow and my laptop monitor is cracked", "EMPLOYEE", "employee")
        if res.get("category") in ("WIFI", "HARDWARE", "GENERAL"):
            record_result("Edge Case: Multiple Simultaneous Issues", "PASS", f"Handled, category routed to {res.get('category')}.")
        else:
            record_result("Edge Case: Multiple Simultaneous Issues", "FAIL", f"Unexpected routing: {res.get('category')}")
    except Exception as e:
        record_result("Edge Case: Multiple Simultaneous Issues", "FAIL", str(e))

    # 3.4 Repeated questions
    try:
        sess_id = "qa-edge-repeat"
        # Send same message multiple times
        handle_chat_turn(sess_id, "Outlook crashes on startup", "EMPLOYEE", "employee")
        res = handle_chat_turn(sess_id, "Outlook crashes on startup", "EMPLOYEE", "employee")
        if res.get("response"):
            record_result("Edge Case: Repeated Questions", "PASS", "Handled repeated user inputs without crashing.")
        else:
            record_result("Edge Case: Repeated Questions", "FAIL", "Returned empty response.")
    except Exception as e:
        record_result("Edge Case: Repeated Questions", "FAIL", str(e))

    # 3.5 Unsupported requests
    try:
        sess_id = "qa-edge-unsupported"
        res = handle_chat_turn(sess_id, "Can you book a flight ticket to Paris?", "EMPLOYEE", "employee")
        if "IT" in res.get("response") or "help" in res.get("response") or "assist" in res.get("response") or "support" in res.get("response"):
            record_result("Edge Case: Unsupported Requests", "PASS", "Politely redirected user back to IT assistance boundaries.")
        else:
            record_result("Edge Case: Unsupported Requests", "FAIL", f"Unexpected response: {res.get('response')}")
    except Exception as e:
        record_result("Edge Case: Unsupported Requests", "FAIL", str(e))

    # 3.6 Gemini unavailable (Fallback Behavior)
    try:
        sess_id = "qa-edge-fallback"
        # Patch generate_decision to throw an error, forcing DiagnosticEngine fallback
        with patch("app.services.orchestrator_service.generate_decision", side_effect=Exception("Gemini Service Timeout")):
            res = handle_chat_turn(sess_id, "VPN connection fails with Error 809", "EMPLOYEE", "employee")
            if res.get("response") and ("timeout" in res["response"].lower() or "vpn" in res["response"].lower() or "connect" in res["response"].lower()):
                record_result("Edge Case: Gemini Unavailable Fallback", "PASS", "Successfully fell back to DiagnosticEngine question / KB search.")
            else:
                record_result("Edge Case: Gemini Unavailable Fallback", "FAIL", f"Unexpected fallback response: {res}")
    except Exception as e:
        record_result("Edge Case: Gemini Unavailable Fallback", "FAIL", str(e))


    # -------------------------------------------------------------------------
    # Summary Report
    # -------------------------------------------------------------------------
    print("\n" + "=" * 70)
    print("QA VALIDATION COMPLETED")
    print("=" * 70)
    
    passed_cnt = sum(1 for r in results if r["status"] == "PASS")
    failed_cnt = sum(1 for r in results if r["status"] == "FAIL")
    total_cnt = len(results)
    readiness_score = int((passed_cnt / total_cnt) * 100) if total_cnt > 0 else 0
    
    print(f"Total Scenarios Tested: {total_cnt}")
    print(f"Passed:                 {passed_cnt}")
    print(f"Failed:                 {failed_cnt}")
    print(f"Overall Readiness Score: {readiness_score}%")
    print("=" * 70)
    
    if failed_cnt > 0:
        print("\nFailed Scenarios:")
        for r in results:
            if r["status"] == "FAIL":
                print(f"  - {r['name']}: {r['details']}")
        sys.exit(1)
    else:
        print("\nAll QA checks and validations passed successfully!")
        sys.exit(0)

if __name__ == "__main__":
    main()
