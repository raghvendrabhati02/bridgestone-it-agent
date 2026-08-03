from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, JSON
from app.database.base import Base

class MockAuditLog(Base):
    __tablename__ = "mock_audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    ticket_number = Column(String(50), index=True, nullable=True)
    event_type = Column(String(100), nullable=False)
    # Event Types: Ticket Created, Ticket Updated, Assignment Changed, Status Changed, Approval Granted, Approval Rejected, Comment Added, Resolution Added
    performed_by = Column(String(100), nullable=False)
    details = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
