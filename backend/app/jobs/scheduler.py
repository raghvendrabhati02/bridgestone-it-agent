import logging
from datetime import datetime, timezone
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger

from app.database.session import get_db
from app.database.models.scheduled_job import ScheduledJob, JobExecutionHistory
from app.jobs.sla_monitor_job import run_sla_monitor_job
from app.jobs.notification_job import run_notification_job
from app.jobs.cleanup_job import run_cleanup_job

logger = logging.getLogger("it-agent-backend")

# Active BackgroundScheduler instance
scheduler_instance = None

# Registry of python functions mapped to job names
JOB_FUNCTIONS = {
    "sla_monitor_job": run_sla_monitor_job,
    "notification_job": run_notification_job,
    "cleanup_job": run_cleanup_job,
}

# Default configurations for startup registration seeding
DEFAULT_JOBS = [
    {
        "job_name": "sla_monitor_job",
        "job_type": "interval",
        "interval_seconds": 60,
        "cron_expression": None,
        "is_enabled": True
    },
    {
        "job_name": "notification_job",
        "job_type": "interval",
        "interval_seconds": 30,
        "cron_expression": None,
        "is_enabled": True
    },
    {
        "job_name": "cleanup_job",
        "job_type": "cron",
        "interval_seconds": None,
        "cron_expression": "0 0 * * *",  # runs at midnight every day
        "is_enabled": True
    }
]

def run_database_migrations():
    """Adds missing SLA and observability columns to tables if they don't exist."""
    try:
        from sqlalchemy import inspect, text
        from app.database.connection import engine
        inspector = inspect(engine)
        
        # 1. Tickets SLA Migrations
        if "tickets" in inspector.get_table_names():
            columns = [col['name'] for col in inspector.get_columns('tickets')]
            with engine.begin() as conn:
                if 'sla_state' not in columns:
                    logger.info("Migration: Adding column 'sla_state' to table 'tickets'")
                    conn.execute(text("ALTER TABLE tickets ADD COLUMN sla_state VARCHAR(50) DEFAULT 'HEALTHY'"))
                if 'sla_breached' not in columns:
                    logger.info("Migration: Adding column 'sla_breached' to table 'tickets'")
                    conn.execute(text("ALTER TABLE tickets ADD COLUMN sla_breached BOOLEAN DEFAULT 0"))
                if 'sla_breached_at' not in columns:
                    logger.info("Migration: Adding column 'sla_breached_at' to table 'tickets'")
                    conn.execute(text("ALTER TABLE tickets ADD COLUMN sla_breached_at TIMESTAMP"))
                    
        # 2. Observability correlation ID migrations
        observability_tables = {
            "audit_logs": "correlation_id",
            "agent_traces": "correlation_id",
            "notifications": "correlation_id",
            "action_history": "correlation_id",
            "security_events": "correlation_id",
            "job_execution_history": "correlation_id",
            "approval_history": "correlation_id"
        }
        
        table_names = inspector.get_table_names()
        for tbl, col in observability_tables.items():
            if tbl in table_names:
                columns = [c['name'] for c in inspector.get_columns(tbl)]
                if col not in columns:
                    logger.info("Migration: Adding column '%s' to table '%s'", col, tbl)
                    with engine.begin() as conn:
                        conn.execute(text(f"ALTER TABLE {tbl} ADD COLUMN {col} VARCHAR(100)"))
                        
        logger.info("Migration: Database migrations checked.")
    except Exception as e:
        logger.error("Migration: Database migrations failed: %s", e)

