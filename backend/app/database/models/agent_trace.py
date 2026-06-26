from sqlalchemy import Column, Integer, String, DateTime, JSON
from datetime import datetime
from app.database.base import Base

class AgentTrace(Base):
    __tablename__ = "agent_traces"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String(100), index=True, nullable=False)
    agent_name = Column(String(100), nullable=False)
    input_data = Column(JSON, nullable=True)
    output_data = Column(JSON, nullable=True)
    correlation_id = Column(String(100), index=True, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
