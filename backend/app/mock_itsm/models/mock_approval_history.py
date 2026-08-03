from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime
from app.database.base import Base

class MockApprovalHistory(Base):
    __tablename__ = "mock_approval_history"

    id = Column(Integer, primary_key=True, index=True)
    approval_id = Column(Integer, index=True, nullable=False)
    ticket_number = Column(String(50), index=True, nullable=False)
    performed_by = Column(String(100), nullable=False)
    action = Column(String(50), nullable=False)  # CREATED, VIEWED, APPROVED, REJECTED, EXPIRED, CANCELLED
    old_status = Column(String(50), nullable=True)
    new_status = Column(String(50), nullable=False)
    comments = Column(Text, nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)
