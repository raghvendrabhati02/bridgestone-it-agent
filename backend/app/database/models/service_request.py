from sqlalchemy import Column, Integer, String, Text, DateTime
from datetime import datetime
from app.database.base import Base

class ServiceRequest(Base):
    __tablename__ = "service_requests"

    id = Column(Integer, primary_key=True, index=True)
    request_id = Column(String(50), unique=True, index=True, nullable=False)  # e.g., REQ0000001
    servicenow_id = Column(String(100), nullable=True)
    service_id = Column(String(50), nullable=False)
    service_name = Column(String(100), nullable=False)
    requested_by = Column(String(100), nullable=False, index=True)
    category = Column(String(50), nullable=False)
    description = Column(Text, nullable=True)
    status = Column(String(50), default="NEW")  # NEW, SUBMITTED, PENDING_APPROVAL, APPROVED, FULFILLMENT, COMPLETED, CLOSED, REJECTED
    stage = Column(String(100), default="Request Submitted")
    assigned_team = Column(String(100), nullable=True)
    estimated_completion = Column(String(50), nullable=True)
    sla_hours = Column(Integer, nullable=True)
    details = Column(Text, nullable=True)  # JSON string of dynamic questions/answers
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
