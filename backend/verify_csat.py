import os
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.database.session import get_db
from app.database.models.ticket import Ticket
from app.services.workflow_service import WorkflowService

def test_csat():
    print("Running verify_csat...")
    with get_db() as db:
        t1_id = "TEST-CSAT-001"
        t2_id = "TEST-CSAT-002"
        
        # t1 is CLOSED, t2 is OPEN
        t1 = Ticket(
            ticket_id=t1_id,
            category="VPN",
            description="CSAT on closed ticket",
            status="CLOSED",
            created_by="tester"
        )
        t2 = Ticket(
            ticket_id=t2_id,
            category="VPN",
            description="CSAT on open ticket",
            status="OPEN",
            created_by="tester"
        )
        db.add(t1)
        db.add(t2)
        db.commit()

        try:
            # 1. CSAT on CLOSED ticket
            survey = WorkflowService.submit_csat(
                db=db,
                ticket_id=t1_id,
                rating=5,
                feedback="Excellent work!",
                response_time_rating=4,
                resolution_quality_rating=5,
                would_recommend=True
            )
            db.commit()
            
            assert survey.rating == 5
            assert survey.feedback == "Excellent work!"

            # 2. CSAT on OPEN ticket (should fail)
            failed = False
            try:
                WorkflowService.submit_csat(
                    db=db,
                    ticket_id=t2_id,
                    rating=4
                )
                db.commit()
            except ValueError:
                failed = True
            
            assert failed, "Should raise ValueError when submitting CSAT for an open ticket"

            print("verify_csat.py: SUCCESS")

        finally:
            from app.database.models.workflow_models import CSATSurvey, TicketTimeline
            db.query(CSATSurvey).filter((CSATSurvey.ticket_id == t1_id) | (CSATSurvey.ticket_id == t2_id)).delete()
            db.query(TicketTimeline).filter((TicketTimeline.ticket_id == t1_id) | (TicketTimeline.ticket_id == t2_id)).delete()
            db.query(Ticket).filter((Ticket.ticket_id == t1_id) | (Ticket.ticket_id == t2_id)).delete()
            db.commit()

if __name__ == "__main__":
    test_csat()
