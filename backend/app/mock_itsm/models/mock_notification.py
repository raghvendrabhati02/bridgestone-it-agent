from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean
from app.database.base import Base

class MockNotification(Base):
    __tablename__ = "mock_notifications"

    id = Column(Integer, primary_key=True, index=True)
    notification_id = Column(String(50), unique=True, index=True, nullable=True)  # e.g., NOTIF0001
    ticket_id = Column(String(50), index=True, nullable=True)
    ticket_number = Column(String(50), index=True, nullable=True)
    user_id = Column(String(100), index=True, nullable=False)
    recipient = Column(String(100), nullable=False)
    recipient_role = Column(String(50), default="EMPLOYEE", nullable=False)  # EMPLOYEE, MANAGER, ENGINEER, ADMIN
    
    type = Column(String(50), default="INFO", nullable=False)  # Ticket Created, Ticket Assigned, Approval Requested, etc.
    title = Column(String(200), nullable=False)
    message = Column(Text, nullable=False)
    
    is_read = Column(Boolean, default=False, nullable=False, index=True)
    status = Column(String(50), default="SENT", nullable=False)  # SENT, READ
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    read_at = Column(DateTime, nullable=True)
