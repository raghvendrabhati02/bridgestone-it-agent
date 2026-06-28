import os
import sys

# Add backend directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.database.session import get_db
from app.database.models.ticket import Ticket
from app.services.workflow_service import WorkflowService

def test_comments():
    print("Running verify_comments...")
    with get_db() as db:
        # Create a test ticket
        ticket_id = "TEST-TC-001"
        ticket = Ticket(
            ticket_id=ticket_id,
            category="GENERAL",
            description="Test comment handling",
            status="OPEN",
            created_by="tester"
        )
        db.add(ticket)
        db.commit()

        try:
            # 1. Post a customer comment
            c1 = WorkflowService.add_comment(
                db=db,
                ticket_id=ticket_id,
                author="tester",
                text="Hello, this is a customer comment.",
                is_internal=False,
                role="EMPLOYEE"
            )
            
            # 2. Post an internal work note as SUPPORT
            c2 = WorkflowService.add_comment(
                db=db,
                ticket_id=ticket_id,
                author="support_agent",
                text="This is an internal note.",
                is_internal=True,
                role="SUPPORT"
            )
            db.commit()

            # 3. Retrieve comments as EMPLOYEE
            employee_comments = WorkflowService.get_comments(db, ticket_id, "EMPLOYEE")
            assert len(employee_comments) == 1, "Employee should only see 1 comment"
            assert employee_comments[0].is_internal is False, "Employee should not see internal notes"

            # 4. Retrieve comments as SUPPORT
            support_comments = WorkflowService.get_comments(db, ticket_id, "SUPPORT")
            assert len(support_comments) == 2, "Support agent should see both comments"

            # 5. Try to edit comment
            WorkflowService.edit_comment(
                db=db,
                comment_id=c1.id,
                author="tester",
                new_text="Edited comment text",
                role="EMPLOYEE"
            )
            db.commit()

            edited = WorkflowService.get_comments(db, ticket_id, "EMPLOYEE")
            assert edited[0].text == "Edited comment text", "Comment text should be updated"
            assert "Edited comment text" in edited[0].text

            print("verify_comments.py: SUCCESS")

        finally:
            # Cleanup comments
            from app.database.models.workflow_models import TicketComment, TicketTimeline
            db.query(TicketComment).filter(TicketComment.ticket_id == ticket_id).delete()
            db.query(TicketTimeline).filter(TicketTimeline.ticket_id == ticket_id).delete()
            db.query(Ticket).filter(Ticket.ticket_id == ticket_id).delete()
            db.commit()

if __name__ == "__main__":
    test_comments()
