from sqlalchemy import Column, Integer, String, Text, DateTime, Float
from datetime import datetime
from app.database.base import Base

class ExecutionHistory(Base):
    __tablename__ = "execution_history"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)
    username = Column(String(100), nullable=False)
    device_id = Column(String(100), nullable=False)
    action_name = Column(String(100), nullable=False)
    result = Column(String(50), nullable=False)
    status = Column(String(50), default="Success", nullable=False) # Pending, Running, Success, Failed, Cancelled
    duration = Column(Float, nullable=False)
    logs = Column(Text, nullable=True)
    
    parameters = Column(Text, nullable=True) # JSON string
    started_at = Column(DateTime, default=datetime.utcnow, nullable=True)
    completed_at = Column(DateTime, default=datetime.utcnow, nullable=True)
    agent_version = Column(String(50), nullable=True)
    department = Column(String(100), nullable=True)
