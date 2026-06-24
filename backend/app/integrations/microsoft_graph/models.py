from pydantic import BaseModel
from typing import Optional, List

class UserProfile(BaseModel):
    id: str
    displayName: str
    mail: Optional[str] = None
    userPrincipalName: str
    jobTitle: Optional[str] = None
    officeLocation: Optional[str] = None

class DirectoryGroup(BaseModel):
    id: str
    displayName: str
    description: Optional[str] = None

class MailboxStatus(BaseModel):
    mailbox_status: str
    exchange_server: str
    exchange_latency: int

class LicenseStatus(BaseModel):
    license: str
    status: str
