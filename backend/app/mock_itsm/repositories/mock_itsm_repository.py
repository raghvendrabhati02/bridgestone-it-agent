"""
mock_itsm_repository.py
─────────────────────────────────────────────────────────────────────────────
Repository pattern implementation for Mock ITSM database operations.
"""

from typing import List, Optional, Tuple
from datetime import datetime
from sqlalchemy import func, select, or_
from sqlalchemy.orm import Session

from app.mock_itsm.models.mock_ticket import MockTicket
from app.mock_itsm.models.mock_ticket_history import MockTicketHistory
from app.mock_itsm.models.mock_approval import MockApproval
from app.mock_itsm.models.mock_approval_history import MockApprovalHistory
from app.mock_itsm.models.mock_approval_comment import MockApprovalComment
from app.mock_itsm.models.mock_notification import MockNotification
from app.mock_itsm.models.mock_assignment_group import MockAssignmentGroup
from app.mock_itsm.models.mock_audit_log import MockAuditLog
from app.mock_itsm.models.mock_user import MockUser


class MockITSMRepository:
    def __init__(self, db: Session):
        self.db = db

    # ── Ticket Operations ──────────────────────────────────────────────────────

    def allocate_next_ticket_number(self) -> str:
        """
        Allocates the next ticket number in format INC0000001, INC0000002...
        Thread-safe DB MAX(id) increment.
        """
        max_id = self.db.execute(select(func.max(MockTicket.id))).scalar()
        next_num = int(max_id or 0) + 1
        return f"INC{next_num:07d}"

    def create_ticket(
        self,
        category: str,
        description: str,
        short_description: Optional[str] = None,
        subcategory: Optional[str] = None,
        created_by: Optional[str] = "employee",
        assigned_group: Optional[str] = None,
        assigned_engineer: Optional[str] = None,
        priority: str = "LOW",
        impact: int = 3,
        urgency: int = 3,
        request_type: str = "INCIDENT",
        manager: Optional[str] = "manager",
        approval_status: str = "NOT_REQUIRED",
        sla_hours: int = 24,
    ) -> MockTicket:
        ticket_number = self.allocate_next_ticket_number()
        ticket = MockTicket(
            ticket_number=ticket_number,
            category=category,
            subcategory=subcategory,
            short_description=short_description or f"{category} issue",
            description=description,
            status="NEW",
            assigned_group=assigned_group,
            assigned_engineer=assigned_engineer,
            created_by=created_by,
            manager=manager,
            priority=priority,
            impact=impact,
            urgency=urgency,
            request_type=request_type,
            approval_status=approval_status,
            sla_hours=sla_hours,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        self.db.add(ticket)
        self.db.flush()
        return ticket

    def get_ticket_by_number(self, ticket_number: str) -> Optional[MockTicket]:
        return self.db.query(MockTicket).filter(
            or_(
                MockTicket.ticket_number == ticket_number,
                MockTicket.id == int(ticket_number) if ticket_number.isdigit() else False
            )
        ).first()

    def list_tickets(
        self,
        status: Optional[str] = None,
        assigned_group: Optional[str] = None,
        category: Optional[str] = None,
        search_query: Optional[str] = None,
        limit: int = 100
    ) -> List[MockTicket]:
        query = self.db.query(MockTicket)
        if status:
            query = query.filter(MockTicket.status == status)
        if assigned_group:
            query = query.filter(MockTicket.assigned_group == assigned_group)
        if category:
            query = query.filter(MockTicket.category == category)
        if search_query:
            pattern = f"%{search_query}%"
            query = query.filter(
                or_(
                    MockTicket.ticket_number.ilike(pattern),
                    MockTicket.category.ilike(pattern),
                    MockTicket.short_description.ilike(pattern),
                    MockTicket.description.ilike(pattern),
                    MockTicket.assigned_group.ilike(pattern),
                )
            )
        return query.order_by(MockTicket.id.desc()).limit(limit).all()

    def update_ticket(self, ticket: MockTicket) -> MockTicket:
        ticket.updated_at = datetime.utcnow()
        self.db.add(ticket)
        self.db.flush()
        return ticket

    def delete_ticket(self, ticket_number: str) -> bool:
        ticket = self.get_ticket_by_number(ticket_number)
        if ticket:
            self.db.delete(ticket)
            self.db.flush()
            return True
        return False

    # ── History & Audit Log ─────────────────────────────────────────────────────

    def add_history(
        self,
        ticket_number: str,
        changed_by: str,
        field_changed: str,
        old_value: Optional[str],
        new_value: Optional[str],
        change_reason: Optional[str] = None
    ) -> MockTicketHistory:
        history = MockTicketHistory(
            ticket_number=ticket_number,
            changed_by=changed_by,
            field_changed=field_changed,
            old_value=str(old_value) if old_value is not None else None,
            new_value=str(new_value) if new_value is not None else None,
            change_reason=change_reason,
            created_at=datetime.utcnow()
        )
        self.db.add(history)
        self.db.flush()
        return history

    def get_history(self, ticket_number: str) -> List[MockTicketHistory]:
        return self.db.query(MockTicketHistory).filter_by(ticket_number=ticket_number).order_by(MockTicketHistory.id.asc()).all()

    def add_audit_log(
        self,
        event_type: str,
        performed_by: str,
        ticket_number: Optional[str] = None,
        details: Optional[dict] = None
    ) -> MockAuditLog:
        log = MockAuditLog(
            ticket_number=ticket_number,
            event_type=event_type,
            performed_by=performed_by,
            details=details or {},
            created_at=datetime.utcnow()
        )
        self.db.add(log)
        self.db.flush()
        return log

    def get_audit_logs(self, ticket_number: Optional[str] = None, limit: int = 100) -> List[MockAuditLog]:
        query = self.db.query(MockAuditLog)
        if ticket_number:
            query = query.filter_by(ticket_number=ticket_number)
        return query.order_by(MockAuditLog.id.desc()).limit(limit).all()

    # ── Approval Operations ───────────────────────────────────────────────────

    def create_approval_request(
        self,
        ticket_number: str,
        requester: str,
        approver: Optional[str] = None,
        approver_role: str = "MANAGER",
        approval_type: str = "Admin Access",
        comments: Optional[str] = None,
        notes: Optional[str] = None
    ) -> MockApproval:
        approval = MockApproval(
            ticket_number=ticket_number,
            requester=requester,
            approver=approver,
            approver_username=approver or "manager",
            approver_role=approver_role,
            approval_type=approval_type,
            status="PENDING",
            comments=comments or notes,
            notes=notes or comments,
            requested_at=datetime.utcnow()
        )
        self.db.add(approval)
        self.db.flush()
        return approval

    def get_approval_by_id(self, approval_id: int) -> Optional[MockApproval]:
        return self.db.query(MockApproval).filter(MockApproval.id == approval_id).first()

    def get_approvals_for_ticket(self, ticket_number: str) -> List[MockApproval]:
        return self.db.query(MockApproval).filter_by(ticket_number=ticket_number).order_by(MockApproval.id.desc()).all()

    def get_pending_approvals(self, approver_username: Optional[str] = None) -> List[MockApproval]:
        query = self.db.query(MockApproval).filter(MockApproval.status == "PENDING")
        if approver_username:
            query = query.filter(or_(MockApproval.approver == approver_username, MockApproval.approver == None))
        return query.order_by(MockApproval.id.desc()).all()

    def get_approvals_by_requester(self, requester: str) -> List[MockApproval]:
        return self.db.query(MockApproval).filter_by(requester=requester).order_by(MockApproval.id.desc()).all()

    def get_all_approvals(self) -> List[MockApproval]:
        return self.db.query(MockApproval).order_by(MockApproval.id.desc()).all()

    def update_approval(self, approval: MockApproval) -> MockApproval:
        self.db.add(approval)
        self.db.flush()
        return approval

    def add_approval_history(
        self,
        approval_id: int,
        ticket_number: str,
        performed_by: str,
        action: str,
        old_status: Optional[str],
        new_status: str,
        comments: Optional[str] = None
    ) -> MockApprovalHistory:
        from app.mock_itsm.models.mock_approval_history import MockApprovalHistory
        hist = MockApprovalHistory(
            approval_id=approval_id,
            ticket_number=ticket_number,
            performed_by=performed_by,
            action=action,
            old_status=old_status,
            new_status=new_status,
            comments=comments,
            timestamp=datetime.utcnow()
        )
        self.db.add(hist)
        self.db.flush()
        return hist

    def add_approval_comment(
        self,
        approval_id: int,
        ticket_number: str,
        author: str,
        comment: str
    ) -> MockApprovalComment:
        from app.mock_itsm.models.mock_approval_comment import MockApprovalComment
        comm = MockApprovalComment(
            approval_id=approval_id,
            ticket_number=ticket_number,
            author=author,
            comment=comment,
            created_at=datetime.utcnow()
        )
        self.db.add(comm)
        self.db.flush()
        return comm

    # ── Notification Operations ────────────────────────────────────────────────

    def allocate_next_notification_id(self) -> str:
        max_id = self.db.execute(select(func.max(MockNotification.id))).scalar()
        next_num = int(max_id or 0) + 1
        return f"NOTIF{next_num:04d}"

    def create_notification(
        self,
        ticket_number: str,
        recipient: str,
        recipient_role: str,
        message: str
    ) -> MockNotification:
        notif_id = self.allocate_next_notification_id()
        notif = MockNotification(
            notification_id=notif_id,
            ticket_number=ticket_number,
            recipient=recipient,
            recipient_role=recipient_role,
            message=message,
            status="SENT",
            created_at=datetime.utcnow()
        )
        self.db.add(notif)
        self.db.flush()
        return notif

    def list_notifications(self, recipient: Optional[str] = None, limit: int = 100) -> List[MockNotification]:
        query = self.db.query(MockNotification)
        if recipient:
            query = query.filter_by(recipient=recipient)
        return query.order_by(MockNotification.id.desc()).limit(limit).all()

    # ── Assignment Group & User Operations ────────────────────────────────────

    def list_assignment_groups(self) -> List[MockAssignmentGroup]:
        return self.db.query(MockAssignmentGroup).filter_by(is_active=True).all()

    def get_assignment_group(self, name: str) -> Optional[MockAssignmentGroup]:
        return self.db.query(MockAssignmentGroup).filter_by(group_name=name).first()

    def get_user(self, username: str) -> Optional[MockUser]:
        return self.db.query(MockUser).filter_by(username=username).first()
