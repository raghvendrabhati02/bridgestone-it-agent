"""
mock_notification_service.py
─────────────────────────────────────────────────────────────────────────────
Notification Engine for Mock ITSM Platform.
Handles role-based notification dispatching for Employee, Manager, Engineer, and Admin.
"""

import logging
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session

from app.mock_itsm.repositories.mock_itsm_repository import MockITSMRepository

logger = logging.getLogger("it-agent-backend")


class MockNotificationService:
    def __init__(self, db: Session):
        self.repo = MockITSMRepository(db)

    def send_notification(
        self,
        ticket_number: str,
        recipient: str,
        recipient_role: str,
        message: str
    ) -> Dict[str, Any]:
        """Creates and logs a role notification."""
        notif = self.repo.create_notification(
            ticket_number=ticket_number,
            recipient=recipient,
            recipient_role=recipient_role,
            message=message
        )
        logger.info(
            "MockNotificationService: Notification [%s] sent to %s (%s) for Ticket %s",
            notif.notification_id, recipient, recipient_role, ticket_number
        )
        return {
            "notification_id": notif.notification_id,
            "ticket_number": notif.ticket_number,
            "recipient": notif.recipient,
            "recipient_role": notif.recipient_role,
            "message": notif.message,
            "status": notif.status,
            "created_at": notif.created_at.isoformat() + "Z"
        }

    def notify_ticket_created(self, ticket_number: str, created_by: str, assigned_group: str, manager: Optional[str] = None):
        """Dispatches creation notifications to employee, manager, and assigned engineering team."""
        # Employee notification
        self.send_notification(
            ticket_number=ticket_number,
            recipient=created_by or "employee",
            recipient_role="EMPLOYEE",
            message=f"Your IT ticket {ticket_number} has been created and assigned to {assigned_group}."
        )
        # Manager notification if pending manager approval
        if manager:
            self.send_notification(
                ticket_number=ticket_number,
                recipient=manager,
                recipient_role="MANAGER",
                message=f"Ticket {ticket_number} created by {created_by} requires your review."
            )
        # Engineer / Team notification
        self.send_notification(
            ticket_number=ticket_number,
            recipient=assigned_group,
            recipient_role="ENGINEER",
            message=f"New ticket {ticket_number} assigned to group {assigned_group}."
        )

    def notify_approval_requested(self, ticket_number: str, approver: str, role: str):
        self.send_notification(
            ticket_number=ticket_number,
            recipient=approver,
            recipient_role=role,
            message=f"Action required: Ticket {ticket_number} is awaiting your {role.lower()} approval."
        )

    def notify_ticket_status_change(self, ticket_number: str, recipient: str, role: str, new_status: str):
        self.send_notification(
            ticket_number=ticket_number,
            recipient=recipient,
            recipient_role=role,
            message=f"Ticket {ticket_number} status updated to '{new_status}'."
        )
