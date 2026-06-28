import os
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.database.session import get_db
from app.database.models.ticket import Ticket
from app.services.workflow_service import WorkflowService

def test_duplicate_detection():
    print("Running verify_duplicate_detection...")
    with get_db() as db:
        t1_id = "TEST-DUP-001"
        t2_id = "TEST-DUP-002"
        
        t1 = Ticket(
            ticket_id=t1_id,
            category="VPN",
            description="Unable to connect to the corporate VPN gateway from home office.",
            status="OPEN",
            created_by="tester1"
        )
        t2 = Ticket(
            ticket_id=t2_id,
            category="VPN",
            description="Unable to connect to corporate VPN from home network.",
            status="OPEN",
            created_by="tester2"
        )
        db.add(t1)
        db.add(t2)
        db.commit()

        try:
            # Check duplicates for a similar description
            dups = WorkflowService.check_duplicate(
                db=db,
                description="Unable to connect to corporate VPN gateway"
            )
            
            assert len(dups) >= 2, "Should find at least 2 similar tickets"
            
            # Verify similarity metric works
            best_match = dups[0]
            assert best_match["similarity"] >= 0.6, "Similarity should be above threshold"
            
            # Confirm duplicate link
            WorkflowService.confirm_duplicate(db, source_id=t2_id, target_id=t1_id)
            db.commit()
            
            # Reload and verify source ticket is resolved
            db.refresh(t2)
            assert t2.status == "RESOLVED", "Source ticket should be RESOLVED after confirming duplicate"
            
            print("verify_duplicate_detection.py: SUCCESS")

        finally:
            from app.database.models.workflow_models import DuplicateRelationship, TicketTimeline
            db.query(DuplicateRelationship).filter(
                (DuplicateRelationship.source_ticket_id == t2_id) | (DuplicateRelationship.source_ticket_id == t1_id)
            ).delete()
            db.query(TicketTimeline).filter(
                (TicketTimeline.ticket_id == t1_id) | (TicketTimeline.ticket_id == t2_id)
            ).delete()
            db.query(Ticket).filter(
                (Ticket.ticket_id == t1_id) | (Ticket.ticket_id == t2_id)
            ).delete()
            db.commit()

if __name__ == "__main__":
    test_duplicate_detection()
