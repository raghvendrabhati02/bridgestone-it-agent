from sqlalchemy import Column, Integer, String, Text, DateTime
from datetime import datetime
from app.database.base import Base

class SecurityEvent(Base):
    __tablename__ = "security_events"

    id = Column(Integer, primary_key=True, index=True)
    event_type = Column(String(50), nullable=False)  # LOGIN, LOGOUT, FAILED_LOGIN, PERMISSION_DENIED, ROLE_CHANGE
    username = Column(String(100), nullable=True)
    details = Column(Text, nullable=True)
    correlation_id = Column(String(100), index=True, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
