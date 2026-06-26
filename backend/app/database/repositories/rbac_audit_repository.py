import json
from datetime import datetime
from typing import Optional, List
from sqlalchemy.orm import Session
from app.database.models.rbac_audit_log import RbacAuditLog


class RbacAuditRepository:
    def __init__(self, db: Session):
        self.db = db

    def save(
        self,
        user: str,
        role: str,
        action: str,
        ticket_id: Optional[str] = None,
        old_state: Optional[str] = None,
        new_state: Optional[str] = None,
        details: Optional[dict] = None,
    ) -> RbacAuditLog:
        """Persists a single RBAC audit event row and returns it."""
        details_str = json.dumps(details) if details else None
        record = RbacAuditLog(
            timestamp=datetime.utcnow(),
            user=user,
            role=role,
            action=action,
            ticket_id=ticket_id,
            old_state=old_state,
            new_state=new_state,
            details=details_str,
        )
        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)
        return record

    def get_all(self) -> List[RbacAuditLog]:
        """Returns all RBAC audit rows, newest first."""
        return (
            self.db.query(RbacAuditLog)
            .order_by(RbacAuditLog.audit_id.desc())
            .all()
        )

    def get_by_ticket(self, ticket_id: str) -> List[RbacAuditLog]:
        """Returns all RBAC audit rows for a specific ticket."""
        return (
            self.db.query(RbacAuditLog)
            .filter(RbacAuditLog.ticket_id == ticket_id)
            .order_by(RbacAuditLog.audit_id.desc())
            .all()
        )

    def get_by_user(self, username: str) -> List[RbacAuditLog]:
        """Returns all RBAC audit rows for a specific user."""
        return (
            self.db.query(RbacAuditLog)
            .filter(RbacAuditLog.user == username)
            .order_by(RbacAuditLog.audit_id.desc())
            .all()
        )
