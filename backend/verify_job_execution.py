import sys
import os
import logging

# Bootstrap backend path
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _SCRIPT_DIR)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("verify_job_execution")

def main():
    print("\n" + "=" * 60)
    print("  VERIFY_JOB_EXECUTION: Job Function isolated execution tests")
    print("=" * 60)

    from app.jobs.sla_monitor_job import run_sla_monitor_job
    from app.jobs.notification_job import run_notification_job
    from app.jobs.cleanup_job import run_cleanup_job
    from app.jobs.scheduler import execute_job_wrapper
    from app.database.session import get_db
    from app.database.models.scheduled_job import JobExecutionHistory

    # Create dummy ticket & queued notification for job runs to have context
    print("\n[TEST 1] Creating mock data for job execution...")
    try:
        from app.database.models.ticket import Ticket
        from app.database.models.notification import Notification
        from datetime import datetime, timedelta

        with get_db() as db:
            # 1. Create a breached ticket
            ticket = Ticket(
                ticket_id="INC_JOB_BREACH_999",
                category="VPN",
                description="VPN test breach",
                issue_description="VPN test breach",
                status="OPEN",
                sla_hours=1,
                created_at=datetime.utcnow() - timedelta(hours=2)
            )
            # Remove existing if any
            db.query(Ticket).filter(Ticket.ticket_id == "INC_JOB_BREACH_999").delete()
            db.add(ticket)

            # 2. Create a queued notification
            notif = Notification(
                notification_id="NOTIF_QUEUED_999",
                ticket_id="INC_JOB_BREACH_999",
                recipient="employee",
                message="Test queued message",
                status="PENDING"
            )
            db.query(Notification).filter(Notification.notification_id == "NOTIF_QUEUED_999").delete()
            db.add(notif)
            
            db.commit()
            print("  [PASS] Mock data created successfully.")
    except Exception as e:
        print(f"  [FAIL] Failed to create mock data: {e}")
        sys.exit(1)

    # Execute jobs individually in isolation
    print("\n[TEST 2] Executing SLA Monitor Job function...")
    try:
        run_sla_monitor_job()
        print("  [PASS] run_sla_monitor_job completed without raising errors.")
    except Exception as e:
        print(f"  [FAIL] run_sla_monitor_job raised: {e}")
        sys.exit(1)

    print("\n[TEST 3] Executing Notification Job function...")
    try:
        run_notification_job()
        print("  [PASS] run_notification_job completed without raising errors.")
        
        # Verify notification status was changed to SENT
        with get_db() as db:
            n = db.query(Notification).filter(Notification.notification_id == "NOTIF_QUEUED_999").first()
            if n and n.status == "SENT":
                print("  [PASS] Queued notification transitioned status PENDING -> SENT.")
            else:
                print(f"  [FAIL] Notification status is: {n.status if n else 'None'}")
                sys.exit(1)
    except Exception as e:
        print(f"  [FAIL] run_notification_job raised: {e}")
        sys.exit(1)

    print("\n[TEST 4] Executing Cleanup Job function...")
    try:
        run_cleanup_job()
        print("  [PASS] run_cleanup_job completed without raising errors.")
    except Exception as e:
        print(f"  [FAIL] run_cleanup_job raised: {e}")
        sys.exit(1)

    # Execute via wrapped execution logs verification
    print("\n[TEST 5] Testing wrapper execution log logger...")
    try:
        # Delete old logs first
        with get_db() as db:
            db.query(JobExecutionHistory).filter(JobExecutionHistory.job_name == "sla_monitor_job").delete()
            db.commit()
            
        execute_job_wrapper("sla_monitor_job")
        
        with get_db() as db:
            logs = db.query(JobExecutionHistory).filter(JobExecutionHistory.job_name == "sla_monitor_job").all()
            if len(logs) > 0:
                print(f"  [PASS] Execution wrapper created {len(logs)} log history rows in DB.")
                print(f"         Status of log: {logs[0].status}, Started At: {logs[0].started_at}")
            else:
                print("  [FAIL] No execution log row created in DB.")
                sys.exit(1)
    except Exception as e:
        print(f"  [FAIL] Wrapper execution testing failed: {e}")
        sys.exit(1)

    print("\n" + "=" * 60)
    print("  ALL JOB EXECUTION TESTS PASSED ✅")
    print("=" * 60 + "\n")
    sys.exit(0)

if __name__ == "__main__":
    main()
