import logging
from sqlalchemy.orm import Session
from app.database.session import get_db
from app.database.repositories.security_event_repository import SecurityEventRepository

logger = logging.getLogger("it-agent-backend")

def log_security_event(event_type: str, username: str = None, details: str = None, db: Session = None):
    """
    Logs a security event to the database. Supports passing an existing db session,
    or creates one using get_db() if none is provided.
    """
    try:
        if db:
            repo = SecurityEventRepository(db)
            repo.save(event_type=event_type, username=username, details=details)
            logger.info("Security Service: Logged security event %s for %s", event_type, username)
        else:
            with get_db() as standalone_db:
                repo = SecurityEventRepository(standalone_db)
                repo.save(event_type=event_type, username=username, details=details)
                logger.info("Security Service: Logged security event %s for %s (standalone DB)", event_type, username)
    except Exception as e:
        logger.error("Security Service: Failed to log security event: %s", e)

def get_all_security_events() -> list:
    """
    Retrieves all security events.
    """
    try:
        with get_db() as db:
            repo = SecurityEventRepository(db)
            events = repo.get_all()
            return [
                {
                    "id": event.id,
                    "event_type": event.event_type,
                    "username": event.username,
                    "details": event.details,
                    "timestamp": event.created_at.isoformat() + "Z"
                }
                for event in events
            ]
    except Exception as e:
        logger.error("Security Service: Failed to fetch security events: %s", e)
        return []
