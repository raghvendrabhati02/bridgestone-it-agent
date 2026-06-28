import os
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.database.session import get_db
from app.database.models.ticket import Ticket
from app.services.workflow_service import WorkflowService

def test_internal_notes_rbac():
    print("Running verify_internal_notes...")
    with get_db() as db:
        ticket_id = "TEST-RBAC-001"
        ticket = Ticket(
            ticket_id=ticket_id,
            category="GENERAL",
            description="Test internal comments RBAC",
            status="OPEN",
            created_by="tester"
        )
        db.add(ticket)
        db.commit()

        try:
            # Try to add internal note as employee (should fail)
            failed = False
            try:
                WorkflowService.add_comment(
                    db=db,
                    ticket_id=ticket_id,
                    author="tester",
                    text="Trying to post internal note as employee",
                    is_internal=True,
                    role="EMPLOYEE"
                )
                db.commit()
            except PermissionError:
                failed = True
                
            assert failed, "Should raise PermissionError when EMPLOYEE tries to post internal note"
            print("verify_internal_notes.py: SUCCESS")

        finally:
            from app.database.models.workflow_models import TicketComment, TicketTimeline
            db.query(TicketComment).filter(TicketComment.ticket_id == ticket_id).delete()
            db.query(TicketTimeline).filter(TicketTimeline.ticket_id == ticket_id).delete()
            db.query(Ticket).filter(Ticket.ticket_id == ticket_id).delete()
            db.commit()

if __name__ == "__main__":
    test_internal_notes_rbac()
