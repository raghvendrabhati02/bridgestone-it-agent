import os
import sys

# Force UTF-8 output on Windows terminals
if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

# Inject mock before importing backend app
import mock_gemini

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "app")))

from app.database.connection import SessionLocal
from app.database.models.ticket import Ticket
from app.services import analytics_service

def verify_dashboard_updates():
    print("Running verify_dashboard_updates.py...")
    db = SessionLocal()
    failures = []

    def check(name, condition, msg):
        if condition:
            print(f"  [\u2705 PASS] {name}: {msg}")
        else:
            print(f"  [\u274c FAIL] {name}: {msg}")
            failures.append(name)

    try:
        # Get baseline metrics
        initial_metrics = analytics_service.get_overview_metrics(db)
        initial_total = initial_metrics.get("total_tickets", 0)
        initial_open = initial_metrics.get("open_tickets", 0)
        
        print(f"  Initial Total Tickets: {initial_total}")
        print(f"  Initial Open Tickets:  {initial_open}")
        
        # 1. Create a new ticket and verify counter increments
        new_ticket = Ticket(
            ticket_id="INC009999",
            category="Software",
            description="Testing dashboard metric increments",
            issue_description="Testing dashboard metric increments",
            priority="LOW",
            sla_hours=24,
            status="OPEN",
            created_by="employee"
        )
        db.add(new_ticket)
        db.commit()
        
        after_metrics = analytics_service.get_overview_metrics(db)
        after_total = after_metrics.get("total_tickets", 0)
        after_open = after_metrics.get("open_tickets", 0)
        
        print(f"  Metrics after ticket creation:")
        print(f"    Total: {after_total} (expected: {initial_total + 1})")
        print(f"    Open:  {after_open} (expected: {initial_open + 1})")
        
        check(
            "Total ticket counter incremented",
            after_total == initial_total + 1,
            "Total ticket counter did not increment after ticket creation."
        )
        check(
            "Open ticket counter incremented",
            after_open == initial_open + 1,
            "Open ticket counter did not increment after ticket creation."
        )
        
        # 2. Resolve the ticket and verify open counter decrements
        new_ticket.status = "RESOLVED"
        db.commit()
        
        resolved_metrics = analytics_service.get_overview_metrics(db)
        resolved_total = resolved_metrics.get("total_tickets", 0)
        resolved_open = resolved_metrics.get("open_tickets", 0)
        
        print(f"  Metrics after resolving ticket:")
        print(f"    Total: {resolved_total} (expected: {initial_total + 1})")
        print(f"    Open:  {resolved_open} (expected: {initial_open})")
        
        check(
            "Total ticket counter remained same",
            resolved_total == initial_total + 1,
            "Total ticket counter shifted unexpectedly."
        )
        check(
            "Open ticket counter decremented",
            resolved_open == initial_open,
            "Open ticket counter did not decrement after ticket resolution."
        )
        
        # Clean up the test ticket
        db.delete(new_ticket)
        db.commit()

    finally:
        db.close()

    if failures:
        print(f"[FAIL] verify_dashboard_updates.py failed with checks: {failures}")
        sys.exit(1)
    else:
        print("[PASS] verify_dashboard_updates.py successfully passed all checks!")
        sys.exit(0)

if __name__ == "__main__":
    verify_dashboard_updates()
