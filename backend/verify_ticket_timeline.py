import os
import sys

# Set testing environment variable
os.environ["TESTING"] = "True"

# Add app directory to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "app")))

from fastapi.testclient import TestClient
from app.main import app
from app.database.session import get_db
from app.database.models.ticket import Ticket
from app.database.models.workflow_models import TicketComment, TicketTimeline

def test_verify_ticket_timeline():
    print("Running verify_ticket_timeline...")
    client = TestClient(app)
    
    # 1. Login as ADMIN and EMPLOYEE
    admin_login = client.post("/auth/login", json={"username": "admin", "password": "adminpassword"})
    admin_headers = {"Authorization": f"Bearer {admin_login.json()['access_token']}"}

    employee_login = client.post("/auth/login", json={"username": "employee", "password": "employeepassword"})
    employee_headers = {"Authorization": f"Bearer {employee_login.json()['access_token']}"}

    ticket_id = "TKT-TIMELINE-TEST"

    with get_db() as db:
        # Cleanup first
        db.query(TicketComment).filter(TicketComment.ticket_id == ticket_id).delete()
        db.query(TicketTimeline).filter(TicketTimeline.ticket_id == ticket_id).delete()
        db.query(Ticket).filter(Ticket.ticket_id == ticket_id).delete()
        db.commit()

        # Create a test ticket
        ticket = Ticket(
            ticket_id=ticket_id,
            category="Software",
            description="Software installation request",
            status="OPEN",
            created_by="employee",
            priority="LOW"
        )
        db.add(ticket)
        db.commit()

    try:
        # 2. Add an internal note (which logs an internal timeline event)
        client.post(
            f"/tickets/{ticket_id}/action",
            json={"action": "add_note", "note": "Confidential investigation details."},
            headers=admin_headers
        )
        
        # 3. Add a public comment
        client.post(
            f"/tickets/{ticket_id}/comments",
            json={"text": "Hello, we will start working on this soon.", "is_internal": False},
            headers=admin_headers
        )

        # 4. Get ticket details as ADMIN (should see all timeline items including internal events)
        res_admin = client.get(f"/tickets/{ticket_id}/details", headers=admin_headers)
        assert res_admin.status_code == 200, "Admin could not fetch details"
        admin_timeline = res_admin.json()["timeline"]
        
        # Admin should see Ticket Created, Note Added, Comment Added
        print(f"Admin timeline count: {len(admin_timeline)}")
        assert len(admin_timeline) >= 2, "Admin should see all timeline logs"
        
        # 5. Get ticket details as EMPLOYEE (should NOT see the internal note timeline logs)
        res_employee = client.get(f"/tickets/{ticket_id}/details", headers=employee_headers)
        assert res_employee.status_code == 200, "Employee could not fetch details"
        employee_timeline = res_employee.json()["timeline"]
        
        print(f"Employee timeline count: {len(employee_timeline)}")
        
        # Check that none of the timeline events visible to employee contain internal/confidential note indicators
        for evt in employee_timeline:
            title = str(evt.get("title", "")).lower()
            desc = str(evt.get("description", "")).lower()
            type_val = str(evt.get("type", "")).lower()
            action_val = str(evt.get("action", "")).lower()
            
            assert "internal note" not in title, "Employee saw internal note title"
            assert "work note" not in title, "Employee saw work note title"
            assert type_val != "note_added", "Employee saw note_added event type"
            assert action_val != "add_internal_note", "Employee saw add_internal_note action"
            assert "confidential" not in desc, "Employee saw confidential description details"

        print("[PASS] verify_ticket_timeline.py: timeline logs creation and employee privacy gates verified!")

    finally:
        # Cleanup
        with get_db() as db:
            db.query(TicketComment).filter(TicketComment.ticket_id == ticket_id).delete()
            db.query(TicketTimeline).filter(TicketTimeline.ticket_id == ticket_id).delete()
            db.query(Ticket).filter(Ticket.ticket_id == ticket_id).delete()
            db.commit()

if __name__ == "__main__":
    test_verify_ticket_timeline()
