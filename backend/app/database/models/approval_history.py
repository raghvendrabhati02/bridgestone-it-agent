from sqlalchemy import Column, Integer, String, DateTime
from datetime import datetime
from app.database.base import Base

class ApprovalHistory(Base):
    __tablename__ = "approval_history"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String(100), index=True, nullable=False)
    recommended_action = Column(String(100), nullable=False)
    approval_status = Column(String(50), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
