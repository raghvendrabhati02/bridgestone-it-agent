from sqlalchemy import Column, Integer, String, Text, DateTime
from datetime import datetime
from app.database.base import Base

class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True)
    notification_id = Column(String(50), unique=True, index=True, nullable=False)
    ticket_id = Column(String(50), index=True, nullable=False)
    recipient = Column(String(100), nullable=False)
    message = Column(Text, nullable=False)
    status = Column(String(50), default="SENT")
    correlation_id = Column(String(100), index=True, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
