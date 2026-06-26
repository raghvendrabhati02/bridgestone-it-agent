from sqlalchemy import Column, Integer, String, Text, DateTime, JSON
from datetime import datetime
from app.database.base import Base

class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String(100), index=True, nullable=False)
    user_message = Column(Text, nullable=True)
    category = Column(String(50), nullable=False)
    decision = Column(String(50), nullable=False)
    approval_status = Column(String(50), nullable=True)
    recommended_action = Column(String(100), nullable=True)
    action_result = Column(JSON, nullable=True)
    ticket_id = Column(String(100), nullable=True)
    servicenow_id = Column(String(100), nullable=True)
    correlation_id = Column(String(100), index=True, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
