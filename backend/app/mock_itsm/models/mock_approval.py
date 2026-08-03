from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime
from app.database.base import Base

class MockApproval(Base):
    __tablename__ = "mock_approvals"

    id = Column(Integer, primary_key=True, index=True)
    ticket_number = Column(String(50), index=True, nullable=False)
    requester = Column(String(100), nullable=False)
    approver = Column(String(100), nullable=True)
    approver_username = Column(String(100), nullable=True)
    approver_role = Column(String(50), default="MANAGER", nullable=False)  # MANAGER, ADMIN
    
    # Supported Approval Types: Software Installation, Admin Privileges, Factory Reset, Password Reset, VPN Elevated Access, Database Access
    approval_type = Column(String(50), default="Admin Privileges", nullable=False)
    
    # Statuses: PENDING, APPROVED, REJECTED, EXPIRED, CANCELLED
    status = Column(String(50), default="PENDING", nullable=False, index=True)
    decision = Column(String(50), nullable=True)
    
    comments = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    requested_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    actioned_at = Column(DateTime, nullable=True)
