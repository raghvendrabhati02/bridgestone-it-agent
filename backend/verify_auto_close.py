import os
import sys
import datetime

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Configure environment for immediate auto-close (0 minutes)
os.environ["AUTO_CLOSE_MINUTES"] = "0"

from app.database.session import get_db
from app.database.models.ticket import Ticket
from app.jobs.auto_close_job import run_auto_close_job

def test_auto_close():
    print("Running verify_auto_close...")
    with get_db() as db:
        ticket_id = "TEST-AC-001"
        
        # Create a ticket resolved 10 minutes ago
        ticket = Ticket(
            ticket_id=ticket_id,
            category="GENERAL",
            description="Testing auto-closure",
            status="RESOLVED",
            resolved_at=datetime.datetime.utcnow() - datetime.timedelta(minutes=10),
            created_by="tester"
        )
        db.add(ticket)
        db.commit()

        try:
            # Run background job
            run_auto_close_job()
            
            db.refresh(ticket)
            assert ticket.status == "CLOSED", f"Expected CLOSED, found {ticket.status}"
            assert ticket.closed_at is not None, "closed_at should be set"
            
            print("verify_auto_close.py: SUCCESS")

        finally:
            from app.database.models.workflow_models import TicketTimeline, KnowledgeDraft
            db.query(TicketTimeline).filter(TicketTimeline.ticket_id == ticket_id).delete()
            db.query(KnowledgeDraft).filter(KnowledgeDraft.source_ticket_id == ticket_id).delete()
            db.query(Ticket).filter(Ticket.ticket_id == ticket_id).delete()
            db.commit()

if __name__ == "__main__":
    test_auto_close()
