import os
import sys
import datetime

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.database.session import get_db
from app.database.models.ticket import Ticket
from app.services.workflow_service import WorkflowService

def test_ticket_aging():
    print("Running verify_ticket_aging...")
    now = datetime.datetime.utcnow()
    
    with get_db() as db:
        # Create tickets with historical created_at times to map to each aging bucket
        tickets_info = [
            ("TEST-AGE-001", now - datetime.timedelta(hours=2)),       # 0-4h
            ("TEST-AGE-002", now - datetime.timedelta(hours=6)),       # 4-8h
            ("TEST-AGE-003", now - datetime.timedelta(hours=12)),      # 8-24h
            ("TEST-AGE-004", now - datetime.timedelta(days=2)),         # 1-3d
            ("TEST-AGE-005", now - datetime.timedelta(days=5)),         # 3-7d
            ("TEST-AGE-006", now - datetime.timedelta(days=10)),        # 7d+
        ]
        
        tickets = []
        for tid, dt in tickets_info:
            t = Ticket(
                ticket_id=tid,
                category="GENERAL",
                description="Testing aging buckets",
                status="OPEN",
                created_at=dt,
                created_by="tester"
            )
            db.add(t)
            tickets.append(t)
            
        db.commit()

        try:
            metrics = WorkflowService.get_executive_metrics(db)
            
            buckets = metrics["aging_buckets"]
            assert buckets["0-4h"] >= 1, "Bucket 0-4h should have at least 1 ticket"
            assert buckets["4-8h"] >= 1, "Bucket 4-8h should have at least 1 ticket"
            assert buckets["8-24h"] >= 1, "Bucket 8-24h should have at least 1 ticket"
            assert buckets["1-3d"] >= 1, "Bucket 1-3d should have at least 1 ticket"
            assert buckets["3-7d"] >= 1, "Bucket 3-7d should have at least 1 ticket"
            assert buckets["7d+"] >= 1, "Bucket 7d+ should have at least 1 ticket"

            print("verify_ticket_aging.py: SUCCESS")

        finally:
            tids = [info[0] for info in tickets_info]
            db.query(Ticket).filter(Ticket.ticket_id.in_(tids)).delete(synchronize_session=False)
            db.commit()

if __name__ == "__main__":
    test_ticket_aging()
