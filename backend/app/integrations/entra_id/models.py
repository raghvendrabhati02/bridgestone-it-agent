from pydantic import BaseModel
from typing import Optional, List, Dict, Any

class UserProfile(BaseModel):
    id: str
    displayName: str
    mail: Optional[str] = None
    userPrincipalName: str
    jobTitle: Optional[str] = None
    department: Optional[str] = None

class DirectoryGroup(BaseModel):
    id: str
    displayName: str
    description: Optional[str] = None

class AccessStatus(BaseModel):
    user_id: str
    target: str  # VPN, app, or security group name
    allowed: bool
    details: Optional[str] = None

class RoleStatus(BaseModel):
    user_id: str
    role: str
    is_assigned: bool

class MonitoringStats(BaseModel):
    status: str
    latency_ms: float
    total_users: int
    total_groups: int
    group_membership_checks: int
    access_validation_checks: int
    role_assignment_checks: int
