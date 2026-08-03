"""
mock_approval_service.py
─────────────────────────────────────────────────────────────────────────────
Approval Workflow Engine for Mock ITSM Platform (Sprint 3).
Enforces approval lifecycle: PENDING, APPROVED, REJECTED, EXPIRED across approval types:
  - Software Installation
  - Admin Access
  - Factory Reset
  - VPN Privilege
  - Database Access
"""

import logging
from datetime import datetime
from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session

from app.mock_itsm.repositories.mock_itsm_repository import MockITSMRepository
from app.mock_itsm.services.mock_audit_service import MockAuditService

logger = logging.getLogger("it-agent-backend")

APPROVAL_TYPES = [
    "Software Installation",
    "Admin Access",
    "Factory Reset",
    "VPN Privilege",
    "Database Access",
]


class MockApprovalService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = MockITSMRepository(db)
        self.audit_service = MockAuditService(db)

    def request_approval(
        self,
        ticket_number: str,
        requester: str,
        approver: Optional[str] = None,
        approver_role: str = "MANAGER",
        approval_type: str = "Admin Access",
        comments: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Submits an approval request linked to a ticket."""
        ticket = self.repo.get_ticket_by_number(ticket_number)
        if not ticket:
            raise ValueError(f"Ticket {ticket_number} not found.")

        ticket.approval_status = "PENDING"
        ticket.status = "On Hold"
        self.repo.update_ticket(ticket)

        approval = self.repo.create_approval_request(
            ticket_number=ticket_number,
            requester=requester,
            approver=approver,
            approver_role=approver_role,
            approval_type=approval_type,
            comments=comments,
            notes=comments,
        )

        self.audit_service.log_event(
            event_type="Approval Created",
            performed_by=requester,
            ticket_number=ticket_number,
            details={
                "approval_id": approval.id,
                "approver": approver,
                "approver_role": approver_role,
                "approval_type": approval_type,
                "comments": comments,
            },
        )

        return {
            "id": approval.id,
            "ticket_number": approval.ticket_number,
            "requester": approval.requester,
            "approver": approval.approver,
            "approver_role": approval.approver_role,
            "approval_type": approval.approval_type,
            "status": approval.status,
            "comments": approval.comments,
            "requested_at": approval.requested_at.isoformat() + "Z",
        }

    def action_approval(
        self,
        approval_id: int,
        approver_username: str,
        decision: str,  # APPROVED or REJECTED
        comments: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Processes approval action (APPROVE or REJECT)."""
        approval = self.repo.get_approval_by_id(approval_id)
        if not approval:
            raise ValueError(f"Approval request {approval_id} not found.")

        if approval.status != "PENDING":
            raise ValueError(f"Approval {approval_id} is already in state '{approval.status}'.")

        decision_upper = decision.strip().upper()
        if decision_upper not in ("APPROVED", "REJECTED", "EXPIRED"):
            raise ValueError(f"Invalid decision '{decision}'. Must be APPROVED, REJECTED, or EXPIRED.")

        approval.status = decision_upper
        approval.approver = approver_username
        approval.comments = comments or approval.comments
        approval.notes = comments or approval.notes
        approval.actioned_at = datetime.utcnow()
        self.repo.update_approval(approval)

        # Update linked ticket
        ticket = self.repo.get_ticket_by_number(approval.ticket_number)
        if ticket:
            ticket.approval_status = decision_upper
            ticket.approved_by = approver_username if decision_upper == "APPROVED" else None
            ticket.approval_notes = comments
            if decision_upper == "APPROVED":
                ticket.approved_at = datetime.utcnow()
                ticket.status = "Assigned" if ticket.assigned_group else "In Progress"
            elif decision_upper == "REJECTED":
                ticket.status = "Closed"
                ticket.closed_at = datetime.utcnow()
            self.repo.update_ticket(ticket)

            self.repo.add_history(
                ticket_number=ticket.ticket_number,
                changed_by=approver_username,
                field_changed="approval_status",
                old_value="PENDING",
                new_value=decision_upper,
                change_reason=comments,
            )

        audit_event_map = {
            "APPROVED": "Approval Approved",
            "REJECTED": "Approval Rejected",
            "EXPIRED": "Approval Expired",
            "CANCELLED": "Approval Cancelled"
        }
        event_name = audit_event_map.get(decision_upper, f"Approval {decision_upper.title()}")

        self.audit_service.log_event(
            event_type=event_name,
            performed_by=approver_username,
            ticket_number=approval.ticket_number,
            details={"approval_id": approval.id, "decision": decision_upper, "comments": comments},
        )

        return {
            "id": approval.id,
            "ticket_number": approval.ticket_number,
            "requester": approval.requester,
            "approver": approval.approver,
            "approval_type": approval.approval_type,
            "status": approval.status,
            "comments": approval.comments,
            "actioned_at": approval.actioned_at.isoformat() + "Z",
        }

    def process_approval(
        self,
        ticket_number: str,
        approver_username: str,
        action: str,
        notes: Optional[str] = None,
        is_admin_override: bool = False,
    ) -> Dict[str, Any]:
        """Legacy helper matching ticket_number processing."""
        approvals = self.repo.get_approvals_for_ticket(ticket_number)
        pending = next((a for a in approvals if a.status == "PENDING"), None)
        if pending:
            return self.action_approval(pending.id, approver_username, action, notes)
        
        # If no pending record exists, create and action one
        req = self.request_approval(
            ticket_number=ticket_number,
            requester="employee",
            approver=approver_username,
            comments=notes,
        )
        return self.action_approval(req["id"], approver_username, action, notes)

    def get_pending_approvals(self, approver_username: Optional[str] = None) -> List[Dict[str, Any]]:
        approvals = self.repo.get_pending_approvals(approver_username)
        return [self._format_approval(a) for a in approvals]

    def get_my_requests(self, requester_username: str) -> List[Dict[str, Any]]:
        approvals = self.repo.get_approvals_by_requester(requester_username)
        return [self._format_approval(a) for a in approvals]

    def get_all_approvals(self) -> List[Dict[str, Any]]:
        approvals = self.repo.get_all_approvals()
        return [self._format_approval(a) for a in approvals]

    def get_ticket_approvals(self, ticket_number: str) -> List[Dict[str, Any]]:
        approvals = self.repo.get_approvals_for_ticket(ticket_number)
        return [self._format_approval(a) for a in approvals]

    def get_approval_by_id(self, approval_id: int, viewer: str = "system") -> Dict[str, Any]:
        a = self.repo.get_approval_by_id(approval_id)
        if not a:
            raise ValueError(f"Approval request {approval_id} not found.")
        self.audit_service.log_event(
            event_type="Approval Viewed",
            performed_by=viewer,
            ticket_number=a.ticket_number,
            details={"approval_id": a.id}
        )
        return self._format_approval(a)

    def _format_approval(self, a) -> Dict[str, Any]:
        return {
            "id": a.id,
            "ticket_number": a.ticket_number,
            "requester": a.requester,
            "approver": a.approver,
            "approver_role": a.approver_role,
            "approval_type": a.approval_type,
            "status": a.status,
            "comments": a.comments or a.notes,
            "requested_at": a.requested_at.isoformat() + "Z" if a.requested_at else None,
            "actioned_at": a.actioned_at.isoformat() + "Z" if a.actioned_at else None,
        }
