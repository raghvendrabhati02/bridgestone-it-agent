from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime
from app.database.base import Base

class MockTicketHistory(Base):
    __tablename__ = "mock_ticket_history"

    id = Column(Integer, primary_key=True, index=True)
    ticket_number = Column(String(50), index=True, nullable=False)
    changed_by = Column(String(100), nullable=False)
    field_changed = Column(String(50), nullable=False)
    old_value = Column(Text, nullable=True)
    new_value = Column(Text, nullable=True)
    change_reason = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
