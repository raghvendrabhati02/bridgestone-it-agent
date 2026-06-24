from pydantic import BaseModel
from typing import Optional

class ServiceNowIncident(BaseModel):
    sys_id: str
    number: str
    state: str
    category: Optional[str] = None
    description: Optional[str] = None
    assignment_group: Optional[str] = None

class IncidentCreateRequest(BaseModel):
    category: str
    description: str
    assignment_group: str

class IncidentUpdateRequest(BaseModel):
    state: Optional[str] = None
    assignment_group: Optional[str] = None

class ServiceRequestCreateRequest(BaseModel):
    category: str
    description: str
    action_type: str

class ServiceRequestUpdateRequest(BaseModel):
    state: Optional[str] = None
