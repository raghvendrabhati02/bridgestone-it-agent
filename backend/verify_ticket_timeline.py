import os
import sys
import uuid

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.database.session import get_db
from app.database.models.ticket import Ticket
from app.services.timeline_service import TimelineService
from app.services.workflow_service import WorkflowService
from app.services.ticket_lifecycle_service import transition
from app.core.logging_context import correlation_id_ctx

def test_ticket_timeline():
    print("Running verify_ticket_timeline...")
    
    # Set correlation ID context
    corr_id = f"corr-test-{uuid.uuid4().hex[:6]}"
    correlation_id_ctx.set(corr_id)

    with get_db() as db:
        ticket_id = "TEST-TL-001"
        ticket = Ticket(
            ticket_id=ticket_id,
            category="SOFTWARE",
            description="Timeline testing",
            status="OPEN",
            created_by="tester"
        )
        db.add(ticket)
        db.commit()

        try:
            # 1. Log a custom event
            TimelineService.log_event(
                db=db,
                ticket_id=ticket_id,
                event_type="TICKET_CREATED",
                actor="tester",
                action="created",
                description="Test ticket created."
            )
            db.commit()

            # 2. Assign ticket (should auto-log event)
            WorkflowService.assign_ticket(
                db=db,
                ticket_id=ticket_id,
                new_engineer="Alice Support",
                assigned_by="dispatcher",
                reason="Load balancing"
            )
            db.commit()

            # 3. Transition to IN_PROGRESS (should auto-log status change event)
            transition(ticket_id, "IN_PROGRESS", note="Starting diagnostics", session_id="session-test")
            db.commit()

            # 4. Fetch timeline
            events = TimelineService.get_timeline(db, ticket_id)
            
            # Assert events exist
            assert len(events) >= 3, f"Expected at least 3 events, found {len(events)}"
            
            # Assert correct order
            assert events[0].event_type == "TICKET_CREATED"
            assert "Alice Support" in events[1].description
            assert events[2].event_type == "STATUS_CHANGED"
            
            # Assert correlation ID propagated
            for e in events:
                if e.event_type == "TICKET_ASSIGNED":
                    assert e.correlation_id == corr_id, "Correlation ID should match contextvar value"
            
            print("verify_ticket_timeline.py: SUCCESS")

        finally:
            from app.database.models.workflow_models import TicketTimeline, AssignmentHistory
            db.query(TicketTimeline).filter(TicketTimeline.ticket_id == ticket_id).delete()
            db.query(AssignmentHistory).filter(AssignmentHistory.ticket_id == ticket_id).delete()
            db.query(Ticket).filter(Ticket.ticket_id == ticket_id).delete()
            db.commit()

if __name__ == "__main__":
    test_ticket_timeline()
