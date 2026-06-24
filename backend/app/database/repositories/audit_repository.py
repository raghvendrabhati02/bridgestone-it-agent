from sqlalchemy.orm import Session
from app.database.models.audit_log import AuditLog
from datetime import datetime

class AuditRepository:
    def __init__(self, db: Session):
        self.db = db

    def save(
        self,
        session_id: str,
        user_message: str,
        category: str,
        decision: str,
        approval_status: str = None,
        recommended_action: str = None,
        action_result: dict = None,
        ticket_id: str = None,
        servicenow_id: str = None
    ) -> AuditLog:
        log = AuditLog(
            session_id=session_id,
            user_message=user_message,
            category=category,
            decision=decision,
            approval_status=approval_status,
            recommended_action=recommended_action,
            action_result=action_result,
            ticket_id=ticket_id,
            servicenow_id=servicenow_id,
            created_at=datetime.utcnow()
        )
        self.db.add(log)
        self.db.commit()
        self.db.refresh(log)
        return log

    def get_all(self) -> list[AuditLog]:
        return self.db.query(AuditLog).order_by(AuditLog.id.asc()).all()