def init_scheduler():
    """
    Initializes and starts the background scheduler. Seeding default jobs,
    loading active ones, and scheduling them into the running instance.
    """
    global scheduler_instance
    if scheduler_instance is not None:
        logger.warning("Scheduler is already initialized.")
        return

    logger.info("Initializing Background Job Scheduler...")
    
    # 0. Ensure database tables exist
    try:
        from app.database.connection import engine
        from app.database.base import Base
        Base.metadata.create_all(bind=engine)
        logger.info("Scheduler: Database tables verified/created.")
        run_database_migrations()
    except Exception as e:
        logger.error("Scheduler: Failed to verify database tables: %s", e)

    # 1. Ensure default jobs are seeded in database
    seed_jobs_db()

    # 2. Start APScheduler BackgroundScheduler
    scheduler_instance = BackgroundScheduler(timezone="UTC")

    # 3. Load all enabled jobs from DB and schedule them
    try:
        with get_db() as db:
            active_jobs = db.query(ScheduledJob).filter(ScheduledJob.is_enabled == True).all()
            for job in active_jobs:
                schedule_job_in_scheduler(job)
    except Exception as e:
        logger.error("Scheduler init: Failed to load and schedule jobs from DB: %s", e)

    # 4. Start scheduler
    scheduler_instance.start()
    logger.info("Background Job Scheduler started successfully. Running status: %s", scheduler_instance.running)
    
    # Update next run times in DB immediately after start
    sync_next_run_times()

def shutdown_scheduler():
    """Shuts down the running scheduler instance."""
    global scheduler_instance
    if scheduler_instance:
        logger.info("Shutting down Background Job Scheduler...")
        scheduler_instance.shutdown(wait=False)
        scheduler_instance = None
        logger.info("Background Job Scheduler shut down successfully.")

def seed_jobs_db():
    """Seeds default job configs into database if they do not exist."""
    try:
        with get_db() as db:
            for dj in DEFAULT_JOBS:
                existing = db.query(ScheduledJob).filter(ScheduledJob.job_name == dj["job_name"]).first()
                if not existing:
                    job = ScheduledJob(
                        job_name=dj["job_name"],
                        job_type=dj["job_type"],
                        interval_seconds=dj["interval_seconds"],
                        cron_expression=dj["cron_expression"],
                        is_enabled=dj["is_enabled"]
                    )
                    db.add(job)
                    logger.info("Scheduler Seed: Created default config for '%s'", dj["job_name"])
            db.commit()
    except Exception as e:
        logger.error("Scheduler: Failed to seed default jobs in DB: %s", e)

def schedule_job_in_scheduler(job_record: ScheduledJob):
    """Adds or replaces a job in the active scheduler instance."""
    global scheduler_instance
    if not scheduler_instance:
        return

    job_name = job_record.job_name
    if job_name not in JOB_FUNCTIONS:
        logger.warning("Scheduler: Job function '%s' not registered. Skipping scheduling.", job_name)
        return

    # Remove existing to prevent duplication
    if scheduler_instance.get_job(job_name):
        scheduler_instance.remove_job(job_name)

    # Build Trigger
    trigger = None
    if job_record.job_type == "interval":
        trigger = IntervalTrigger(seconds=job_record.interval_seconds, timezone="UTC")
    elif job_record.job_type == "cron":
        trigger = CronTrigger.from_crontab(job_record.cron_expression, timezone="UTC")
    else:
        logger.error("Scheduler: Unknown job trigger type '%s' for job '%s'", job_record.job_type, job_name)
        return

    # Add wrapped execution job
    scheduler_instance.add_job(
        func=execute_job_wrapper,
        args=[job_name],
        trigger=trigger,
        id=job_name,
        replace_existing=True
    )
    logger.info("Scheduler: Scheduled job '%s' (%s trigger)", job_name, job_record.job_type)

