import sys
import os
import logging

# Bootstrap backend path
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _SCRIPT_DIR)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("verify_scheduler")

def main():
    print("\n" + "=" * 60)
    print("  VERIFY_SCHEDULER: Core Scheduler Lifecycle Tests")
    print("=" * 60)

    import app.jobs.scheduler as scheduler
    from app.database.session import get_db
    from app.database.models.scheduled_job import ScheduledJob

    # Initialize scheduler
    print("\n[TEST 1] Initializing background scheduler...")
    try:
        scheduler.init_scheduler()
    except Exception as e:
        print(f"  [FAIL] Failed to initialize scheduler: {e}")
        sys.exit(1)

    # Check running state
    is_running = scheduler.scheduler_instance is not None and scheduler.scheduler_instance.running
    if is_running:
        print("  [PASS] Scheduler is running.")
    else:
        print("  [FAIL] Scheduler is not running.")
        sys.exit(1)

    # Verify jobs scheduled in memory
    print("\n[TEST 2] Verifying jobs scheduled in APScheduler memory...")
    expected_jobs = ["sla_monitor_job", "notification_job", "cleanup_job"]
    for jname in expected_jobs:
        job = scheduler.scheduler_instance.get_job(jname)
        if job:
            print(f"  [PASS] Found job '{jname}' in active scheduler memory.")
        else:
            print(f"  [FAIL] Job '{jname}' missing in active scheduler memory.")
            scheduler.shutdown_scheduler()
            sys.exit(1)

    # Verify DB seeding
    print("\n[TEST 3] Verifying jobs seeded in database...")
    try:
        with get_db() as db:
            jobs = db.query(ScheduledJob).all()
            db_job_names = [j.job_name for j in jobs]
            print(f"  Info: Jobs found in DB: {db_job_names}")
            for jname in expected_jobs:
                if jname in db_job_names:
                    print(f"  [PASS] Found job '{jname}' seeded in DB.")
                else:
                    print(f"  [FAIL] Job '{jname}' not found in DB.")
                    scheduler.shutdown_scheduler()
                    sys.exit(1)
    except Exception as e:
        print(f"  [FAIL] Failed to query DB: {e}")
        scheduler.shutdown_scheduler()
        sys.exit(1)

    # Shutdown
    print("\n[TEST 4] Shutting down scheduler...")
    try:
        scheduler.shutdown_scheduler()
        if scheduler.scheduler_instance is None:
            print("  [PASS] Scheduler successfully terminated.")
        else:
            print("  [FAIL] Scheduler instance still exists.")
            sys.exit(1)
    except Exception as e:
        print(f"  [FAIL] Error during shutdown: {e}")
        sys.exit(1)

    print("\n" + "=" * 60)
    print("  ALL CORE SCHEDULER LIFECYCLE TESTS PASSED ✅")
    print("=" * 60 + "\n")
    sys.exit(0)

if __name__ == "__main__":
    main()
