from sqlalchemy import Column, Integer, String, Boolean, DateTime
from datetime import datetime
from app.database.base import Base

class ActionHistory(Base):
    __tablename__ = "action_history"

    id = Column(Integer, primary_key=True, index=True)
    request_id = Column(String(100), index=True, nullable=False)
    action_type = Column(String(100), nullable=False)
    status = Column(String(50), nullable=False)
    servicenow_id = Column(String(100), nullable=True)
    approved_by_user = Column(Boolean, default=False)
    correlation_id = Column(String(100), index=True, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
