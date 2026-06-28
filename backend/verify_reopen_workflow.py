import os
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.database.session import get_db
from app.database.models.ticket import Ticket
from app.services.workflow_service import WorkflowService

def test_reopen_workflow():
    print("Running verify_reopen_workflow...")
    with get_db() as db:
        ticket_id = "TEST-REOPEN-001"
        ticket = Ticket(
            ticket_id=ticket_id,
            category="NETWORK",
            description="VPN dropouts",
            status="RESOLVED",
            resolved_at=None,
            created_by="tester"
        )
        db.add(ticket)
        db.commit()

        try:
            # Reopen ticket
            WorkflowService.reopen_ticket(
                db=db,
                ticket_id=ticket_id,
                reopened_by="tester",
                reason="Issue returned immediately."
            )
            db.commit()
            
            db.refresh(ticket)
            assert ticket.status == "IN_PROGRESS", "Reopened ticket status should be IN_PROGRESS"
            assert ticket.reopen_count == 1, f"Expected reopen_count=1, got {ticket.reopen_count}"
            assert ticket.reopened_by == "tester"
            assert ticket.reopen_reason == "Issue returned immediately."
            assert ticket.previous_resolution is not None, "Should back up previous status info"

            print("verify_reopen_workflow.py: SUCCESS")

        except Exception as e:
            print("Failed reopen assertion: ", e)
            raise e

        finally:
            from app.database.models.workflow_models import TicketTimeline
            db.query(TicketTimeline).filter(TicketTimeline.ticket_id == ticket_id).delete()
            db.query(Ticket).filter(Ticket.ticket_id == ticket_id).delete()
            db.commit()

if __name__ == "__main__":
    test_reopen_workflow()
