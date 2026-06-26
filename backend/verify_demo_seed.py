import os
import sys

# Add app directory to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "app")))

from app.database.connection import SessionLocal
from app.database.models.user import User
from app.database.models.ticket import Ticket
from app.database.models.notification import Notification
from app.database.models.security_event import SecurityEvent
from app.database.models.rbac_audit_log import RbacAuditLog
from app.database.models.approval_history import ApprovalHistory
from app.database.models.action_history import ActionHistory
from app.database.models.scheduled_job import ScheduledJob, JobExecutionHistory
from app.services import analytics_service

def verify_seeding():
    print("=== Bridgestone Demo Seeding Verification ===")
    db = SessionLocal()
    
    # Track passes and failures
    failures = []
    
    def check(name, condition, message):
        if condition:
            print(f"  [PASS] {name}: {message}")
        else:
            print(f"  [FAIL] {name}: {message}")
            failures.append(name)

    try:
        # 1. Verify Users count
        users_count = db.query(User).count()
        check("User Count", users_count == 3, f"Expected 3 standard users, got {users_count}.")

        # 2. Verify Ticket counts
        tickets_count = db.query(Ticket).count()
        check("Ticket Count", tickets_count == 12, f"Expected 12 total tickets, got {tickets_count}.")

        # 3. Verify Active Tickets count
        active_statuses = ["OPEN", "ASSIGNED", "IN_PROGRESS", "WAITING_FOR_USER"]
        active_count = db.query(Ticket).filter(Ticket.status.in_(active_statuses)).count()
        check("Active Tickets Count", active_count == 8, f"Expected 8 active tickets, got {active_count}.")

        # 4. Verify Resolved/Closed Tickets count
        resolved_closed_statuses = ["RESOLVED", "CLOSED"]
        resolved_count = db.query(Ticket).filter(Ticket.status.in_(resolved_closed_statuses)).count()
        check("Resolved/Closed Tickets Count", resolved_count == 4, f"Expected 4 resolved/closed tickets, got {resolved_count}.")

        # 5. Verify Notifications count
        notif_count = db.query(Notification).count()
        check("Notification Count", notif_count >= 4, f"Expected at least 4 notifications, got {notif_count}.")

        # 6. Verify Approvals count
        approval_count = db.query(ApprovalHistory).count()
        check("Approval Count", approval_count in [4, 9], f"Expected 4 or 9 approval history entries, got {approval_count}.")
        
        # 7. Verify Executed Actions
        action_count = db.query(ActionHistory).count()
        check("Action History Count", action_count == 3, f"Expected 3 executed actions in ActionHistory, got {action_count}.")

        # 8. Verify Security events count
        security_count = db.query(SecurityEvent).count()
        check("Security Events Count", security_count == 4, f"Expected 4 security events, got {security_count}.")
        
        # 9. Verify RbacAuditLogs count (creation + assignments + resolution logs)
        rbac_logs_count = db.query(RbacAuditLog).count()
        check("RBAC Audit Logs Count", rbac_logs_count >= 24, f"Expected at least 24 RbacAuditLogs, got {rbac_logs_count}.")

        # 10. Verify Scheduled Jobs
        jobs_count = db.query(ScheduledJob).count()
        check("Scheduled Jobs Count", jobs_count >= 3, f"Expected at least 3 scheduled background jobs, got {jobs_count}.")

        print("\n=== Verifying Dashboard Calculations ===")
        
        # 11. Test Overview Calculations
        overview = analytics_service.get_overview_metrics(db)
        check("Dashboard: Total Tickets", overview["total_tickets"] == 12, f"Expected 12 total tickets, got {overview['total_tickets']}.")
        check("Dashboard: Open Tickets", overview["open_tickets"] == 8, f"Expected 8 open tickets, got {overview['open_tickets']}.")
        check("Dashboard: SLA Compliance %", overview["compliance_pct"] == 87.5, f"Expected 87.5% compliance, got {overview['compliance_pct']}%.")
        check("Dashboard: Avg Resolution Time", 1.2 <= overview["avg_resolution_hours"] <= 1.6, f"Expected avg resolution around ~1.4h, got {overview['avg_resolution_hours']}h.")

        # 12. Test SLA Calculations
        sla = analytics_service.get_sla_metrics(db)
        check("SLA Dashboard: Healthy count", sla["healthy"] == 5, f"Expected 5 healthy SLA active tickets, got {sla['healthy']}.")
        check("SLA Dashboard: Warning 75%", sla["warning_75"] == 1, f"Expected 1 warning 75% active tickets, got {sla['warning_75']}.")
        check("SLA Dashboard: Warning 90%", sla["warning_90"] == 1, f"Expected 1 warning 90% active tickets, got {sla['warning_90']}.")
        check("SLA Dashboard: Breached / Escalated", sla["breached"] == 0 and sla["escalated_l3"] == 1, f"Expected 1 escalated Level 3 active ticket, got breaches: {sla['breached']}, L3: {sla['escalated_l3']}.")
        check("SLA Dashboard: Avg First Response Time", 0.1 <= sla["avg_first_response_hours"] <= 0.3, f"Expected avg response time around ~0.2h, got {sla['avg_first_response_hours']}h.")

        print("\n" + "="*55)
        if len(failures) == 0:
            print("  ALL SEEDING VERIFICATION CHECKS PASSED [OK]")
            print("  DATABASE STATUS: EXECUTIVE DEMO READY")
        else:
            print(f"  VERIFICATION FAILED: {len(failures)} checks failed [ERROR]")
            for f in failures:
                print(f"    - {f}")
        print("="*55)
        
    finally:
        db.close()

if __name__ == "__main__":
    verify_seeding()
