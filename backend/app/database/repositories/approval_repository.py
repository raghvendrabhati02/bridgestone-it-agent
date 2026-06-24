from sqlalchemy.orm import Session
from app.database.models.approval_history import ApprovalHistory
from datetime import datetime

class ApprovalRepository:
    def __init__(self, db: Session):
        self.db = db

    def save(
        self,
        session_id: str,
        recommended_action: str,
        approval_status: str
    ) -> ApprovalHistory:
        approval = ApprovalHistory(
            session_id=session_id,
            recommended_action=recommended_action,
            approval_status=approval_status,
            created_at=datetime.utcnow()
        )
        self.db.add(approval)
        self.db.commit()
        self.db.refresh(approval)
        return approval

    def get_all(self) -> list[ApprovalHistory]:
        return self.db.query(ApprovalHistory).order_by(ApprovalHistory.id.asc()).all()
