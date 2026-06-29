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

def test_verify_comments_notes():
    print("Running verify_comments_notes...")
    client = TestClient(app)
    
    # 1. Login as ADMIN and EMPLOYEE
    admin_login = client.post("/auth/login", json={"username": "admin", "password": "adminpassword"})
    admin_headers = {"Authorization": f"Bearer {admin_login.json()['access_token']}"}

    employee_login = client.post("/auth/login", json={"username": "employee", "password": "employeepassword"})
    employee_headers = {"Authorization": f"Bearer {employee_login.json()['access_token']}"}

    ticket_id = "TKT-COMMENTS-TEST"

    with get_db() as db:
        # Cleanup first
        db.query(TicketComment).filter(TicketComment.ticket_id == ticket_id).delete()
        db.query(TicketTimeline).filter(TicketTimeline.ticket_id == ticket_id).delete()
        db.query(Ticket).filter(Ticket.ticket_id == ticket_id).delete()
        db.commit()

        # Create a test ticket
        ticket = Ticket(
            ticket_id=ticket_id,
            category="VPN",
            description="VPN login issue",
            status="OPEN",
            created_by="employee",
            priority="LOW"
        )
        db.add(ticket)
        db.commit()

    try:
        # 2. Add customer comment as EMPLOYEE (should succeed)
        res = client.post(
            f"/tickets/{ticket_id}/comments",
            json={"text": "Here is a message from the employee.", "is_internal": False},
            headers=employee_headers
        )
        assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"

        # 3. Try to add internal note as EMPLOYEE (should fail with 403)
        res = client.post(
            f"/tickets/{ticket_id}/comments",
            json={"text": "Trying to post confidential internal note.", "is_internal": True},
            headers=employee_headers
        )
        assert res.status_code == 403, f"Expected 403, got {res.status_code}"

        # 4. Add internal note as ADMIN (should succeed)
        res = client.post(
            f"/tickets/{ticket_id}/comments",
            json={"text": "Confidential investigation details for admins/managers.", "is_internal": True},
            headers=admin_headers
        )
        assert res.status_code == 200, f"Expected 200, got {res.status_code}"

        # 5. Fetch details as EMPLOYEE (should see comments but NOT internal notes)
        details_emp = client.get(f"/tickets/{ticket_id}/details", headers=employee_headers)
        assert details_emp.status_code == 200
        data_emp = details_emp.json()
        assert len(data_emp["comments"]) == 1
        assert len(data_emp["internal_notes"]) == 0, "Employee should not see internal notes"

        # 6. Fetch details as ADMIN (should see comments AND internal notes)
        details_adm = client.get(f"/tickets/{ticket_id}/details", headers=admin_headers)
        assert details_adm.status_code == 200
        data_adm = details_adm.json()
        assert len(data_adm["comments"]) == 1
        assert len(data_adm["internal_notes"]) == 1, "Admin should see internal notes"

        print("[PASS] verify_comments_notes.py: customer comments and internal work notes RBAC gates passed successfully!")

    finally:
        # Cleanup
        with get_db() as db:
            db.query(TicketComment).filter(TicketComment.ticket_id == ticket_id).delete()
            db.query(TicketTimeline).filter(TicketTimeline.ticket_id == ticket_id).delete()
            db.query(Ticket).filter(Ticket.ticket_id == ticket_id).delete()
            db.commit()

if __name__ == "__main__":
    test_verify_comments_notes()
