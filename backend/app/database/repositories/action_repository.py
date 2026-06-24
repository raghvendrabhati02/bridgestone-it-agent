from sqlalchemy.orm import Session
from app.database.models.action_history import ActionHistory
from datetime import datetime

class ActionRepository:
    def __init__(self, db: Session):
        self.db = db

    def save(
        self,
        request_id: str,
        action_type: str,
        status: str,
        approved_by_user: bool,
        servicenow_id: str = None
    ) -> ActionHistory:
        action = ActionHistory(
            request_id=request_id,
            action_type=action_type,
            status=status,
            approved_by_user=approved_by_user,
            servicenow_id=servicenow_id,
            created_at=datetime.utcnow()
        )
        self.db.add(action)
        self.db.commit()
        self.db.refresh(action)
        return action

    def get_all(self) -> list[ActionHistory]:
        return self.db.query(ActionHistory).order_by(ActionHistory.id.asc()).all()
