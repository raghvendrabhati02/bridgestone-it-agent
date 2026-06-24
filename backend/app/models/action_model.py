from pydantic import BaseModel

class ActionRequest(BaseModel):
    request_id: str
    action_type: str
    status: str
    created_at: str
    approved_by_user: bool = True
