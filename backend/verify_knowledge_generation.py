import os
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.database.session import get_db
from app.database.models.ticket import Ticket
from app.services.knowledge_generation_service import KnowledgeGenerationService

def test_knowledge_generation():
    print("Running verify_knowledge_generation...")
    with get_db() as db:
        ticket_id = "TEST-KB-001"
        ticket = Ticket(
            ticket_id=ticket_id,
            category="SAP",
            description="SAP user lock due to multiple incorrect password attempts.",
            status="RESOLVED",
            previous_resolution="Unlocked account in Active Directory and reset SAP password.",
            created_by="tester"
        )
        db.add(ticket)
        db.commit()

        try:
            # Trigger KB draft generation
            draft = KnowledgeGenerationService.generate_draft_for_ticket(db, ticket_id)
            db.commit()
            
            assert draft is not None, "KB draft should be generated"
            assert draft.source_ticket_id == ticket_id
            assert len(draft.title) > 0
            
            # Reload from DB to verify persistence
            from app.database.models.workflow_models import KnowledgeDraft
            db_draft = db.query(KnowledgeDraft).filter(KnowledgeDraft.source_ticket_id == ticket_id).first()
            assert db_draft is not None
            assert db_draft.category == "SAP" or "SAP" in db_draft.title

            print("verify_knowledge_generation.py: SUCCESS")

        finally:
            from app.database.models.workflow_models import KnowledgeDraft, TicketTimeline
            db.query(KnowledgeDraft).filter(KnowledgeDraft.source_ticket_id == ticket_id).delete()
            db.query(TicketTimeline).filter(TicketTimeline.ticket_id == ticket_id).delete()
            db.query(Ticket).filter(Ticket.ticket_id == ticket_id).delete()
            db.commit()

if __name__ == "__main__":
    test_knowledge_generation()
