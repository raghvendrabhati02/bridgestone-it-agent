from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean
from datetime import datetime
from enum import Enum
from app.database.base import Base

class TicketState(str, Enum):
    NEW = "NEW"
    WAITING_MANAGER = "WAITING_MANAGER"
    APPROVED = "APPROVED"
    ASSIGNED = "ASSIGNED"
    IN_PROGRESS = "IN_PROGRESS"
    PENDING = "PENDING"
    RESOLVED = "RESOLVED"
    FULFILLED = "FULFILLED"
    CLOSED = "CLOSED"
    REJECTED = "REJECTED"

class Ticket(Base):
    __tablename__ = "tickets"

    id = Column(Integer, primary_key=True, index=True)
    ticket_id = Column(String(50), unique=True, index=True, nullable=False)
    category = Column(String(50), nullable=False, index=True)
    description = Column(Text, nullable=True)
    issue_description = Column(Text, nullable=True)
    assigned_team = Column(String(100), nullable=True, index=True)
    priority = Column(String(50), nullable=True)
    sla_hours = Column(Integer, nullable=True)
    status = Column(String(50), default="NEW", index=True)  # Default to NEW
    servicenow_id = Column(String(100), nullable=True)
    servicenow_number = Column(String(100), nullable=True)
    created_by = Column(String(100), nullable=True, index=True)  # Username of the creator
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # ITSM Workflow fields
    request_type = Column(String(50), nullable=True)      # "INCIDENT" | "SERVICE_REQUEST" | "PRIVILEGED_ACTION"
    manager = Column(String(100), nullable=True, index=True) # Manager username
    approval_status = Column(String(50), nullable=True, index=True) # "PENDING" | "APPROVED" | "REJECTED" | "NOT_REQUIRED"
    assignment_group = Column(String(100), nullable=True)  # Maps to assignment group
    approved_by = Column(String(100), nullable=True)       # Username of approver
    approval_notes = Column(Text, nullable=True)           # Approval reason/notes
    approved_at = Column(DateTime, nullable=True)          # Timestamp of approval

    # ── SLA Escalation Engine fields ──────────────────────────────────────────
    sla_state = Column(String(50), nullable=True, default="HEALTHY", index=True) # SLA state enum string
    sla_breached = Column(Boolean, nullable=True, default=False, index=True)     # True once SLA is breached

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

    # LAPS Simulation fields
    laps_password = Column(String(100), nullable=True)
    laps_expiration = Column(DateTime, nullable=True)
    laps_active = Column(Boolean, default=False)
    laps_audit_id = Column(String(50), nullable=True)



