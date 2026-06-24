from sqlalchemy import Column, String, Integer, Boolean, DateTime, JSON
from datetime import datetime
from app.database.base import Base

class SessionModel(Base):
    __tablename__ = "sessions"

    session_id = Column(String(100), primary_key=True, index=True)
    category = Column(String(50), default="GENERAL")
    current_step = Column(Integer, default=0)
    status = Column(String(50), default="ACTIVE")
    approval_required = Column(Boolean, default=False)
    approval_status = Column(String(50), default="PENDING")
    recommended_action = Column(String(100), default="")
    action_result = Column(JSON, nullable=True)
    tool_result = Column(JSON, nullable=True)

    active_ticket = Column(String(100), nullable=True)
    active_issue = Column(String(100), nullable=True)
    active_request = Column(String(100), nullable=True)
    conversation_goal = Column(String(500), nullable=True)
    last_action = Column(String(100), nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
