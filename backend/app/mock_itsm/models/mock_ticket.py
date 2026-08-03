from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean
from app.database.base import Base

class MockTicket(Base):
    __tablename__ = "mock_tickets"

    id = Column(Integer, primary_key=True, index=True)
    ticket_number = Column(String(50), unique=True, index=True, nullable=False)  # e.g., INC0000001
    category = Column(String(50), nullable=False)
    subcategory = Column(String(50), nullable=True)
    short_description = Column(String(255), nullable=True)
    description = Column(Text, nullable=True)
    
    # State Machine: NEW -> ASSIGNED -> IN_PROGRESS -> ON_HOLD -> RESOLVED -> CLOSED
    status = Column(String(50), default="NEW", index=True, nullable=False)
    
    # Assignment & Ownership
    assigned_group = Column(String(100), nullable=True, index=True)
    assigned_engineer = Column(String(100), nullable=True)
    created_by = Column(String(100), nullable=True)
    manager = Column(String(100), nullable=True)
    
    # Priority & Impact
    priority = Column(String(50), default="LOW", nullable=False)
    impact = Column(Integer, default=3)
    urgency = Column(Integer, default=3)
    request_type = Column(String(50), default="INCIDENT")  # INCIDENT, SERVICE_REQUEST, PRIVILEGED_ACTION
    
    # Workflow & Approval
    approval_status = Column(String(50), default="NOT_REQUIRED")  # NOT_REQUIRED, PENDING, APPROVED, REJECTED
    approved_by = Column(String(100), nullable=True)
    approval_notes = Column(Text, nullable=True)
    approved_at = Column(DateTime, nullable=True)
    
    # Resolution & Closure
    resolution_notes = Column(Text, nullable=True)
    resolved_at = Column(DateTime, nullable=True)
    closed_at = Column(DateTime, nullable=True)
    
    # SLA Tracking
    sla_hours = Column(Integer, nullable=True, default=24)
    sla_breached = Column(Boolean, default=False)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
