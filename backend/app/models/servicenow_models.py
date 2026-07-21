"""
servicenow_models.py
─────────────────────────────────────────────────────────────────────────────
Strongly-typed Pydantic models for ServiceNow integration layer.
"""

from __future__ import annotations
from typing import Optional, Dict, Any, Union
from pydantic import BaseModel, Field


def extract_sn_field(data: dict, field_name: str, default: str = "") -> str:
    """Extract a ServiceNow field value safely whether it's a scalar string or reference object."""
    if not isinstance(data, dict):
        return default
    val = data.get(field_name)
    if val is None:
        return default
    if isinstance(val, dict):
        return str(val.get("display_value") or val.get("value") or val.get("name") or default)
    return str(val)


class IncidentCreateRequest(BaseModel):
    """Payload model for creating a ServiceNow incident."""
    short_description: str = Field(..., description="Short summary of the issue")
    description: str = Field(..., description="Detailed description of the issue")
    category: Optional[str] = Field("GENERAL", description="Category of the ticket")
    severity: int = Field(3, description="Incident severity level (1-High, 2-Medium, 3-Low)")
    assignment_group: Optional[str] = Field("IT Support", description="Assigned support team group")
    caller_id: Optional[str] = Field(None, description="Username or ID of the caller")
    urgency: Optional[int] = Field(3, description="Urgency level")
    impact: Optional[int] = Field(3, description="Impact level")
    extra_fields: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Additional custom fields")


class IncidentCreateResponse(BaseModel):
    """Response model returned after creating a ServiceNow incident."""
    success: bool = Field(..., description="True if incident creation succeeded")
    sys_id: str = Field("", description="ServiceNow sys_id identifier")
    number: str = Field("", description="ServiceNow incident number (e.g. INC0012345)")
    ticket_id: str = Field("", description="Normalized ticket ID")
    state: str = Field("", description="State code of the created incident")
    caller_id: Optional[str] = Field(None, description="Caller ID assigned to incident")
    message: str = Field("", description="Status message or error explanation")
    result: Optional[Dict[str, Any]] = Field(None, description="Raw result dictionary from ServiceNow")


class IncidentStatus(BaseModel):
    """Model representing the status of an incident retrieved from ServiceNow."""
    sys_id: str = Field(..., description="ServiceNow sys_id identifier")
    number: str = Field("", description="ServiceNow incident number")
    state: str = Field("", description="State code or status description")
    short_description: Optional[str] = Field("", description="Summary description")
    description: Optional[str] = Field("", description="Detailed description")
    category: Optional[str] = Field("", description="Category of the incident")
    assignment_group: Optional[str] = Field("", description="Assigned support group")
    caller_id: Optional[str] = Field(None, description="Caller ID associated with incident")
    created_at: Optional[str] = Field(None, description="Creation timestamp ISO string")
    updated_at: Optional[str] = Field(None, description="Last updated timestamp ISO string")
    close_notes: Optional[str] = Field(None, description="Resolution or close notes")
    work_notes: Optional[str] = Field(None, description="Work log notes")
    raw_result: Optional[Dict[str, Any]] = Field(None, description="Full raw JSON result dictionary")


class IncidentUpdateRequest(BaseModel):
    """Payload model for updating an existing ServiceNow incident."""
    short_description: Optional[str] = Field(None, description="Updated short description")
    description: Optional[str] = Field(None, description="Updated description")
    state: Optional[str] = Field(None, description="Target state code (e.g. '7' for closed)")
    assignment_group: Optional[str] = Field(None, description="New assignment group")
    caller_id: Optional[str] = Field(None, description="Updated caller ID")
    work_notes: Optional[str] = Field(None, description="Work note entry")
    close_notes: Optional[str] = Field(None, description="Close / resolution note entry")
    close_code: Optional[str] = Field(None, description="Resolution code description")
    extra_fields: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Additional custom fields")
