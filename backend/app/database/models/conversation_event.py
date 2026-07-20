from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean
from datetime import datetime
from app.database.base import Base

class ConversationEvent(Base):
    __tablename__ = "conversation_events"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String(100), index=True, nullable=False)
    conversation_id = Column(String(100), index=True, nullable=False)
    event_name = Column(String(100), nullable=False)
    username = Column(String(100), nullable=True)
    user_role = Column(String(100), nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    intent = Column(String(100), nullable=True)
    category = Column(String(100), nullable=True)
    phase = Column(String(100), nullable=True)
    clarifying_questions_asked = Column(Integer, default=0)
    troubleshooting_steps_suggested = Column(Integer, default=0)
    escalation_reason = Column(String(100), nullable=True)
    escalation_blocked = Column(Boolean, nullable=True)
    ticket_id = Column(String(100), nullable=True)
    response_latency = Column(Float, default=0.0)
    llm_confidence = Column(Float, default=0.0)
    model_name = Column(String(100), nullable=True)
