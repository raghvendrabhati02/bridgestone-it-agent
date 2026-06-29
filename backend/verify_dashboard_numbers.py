import os
import sys

# Force UTF-8 output on Windows terminals
if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "app")))

from app.database.connection import SessionLocal
from app.database.models.ticket import Ticket
from app.services import analytics_service

def verify_dashboard_numbers():
    print("Running verify_dashboard_numbers.py...")
    db = SessionLocal()
    failures = []

    def check(name, condition, msg):
        if condition:
            print(f"  [\u2705 PASS] {name}: {msg}")
        else:
            print(f"  [\u274c FAIL] {name}: {msg}")
            failures.append(name)

    try:
        overview = analytics_service.get_overview_metrics(db)
        
        # 1. Total count checks from overview dictionary
        total_tickets = overview.get("total_tickets", 0)
        open_tickets = overview.get("open_tickets", 0)
        
        check(
            "Overview total count non-negative",
            total_tickets >= 0,
            f"Total tickets negative or missing: {total_tickets}"
        )
        check(
            "Overview open count non-negative",
            open_tickets >= 0,
            f"Open tickets negative: {open_tickets}"
        )
        
        # Query database directly for resolved/closed count
        resolved_tickets_count = db.query(Ticket).filter(Ticket.status.in_(["RESOLVED", "CLOSED"])).count()
        check(
            "Resolved count non-negative",
            resolved_tickets_count >= 0,
            f"Resolved tickets count negative: {resolved_tickets_count}"
        )
        
        # 2. Consistent mathematical totals
        total_calc = open_tickets + resolved_tickets_count
        check(
            "Ticket counts sum consistency",
            total_calc == total_tickets,
            f"Open ({open_tickets}) + Resolved ({resolved_tickets_count}) = {total_calc}, but Total = {total_tickets}"
        )
        
        # 3. Compliance percentages limits
        comp_pct = overview.get("compliance_pct", -1)
        check(
            "SLA Compliance within bounds",
            0 <= comp_pct <= 100,
            f"SLA Compliance percentage out of bounds: {comp_pct}%"
        )
        
        # 4. SLA engine status metrics
        sla = analytics_service.get_sla_metrics(db)
        check(
            "SLA dashboardhealthy count non-negative",
            sla.get("healthy", -1) >= 0,
            f"Healthy count negative: {sla.get('healthy')}"
        )
        check(
            "SLA warning_75 count non-negative",
            sla.get("warning_75", -1) >= 0,
            f"Warning 75 count negative: {sla.get('warning_75')}"
        )
        check(
            "SLA warning_90 count non-negative",
            sla.get("warning_90", -1) >= 0,
            f"Warning 90 count negative: {sla.get('warning_90')}"
        )
        check(
            "SLA breached count non-negative",
            sla.get("breached", -1) >= 0,
            f"Breached count negative: {sla.get('breached')}"
        )

    finally:
        db.close()

    if failures:
        print(f"[FAIL] verify_dashboard_numbers.py failed with checks: {failures}")
        sys.exit(1)
    else:
        print("[PASS] verify_dashboard_numbers.py successfully passed all checks!")
        sys.exit(0)

if __name__ == "__main__":
    verify_dashboard_numbers()
