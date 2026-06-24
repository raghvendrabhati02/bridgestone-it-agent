from pydantic import BaseModel

class ServiceNowIncident(BaseModel):
    sys_id: str
    number: str
    state: str
    category: str | None = None
    description: str | None = None
    assignment_group: str | None = None

class IncidentCreateRequest(BaseModel):
    category: str
    description: str
    assignment_group: str

class IncidentUpdateRequest(BaseModel):
    state: str | None = None
    assignment_group: str | None = None
