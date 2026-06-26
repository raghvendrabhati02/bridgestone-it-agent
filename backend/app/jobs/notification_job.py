import logging
from datetime import datetime
from app.database.session import get_db
from app.database.models.notification import Notification

logger = logging.getLogger("it-agent-backend")

def run_notification_job():
    """
    Notification Job: Scans for any pending/queued notification records,
    simulates delivery to Email/Teams adapter pipelines, and marks them as SENT.
    """
    logger.info("Starting Notification Processing Job...")
    try:
        with get_db() as db:
            # Query for notifications that are in PENDING or QUEUED status
            pending_notifications = db.query(Notification).filter(Notification.status.in_(["PENDING", "QUEUED"])).all()
            logger.info("Notification Job: Found %d queued notifications to process.", len(pending_notifications))
            
            for notif in pending_notifications:
                logger.info(
                    "Processing notification %s: Recipient='%s', Message='%s'",
                    notif.notification_id, notif.recipient, notif.message
                )
                # Simulated delivery
                # In the future, this would integrate with SMTP/MS Teams webhook clients
                
                notif.status = "SENT"
                notif.created_at = datetime.utcnow()
                
            db.commit()
        logger.info("Notification Processing Job completed successfully.")
    except Exception as e:
        logger.error("Notification Processing Job failed: %s", e)
        raise e
