"""
mock_audit_service.py
─────────────────────────────────────────────────────────────────────────────
Audit Service for Mock ITSM Platform.
Records key lifecycle audit events:
  - Ticket Created
  - Ticket Updated
  - Assignment Changed
  - Status Changed
  - Approval Granted
  - Approval Rejected
  - Comment Added
  - Resolution Added
"""

import logging
from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session

from app.mock_itsm.repositories.mock_itsm_repository import MockITSMRepository

logger = logging.getLogger("it-agent-backend")


class MockAuditService:
    def __init__(self, db: Session):
        self.repo = MockITSMRepository(db)

    def log_event(
        self,
        event_type: str,
        performed_by: str,
        ticket_number: Optional[str] = None,
        details: Optional[dict] = None
    ) -> Dict[str, Any]:
        audit_entry = self.repo.add_audit_log(
            event_type=event_type,
            performed_by=performed_by,
            ticket_number=ticket_number,
            details=details or {}
        )
        logger.info(
            "MockAuditService: Recorded audit log [%s] by '%s' for Ticket %s",
            event_type, performed_by, ticket_number or "<general>"
        )
        return {
            "id": audit_entry.id,
            "ticket_number": audit_entry.ticket_number,
            "event_type": audit_entry.event_type,
            "performed_by": audit_entry.performed_by,
            "details": audit_entry.details,
            "created_at": audit_entry.created_at.isoformat() + "Z"
        }

    def get_audit_trail(self, ticket_number: Optional[str] = None) -> List[Dict[str, Any]]:
        logs = self.repo.get_audit_logs(ticket_number=ticket_number)
        return [
            {
                "id": log.id,
                "ticket_number": log.ticket_number,
                "event_type": log.event_type,
                "performed_by": log.performed_by,
                "details": log.details,
                "created_at": log.created_at.isoformat() + "Z"
            }
            for log in logs
        ]
