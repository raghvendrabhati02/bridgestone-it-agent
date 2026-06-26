import logging
from datetime import datetime, timedelta
from app.database.session import get_db
from app.database.models.scheduled_job import JobExecutionHistory
from app.database.models.agent_trace import AgentTrace

logger = logging.getLogger("it-agent-backend")

def run_cleanup_job():
    """
    Cleanup Job: Purges execution history logs older than 7 days and
    agent trace records older than 30 days to keep DB storage optimized.
    """
    logger.info("Starting Log Cleanup Job...")
    try:
        now = datetime.utcnow()
        history_cutoff = now - timedelta(days=7)
        trace_cutoff = now - timedelta(days=30)
        
        with get_db() as db:
            # Delete old job history
            deleted_histories = db.query(JobExecutionHistory).filter(JobExecutionHistory.started_at < history_cutoff).delete()
            # Delete old agent traces
            deleted_traces = db.query(AgentTrace).filter(AgentTrace.created_at < trace_cutoff).delete()
            
            db.commit()
            logger.info("Cleanup Job: Purged %d old execution history rows.", deleted_histories)
            logger.info("Cleanup Job: Purged %d old agent trace rows.", deleted_traces)
            
        logger.info("Log Cleanup Job completed successfully.")
    except Exception as e:
        logger.error("Log Cleanup Job failed: %s", e)
        raise e