def execute_job_wrapper(job_name: str):
    """
    Wrapper around job execution to log status, start/end timestamps,
    success/failure states, error messages, and next execution target times.
    """
    import uuid
    from app.core.logging_context import (
        clear_logging_context,
        request_id_ctx,
        correlation_id_ctx,
        session_id_ctx,
        user_ctx,
        role_ctx,
        error_stack_ctx
    )
    
    clear_logging_context()
    req_id = f"req-job-{uuid.uuid4().hex[:8]}"
    corr_id = f"corr-job-{uuid.uuid4().hex[:8]}"
    
    request_id_ctx.set(req_id)
    correlation_id_ctx.set(corr_id)
    session_id_ctx.set(f"session-job-{job_name}")
    user_ctx.set("system")
    role_ctx.set("SYSTEM")

    started_at = datetime.utcnow()
    logger.info("Scheduler: starting execution wrapper for job '%s'", job_name)
    
    # 1. Log start in JobExecutionHistory
    db_history_id = None
    try:
        with get_db() as db:
            hist = JobExecutionHistory(
                job_name=job_name,
                status="RUNNING",
                started_at=started_at,
                correlation_id=corr_id
            )
            db.add(hist)
            db.commit()
            db.refresh(hist)
            db_history_id = hist.id
    except Exception as e:
        logger.error("Scheduler: Failed to write job start log to history: %s", e)

    # 2. Resolve and execute actual job function
    func = JOB_FUNCTIONS.get(job_name)
    status = "SUCCESS"
    err_msg = None
    
    if not func:
        status = "FAILED"
        err_msg = f"Job function '{job_name}' is not registered in JOB_FUNCTIONS."
        logger.error("Scheduler: %s", err_msg)
    else:
        try:
            func()
        except Exception as exc:
            status = "FAILED"
            import traceback
            err_msg = str(exc)
            error_stack_ctx.set(traceback.format_exc())
            logger.error("Scheduler: Job '%s' failed with exception: %s", job_name, err_msg)

    # 3. Log completion/failure in history and update next execution targets
    completed_at = datetime.utcnow()
    try:
        with get_db() as db:
            # Update history row
            if db_history_id:
                hist = db.query(JobExecutionHistory).filter(JobExecutionHistory.id == db_history_id).first()
                if hist:
                    hist.status = status
                    hist.completed_at = completed_at
                    hist.error_message = err_msg
                    hist.correlation_id = corr_id
            else:
                hist = JobExecutionHistory(
                    job_name=job_name,
                    status=status,
                    started_at=started_at,
                    completed_at=completed_at,
                    error_message=err_msg,
                    correlation_id=corr_id
                )
                db.add(hist)
            
            # Update ScheduledJob execution statistics
            job_record = db.query(ScheduledJob).filter(ScheduledJob.job_name == job_name).first()
            if job_record:
                job_record.last_run_time = completed_at
                
                # Retrieve next run time from scheduler
                next_run = None
                if scheduler_instance:
                    act_job = scheduler_instance.get_job(job_name)
                    if act_job and act_job.next_run_time:
                        next_run = act_job.next_run_time.replace(tzinfo=None)
                job_record.next_run_time = next_run
                
            db.commit()
            logger.info("Scheduler: wrapped job '%s' finished with status=%s", job_name, status)
    except Exception as e:
        logger.error("Scheduler: Failed to finalize job execution metadata in DB: %s", e)
    finally:
        clear_logging_context()

def sync_next_run_times():
    """Syncs DB job next_run_time fields with the active scheduler scheduler_instance."""
    global scheduler_instance
    if not scheduler_instance:
        return
    try:
        with get_db() as db:
            jobs = db.query(ScheduledJob).all()
            for job_record in jobs:
                act_job = scheduler_instance.get_job(job_record.job_name)
                if act_job and act_job.next_run_time:
                    job_record.next_run_time = act_job.next_run_time.replace(tzinfo=None)
                else:
                    job_record.next_run_time = None
            db.commit()
    except Exception as e:
        logger.error("Scheduler: Failed to sync next run times: %s", e)

def execute_job_manually(job_name: str) -> bool:
    """Executes a job synchronously in the background (or foreground) immediately."""
    if job_name not in JOB_FUNCTIONS:
        return False
    
    # Run the wrapper logic directly (writes execution logs to history in-place)
    execute_job_wrapper(job_name)
    return True
