from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field

class MockTicketCreateRequest(BaseModel):
    category: str
    description: str
    short_description: Optional[str] = None
    subcategory: Optional[str] = None
    created_by: Optional[str] = "employee"
    assigned_group: Optional[str] = None
    priority: Optional[str] = "LOW"
    impact: Optional[int] = 3
    urgency: Optional[int] = 3
    request_type: Optional[str] = "INCIDENT"
    manager: Optional[str] = "manager"

class MockTicketUpdateRequest(BaseModel):
    status: Optional[str] = None
    assigned_group: Optional[str] = None
    assigned_engineer: Optional[str] = None
    priority: Optional[str] = None
    impact: Optional[int] = None
    urgency: Optional[int] = None
    resolution_notes: Optional[str] = None
    approval_status: Optional[str] = None
    approval_notes: Optional[str] = None
    approved_by: Optional[str] = None
    changed_by: Optional[str] = "system"
    reason: Optional[str] = None

class MockTicketResponse(BaseModel):
    id: int
    ticket_number: str
    category: str
    subcategory: Optional[str] = None
    short_description: Optional[str] = None
    description: Optional[str] = None
    status: str
    assigned_group: Optional[str] = None
    assigned_engineer: Optional[str] = None
    created_by: Optional[str] = None
    manager: Optional[str] = None
    priority: str
    impact: int
    urgency: int
    request_type: str
    approval_status: str
    approved_by: Optional[str] = None
    approval_notes: Optional[str] = None
    approved_at: Optional[datetime] = None
    resolution_notes: Optional[str] = None
    resolved_at: Optional[datetime] = None
    closed_at: Optional[datetime] = None
    sla_hours: Optional[int] = 24
    sla_breached: bool = False
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True
        from_attributes = True

class MockApprovalRequest(BaseModel):
    ticket_number: str
    approval_type: str = "Admin Access"
    # Types: Software Installation, Admin Access, Factory Reset, VPN Privilege, Database Access
    approver: Optional[str] = None
    approver_role: str = "MANAGER"
    comments: Optional[str] = None

class MockApprovalActionRequest(BaseModel):
    decision: str  # APPROVED, REJECTED
    comments: Optional[str] = None

class MockApprovalResponse(BaseModel):
    id: int
    ticket_number: str
    requester: str
    approver: Optional[str] = None
    approver_role: str
    approval_type: str
    status: str  # PENDING, APPROVED, REJECTED, EXPIRED
    comments: Optional[str] = None
    requested_at: datetime
    actioned_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class MockNotificationResponse(BaseModel):
    id: int
    notification_id: str
    ticket_number: str
    recipient: str
    recipient_role: str
    message: str
    status: str
    created_at: datetime

    class Config:
        from_attributes = True

class MockAssignmentGroupResponse(BaseModel):
    id: int
    group_name: str
    description: Optional[str] = None
    lead_engineer: Optional[str] = None
    is_active: bool

    class Config:
        from_attributes = True

class MockAuditLogResponse(BaseModel):
    id: int
    ticket_number: Optional[str] = None
    event_type: str
    performed_by: str
    details: Optional[Dict[str, Any]] = None
    created_at: datetime

    class Config:
        from_attributes = True
