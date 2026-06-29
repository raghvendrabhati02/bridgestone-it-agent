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

def test_verify_ticket_drawer():
    print("Running verify_ticket_drawer...")
    client = TestClient(app)
    
    # 1. Login to get token for ADMIN role
    login_response = client.post("/auth/login", json={"username": "admin", "password": "adminpassword"})
    assert login_response.status_code == 200, "Admin login failed"
    token = login_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    ticket_id = "TKT-DRAWER-TEST"
    
    with get_db() as db:
        # Create a test ticket in DB
        ticket = Ticket(
            ticket_id=ticket_id,
            category="VPN",
            description="VPN connection failure",
            status="OPEN",
            created_by="employee",
            priority="HIGH",
            sla_hours=4,
            servicenow_id="INC-TKT-DRAWER"
        )
        db.add(ticket)
        db.commit()

    try:
        # 2. Add customer comment & internal note via API or DB
        with get_db() as db:
            from app.services.workflow_service import WorkflowService
            WorkflowService.add_comment(
                db=db,
                ticket_id=ticket_id,
                author="employee",
                text="Hello, VPN is still broken.",
                is_internal=False,
                role="EMPLOYEE"
            )
            WorkflowService.add_comment(
                db=db,
                ticket_id=ticket_id,
                author="admin",
                text="Investigating corporate firewall logs.",
                is_internal=True,
                role="ADMIN"
            )
            db.commit()

        # 3. Call the details endpoint
        response = client.get(f"/tickets/{ticket_id}/details", headers=headers)
        assert response.status_code == 200, f"Failed to get ticket details: {response.text}"
        data = response.json()

        # 4. Verify properties required for the ServiceNow details drawer
        assert data["ticket"]["ticket_id"] == ticket_id
        assert data["ticket"]["category"] == "VPN"
        assert data["ticket"]["priority"] == "HIGH"
        assert data["ticket"]["servicenow_id"] == "INC-TKT-DRAWER"
        
        # Verify requester fields (operating system & device workstation details)
        assert "operating_system" in data["requester"]
        assert "device" in data["requester"]
        
        # Verify separate arrays of comments & internal notes
        assert len(data["comments"]) == 1, f"Expected 1 comment, got {len(data['comments'])}"
        assert len(data["internal_notes"]) == 1, f"Expected 1 internal note, got {len(data['internal_notes'])}"
        assert data["comments"][0]["text"] == "Hello, VPN is still broken."
        assert data["internal_notes"][0]["text"] == "Investigating corporate firewall logs."

        print("[PASS] verify_ticket_drawer.py: all checks passed successfully!")

    finally:
        # Cleanup
        with get_db() as db:
            db.query(TicketComment).filter(TicketComment.ticket_id == ticket_id).delete()
            db.query(TicketTimeline).filter(TicketTimeline.ticket_id == ticket_id).delete()
            db.query(Ticket).filter(Ticket.ticket_id == ticket_id).delete()
            db.commit()

if __name__ == "__main__":
    test_verify_ticket_drawer()
