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

def test_verify_ticket_actions():
    print("Running verify_ticket_actions...")
    client = TestClient(app)
    
    # 1. Login to get tokens for different roles
    admin_login = client.post("/auth/login", json={"username": "admin", "password": "adminpassword"})
    admin_token = admin_login.json()["access_token"]
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    employee_login = client.post("/auth/login", json={"username": "employee", "password": "employeepassword"})
    employee_token = employee_login.json()["access_token"]
    employee_headers = {"Authorization": f"Bearer {employee_token}"}

    ticket_id = "TKT-ACTIONS-TEST"
    
    # Setup test ticket in its own isolated transaction block
    with get_db() as db:
        # Cleanup any leftover first
        db.query(TicketComment).filter(TicketComment.ticket_id == ticket_id).delete()
        db.query(TicketTimeline).filter(TicketTimeline.ticket_id == ticket_id).delete()
        db.query(Ticket).filter(Ticket.ticket_id == ticket_id).delete()
        db.commit()

        ticket = Ticket(
            ticket_id=ticket_id,
            category="Outlook",
            description="Outlook email sync failing",
            status="OPEN",
            created_by="employee",
            priority="MEDIUM",
            assigned_team="Helpdesk"
        )
        db.add(ticket)
        db.commit()

    try:
        # 2. Try start_work as employee (should fail with 403)
        res = client.post(f"/tickets/{ticket_id}/action", json={"action": "start_work"}, headers=employee_headers)
        assert res.status_code == 403, f"Expected 403, got {res.status_code}"

        # 3. Perform start_work as admin (should succeed)
        res = client.post(f"/tickets/{ticket_id}/action", json={"action": "start_work"}, headers=admin_headers)
        assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
        
        # Verify via details endpoint
        details_res = client.get(f"/tickets/{ticket_id}/details", headers=admin_headers)
        assert details_res.json()["ticket"]["status"] == "IN_PROGRESS"

        # 4. Perform change_priority as admin
        res = client.post(f"/tickets/{ticket_id}/action", json={"action": "change_priority", "priority": "HIGH"}, headers=admin_headers)
        assert res.status_code == 200, f"Expected 200, got {res.status_code}"
        
        details_res = client.get(f"/tickets/{ticket_id}/details", headers=admin_headers)
        assert details_res.json()["ticket"]["priority"] == "HIGH"

        # 5. Perform transfer_team as admin
        res = client.post(f"/tickets/{ticket_id}/action", json={"action": "transfer_team", "team": "Network"}, headers=admin_headers)
        assert res.status_code == 200, f"Expected 200, got {res.status_code}"
        
        details_res = client.get(f"/tickets/{ticket_id}/details", headers=admin_headers)
        assert details_res.json()["ticket"]["assigned_team"] == "Network"

        # 6. Perform resolve as admin
        res = client.post(f"/tickets/{ticket_id}/action", json={"action": "resolve"}, headers=admin_headers)
        assert res.status_code == 200, f"Expected 200, got {res.status_code}"
        
        details_res = client.get(f"/tickets/{ticket_id}/details", headers=admin_headers)
        assert details_res.json()["ticket"]["status"] == "RESOLVED"

        # 7. Confirm resolution as employee (since employee is creator)
        res = client.post(f"/tickets/{ticket_id}/action", json={"action": "confirm_resolution"}, headers=employee_headers)
        assert res.status_code == 200, f"Expected 200, got {res.status_code}"
        
        details_res = client.get(f"/tickets/{ticket_id}/details", headers=admin_headers)
        assert details_res.json()["ticket"]["status"] == "CLOSED"

        # 8. Reopen as employee
        res = client.post(f"/tickets/{ticket_id}/action", json={"action": "reopen"}, headers=employee_headers)
        assert res.status_code == 200, f"Expected 200, got {res.status_code}"
        
        details_res = client.get(f"/tickets/{ticket_id}/details", headers=admin_headers)
        assert details_res.json()["ticket"]["status"] == "ASSIGNED"

        print("[PASS] verify_ticket_actions.py: all actions and RBAC checks passed successfully!")

    finally:
        # Cleanup in isolated session block
        with get_db() as db:
            db.query(TicketComment).filter(TicketComment.ticket_id == ticket_id).delete()
            db.query(TicketTimeline).filter(TicketTimeline.ticket_id == ticket_id).delete()
            db.query(Ticket).filter(Ticket.ticket_id == ticket_id).delete()
            db.commit()

if __name__ == "__main__":
    test_verify_ticket_actions()
