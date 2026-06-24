from sqlalchemy.orm import Session
from app.database.models.security_event import SecurityEvent
from datetime import datetime

class SecurityEventRepository:
    def __init__(self, db: Session):
        self.db = db

    def save(self, event_type: str, username: str = None, details: str = None) -> SecurityEvent:
        event = SecurityEvent(
            event_type=event_type,
            username=username,
            details=details,
            created_at=datetime.utcnow()
        )
        self.db.add(event)
        self.db.commit()
        self.db.refresh(event)
        return event

    def get_all(self) -> list[SecurityEvent]:
        return self.db.query(SecurityEvent).order_by(SecurityEvent.id.asc()).all()
