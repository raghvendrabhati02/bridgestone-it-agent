from sqlalchemy import Column, Integer, String, Text, DateTime
from datetime import datetime
from app.database.base import Base

class Ticket(Base):
    __tablename__ = "tickets"

    id = Column(Integer, primary_key=True, index=True)
    ticket_id = Column(String(50), unique=True, index=True, nullable=False)
    category = Column(String(50), nullable=False)
    description = Column(Text, nullable=True)
    issue_description = Column(Text, nullable=True)
    assigned_team = Column(String(100), nullable=True)
    priority = Column(String(50), nullable=True)
    sla_hours = Column(Integer, nullable=True)
    status = Column(String(50), default="OPEN")
    servicenow_id = Column(String(100), nullable=True)
    created_by = Column(String(100), nullable=True)  # Username of the creator
    created_at = Column(DateTime, default=datetime.utcnow)

