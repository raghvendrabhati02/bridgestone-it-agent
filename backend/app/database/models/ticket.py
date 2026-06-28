from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean
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
    # ── SLA Escalation Engine fields ──────────────────────────────────────────
    sla_state = Column(String(50), nullable=True, default="HEALTHY")  # SLA state enum string
    sla_breached = Column(Boolean, nullable=True, default=False)      # True once SLA is breached
    sla_breached_at = Column(DateTime, nullable=True)                 # UTC timestamp of first breach

    # ServiceNow Operational Workflow fields
    assigned_engineer = Column(String(100), nullable=True)
    waiting_since = Column(DateTime, nullable=True)
    waiting_duration_sec = Column(Integer, default=0)
    reminders_sent = Column(Integer, default=0)
    last_customer_response_at = Column(DateTime, nullable=True)
    resolved_at = Column(DateTime, nullable=True)
    closed_at = Column(DateTime, nullable=True)
    reopen_count = Column(Integer, default=0)
    reopened_by = Column(String(100), nullable=True)
    reopened_at = Column(DateTime, nullable=True)
    reopen_reason = Column(Text, nullable=True)
    previous_resolution = Column(Text, nullable=True)
    cluster_id = Column(Integer, nullable=True)


