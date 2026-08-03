from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean
from datetime import datetime
from app.database.base import Base

class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String(100), index=True, nullable=False)
    ticket_id = Column(String(50), index=True, nullable=True)
    type = Column(String(50), index=True, nullable=False)
    title = Column(String(255), nullable=False)
    message = Column(Text, nullable=False)
    is_read = Column(Boolean, default=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    read_at = Column(DateTime, nullable=True)

    # Legacy/compatibility columns
    recipient = Column(String(100), nullable=True)
    notification_id = Column(String(50), index=True, nullable=True)
    status = Column(String(50), default="SENT", nullable=True)
    correlation_id = Column(String(100), index=True, nullable=True)

