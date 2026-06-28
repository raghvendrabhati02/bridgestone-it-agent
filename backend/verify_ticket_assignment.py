import os
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.database.session import get_db
from app.database.models.ticket import Ticket
from app.services.workflow_service import WorkflowService

def test_ticket_assignment():
    print("Running verify_ticket_assignment...")
    with get_db() as db:
        ticket_id = "TEST-ASGN-001"
        ticket = Ticket(
            ticket_id=ticket_id,
            category="SAP",
            description="Testing assignment workflows",
            status="OPEN",
            created_by="tester"
        )
        db.add(ticket)
        db.commit()

        try:
            # 1. First assignment
            WorkflowService.assign_ticket(
                db=db,
                ticket_id=ticket_id,
                new_engineer="Bob SAP",
                assigned_by="admin_user",
                reason="Initial assignment",
                new_group="SAP Support Team"
            )
            db.commit()
            
            db.refresh(ticket)
            assert ticket.assigned_engineer == "Bob SAP"
            assert ticket.assigned_team == "SAP Support Team"

            # 2. Reassignment
            WorkflowService.assign_ticket(
                db=db,
                ticket_id=ticket_id,
                new_engineer="Charlie SAP",
                assigned_by="admin_user",
                reason="Escalation to senior",
                new_group="SAP Tier 2"
            )
            db.commit()

            db.refresh(ticket)
            assert ticket.assigned_engineer == "Charlie SAP"
            
            # 3. Query history
            from app.database.models.workflow_models import AssignmentHistory
            history = db.query(AssignmentHistory).filter(AssignmentHistory.ticket_id == ticket_id).order_by(AssignmentHistory.assigned_time.asc()).all()
            assert len(history) == 2, "Expected 2 assignment logs"
            
            assert history[0].new_engineer == "Bob SAP"
            assert history[1].previous_engineer == "Bob SAP"
            assert history[1].new_engineer == "Charlie SAP"
            assert history[1].reason == "Escalation to senior"

            print("verify_ticket_assignment.py: SUCCESS")

        finally:
            from app.database.models.workflow_models import AssignmentHistory, TicketTimeline
            db.query(AssignmentHistory).filter(AssignmentHistory.ticket_id == ticket_id).delete()
            db.query(TicketTimeline).filter(TicketTimeline.ticket_id == ticket_id).delete()
            db.query(Ticket).filter(Ticket.ticket_id == ticket_id).delete()
            db.commit()

if __name__ == "__main__":
    test_ticket_assignment()
