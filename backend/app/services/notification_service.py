import datetime
import logging
from app.database.session import get_db
from app.database.repositories.ticket_repository import TicketRepository
from app.core.retry_helper import with_retry

logger = logging.getLogger("it-agent-backend")

# Volatile fallback list
notifications = []
notification_counter = 0

def init_notification_counter():
    """Initializes notification counter from DB."""
    global notification_counter
    try:
        with get_db() as db:
            repo = TicketRepository(db)
            all_n = repo.get_all_notifications()
            max_num = 0
            for n in all_n:
                try:
                    num = int(n.notification_id[5:])
                    if num > max_num:
                        max_num = num
                except Exception:
                    pass
            notification_counter = max_num
            logger.info("Notification Service: Initialized notification counter to %d from DB", notification_counter)
    except Exception as e:
        logger.warning("Notification Service: Failed to initialize notification counter from database: %s", e)

# Run initialization once at import time
init_notification_counter()

@with_retry(retries=3, backoff_factor=2.0)
def create_notification(ticket_id: str, recipient: str, message: str) -> dict:
    """
    Notification Agent: Creates a notification record associated with a ticket,
    stores it in database, and returns the details.
    """
    global notification_counter
    notification_counter += 1
    
    notification_id = f"NOTIF{notification_counter:04d}"
    timestamp = datetime.datetime.utcnow().isoformat() + "Z"
    
    try:
        from app.core.metrics import BUSINESS_NOTIFICATIONS_SENT_TOTAL
        BUSINESS_NOTIFICATIONS_SENT_TOTAL.inc()
    except Exception:
        pass
    
    notif = {
        "notification_id": notification_id,
        "ticket_id": ticket_id,
        "recipient": recipient,
        "message": message,
        "status": "SENT",
        "timestamp": timestamp
    }
    
    # Save to Database via TicketRepository
    try:
        with get_db() as db:
            repo = TicketRepository(db)
            db_notif = repo.save_notification(
                notification_id=notification_id,
                ticket_id=ticket_id,
                recipient=recipient,
                message=message,
                status="SENT"
            )
            logger.info("Notification Service: Persisted notification %s to database", notification_id)
            notif = {
                "notification_id": db_notif.notification_id,
                "ticket_id": db_notif.ticket_id,
                "recipient": db_notif.recipient,
                "message": db_notif.message,
                "status": db_notif.status,
                "timestamp": db_notif.created_at.isoformat() + "Z"
            }
    except Exception as e:
        logger.error("Notification Service: Failed to persist notification to database: %s", e)
        # Fallback to volatile memory list
        notifications.append(notif)
        
    logger.info("Notification Service: Notification %s sent to '%s'", notification_id, recipient)
    return notif

def get_all_notifications() -> list[dict]:
    """
    Returns the list of all created notifications.
    """
    try:
        with get_db() as db:
            repo = TicketRepository(db)
            db_notifs = repo.get_all_notifications()
            return [
                {
                    "notification_id": n.notification_id,
                    "ticket_id": n.ticket_id,
                    "recipient": n.recipient,
                    "message": n.message,
                    "status": n.status,
                    "timestamp": n.created_at.isoformat() + "Z"
                }
                for n in db_notifs
            ]
    except Exception as e:
        logger.error("Notification Service: Failed to get notifications from DB: %s", e)
        return notifications

def get_notifications() -> list[dict]:
    """
    Notification Agent: Returns the list of all created notifications.
    """
    return get_all_notifications()
