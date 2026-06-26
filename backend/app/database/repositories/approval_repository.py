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
        from app.core.logging_context import correlation_id_ctx
        corr_id = correlation_id_ctx.get() or None

        # If the status is transitioning to a final state, try to update the existing PENDING record
        if approval_status != "PENDING":
            pending = (
                self.db.query(ApprovalHistory)
                .filter(
                    ApprovalHistory.session_id == session_id,
                    ApprovalHistory.approval_status == "PENDING"
                )
                .first()
            )
            if pending:
                pending.approval_status = approval_status
                if corr_id:
                    pending.correlation_id = corr_id
                pending.created_at = datetime.utcnow()
                self.db.commit()
                self.db.refresh(pending)
                return pending

        # Default: Save as a new approval history entry
        approval = ApprovalHistory(
            session_id=session_id,
            recommended_action=recommended_action,
            approval_status=approval_status,
            correlation_id=corr_id,
            created_at=datetime.utcnow()
        )
        self.db.add(approval)
        self.db.commit()
        self.db.refresh(approval)
        return approval

    def get_all(self) -> list[ApprovalHistory]:
        return self.db.query(ApprovalHistory).order_by(ApprovalHistory.id.asc()).all()
