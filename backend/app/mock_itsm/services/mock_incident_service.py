"""
mock_incident_service.py
─────────────────────────────────────────────────────────────────────────────
Incident Lifecycle & Ticket Management Service for Mock ITSM Platform.
Manages automatic ticket numbers (INC0000001, INC0000002...) and strict state transitions:
  New -> Assigned -> In Progress -> On Hold -> Resolved -> Closed
"""

import logging
from datetime import datetime
from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session

from app.mock_itsm.models.mock_ticket import MockTicket
from app.mock_itsm.repositories.mock_itsm_repository import MockITSMRepository
from app.mock_itsm.services.mock_assignment_service import MockAssignmentService
from app.mock_itsm.services.mock_sla_service import MockSLAService
from app.mock_itsm.services.mock_notification_service import MockNotificationService
from app.mock_itsm.services.mock_audit_service import MockAuditService

logger = logging.getLogger("it-agent-backend")

VALID_STATUSES = ["New", "Assigned", "In Progress", "On Hold", "Resolved", "Closed"]


class MockIncidentService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = MockITSMRepository(db)
        self.notification_service = MockNotificationService(db)
        self.audit_service = MockAuditService(db)

    def create_incident(
        self,
        category: str,
        description: str,
        short_description: Optional[str] = None,
        subcategory: Optional[str] = None,
        created_by: Optional[str] = "employee",
        assigned_group: Optional[str] = None,
        priority: Optional[str] = None,
        request_type: Optional[str] = "INCIDENT",
        manager: Optional[str] = "manager",
        impact: int = 3,
        urgency: int = 3,
        **kwargs
    ) -> MockTicket:
        """
        Creates a new incident in Mock ITSM with:
          - Automatic ticket number allocation (INC0000001...)
          - Priority calculation & SLA resolution target
          - Dynamic Assignment Group routing
          - Audit logging & Notifications
        """
        # Determine priority and SLA
        computed_priority = priority or MockSLAService.calculate_priority(category, description)
        sla_hours = MockSLAService.calculate_sla_hours(computed_priority)

        # Route assignment group if not specified
        target_group = assigned_group or MockAssignmentService.get_assignment_team(category, description)

        # Create ticket record
        ticket = self.repo.create_ticket(
            category=category,
            description=description,
            short_description=short_description,
            subcategory=subcategory,
            created_by=created_by,
            assigned_group=target_group,
            priority=computed_priority,
            impact=impact,
            urgency=urgency,
            request_type=request_type,
            manager=manager,
            sla_hours=sla_hours,
        )

        # State transition: New -> Assigned
        ticket.status = "Assigned"
        self.repo.update_ticket(ticket)

        # Log history & audit
        self.repo.add_history(
            ticket_number=ticket.ticket_number,
            changed_by=created_by or "system",
            field_changed="status",
            old_value="NEW",
            new_value="Assigned",
            change_reason="Auto-assigned to support group"
        )
        self.audit_service.log_event(
            event_type="Ticket Created",
            performed_by=created_by or "system",
            ticket_number=ticket.ticket_number,
            details={
                "category": category,
                "assigned_group": target_group,
                "priority": computed_priority,
                "sla_hours": sla_hours
            }
        )

        # Trigger notifications
        self.notification_service.notify_ticket_created(
            ticket_number=ticket.ticket_number,
            created_by=created_by or "employee",
            assigned_group=target_group,
            manager=manager
        )

        logger.info(
            "MockIncidentService: Created Ticket %s (Category=%s, Group=%s, Priority=%s)",
            ticket.ticket_number, category, target_group, computed_priority
        )
        return ticket

    def get_incident(self, ticket_number: str) -> Optional[MockTicket]:
        return self.repo.get_ticket_by_number(ticket_number)

    def list_incidents(
        self,
        status: Optional[str] = None,
        assigned_group: Optional[str] = None,
        category: Optional[str] = None,
        search_query: Optional[str] = None,
        limit: int = 100
    ) -> List[MockTicket]:
        return self.repo.list_tickets(
            status=status,
            assigned_group=assigned_group,
            category=category,
            search_query=search_query,
            limit=limit
        )

    def update_incident(
        self,
        ticket_number: str,
        changed_by: str = "system",
        status: Optional[str] = None,
        assigned_group: Optional[str] = None,
        assigned_engineer: Optional[str] = None,
        priority: Optional[str] = None,
        resolution_notes: Optional[str] = None,
        approval_status: Optional[str] = None,
        reason: Optional[str] = None,
        **kwargs
    ) -> MockTicket:
        """
        Updates ticket fields while maintaining state machine and history log.
        """
        ticket = self.repo.get_ticket_by_number(ticket_number)
        if not ticket:
            raise ValueError(f"Ticket {ticket_number} not found.")

        # Handle Status transition
        if status and status != ticket.status:
            old_status = ticket.status
            ticket.status = status
            self.repo.add_history(
                ticket_number=ticket_number,
                changed_by=changed_by,
                field_changed="status",
                old_value=old_status,
                new_value=status,
                change_reason=reason
            )
            self.audit_service.log_event(
                event_type="Status Changed",
                performed_by=changed_by,
                ticket_number=ticket_number,
                details={"old_status": old_status, "new_status": status, "reason": reason}
            )

            if status == "Resolved":
                ticket.resolved_at = datetime.utcnow()
                if resolution_notes:
                    ticket.resolution_notes = resolution_notes
                self.audit_service.log_event(
                    event_type="Resolution Added",
                    performed_by=changed_by,
                    ticket_number=ticket_number,
                    details={"resolution_notes": resolution_notes}
                )
            elif status == "Closed":
                ticket.closed_at = datetime.utcnow()

        # Handle Assignment transition
        if assigned_group and assigned_group != ticket.assigned_group:
            old_grp = ticket.assigned_group
            ticket.assigned_group = assigned_group
            self.repo.add_history(
                ticket_number=ticket_number,
                changed_by=changed_by,
                field_changed="assigned_group",
                old_value=old_grp,
                new_value=assigned_group,
                change_reason=reason
            )
            self.audit_service.log_event(
                event_type="Assignment Changed",
                performed_by=changed_by,
                ticket_number=ticket_number,
                details={"old_group": old_grp, "new_group": assigned_group}
            )

        if assigned_engineer and assigned_engineer != ticket.assigned_engineer:
            ticket.assigned_engineer = assigned_engineer

        if priority and priority != ticket.priority:
            ticket.priority = priority
            ticket.sla_hours = MockSLAService.calculate_sla_hours(priority)

        if approval_status and approval_status != ticket.approval_status:
            ticket.approval_status = approval_status

        if resolution_notes and not ticket.resolution_notes:
            ticket.resolution_notes = resolution_notes

        self.repo.update_ticket(ticket)
        self.audit_service.log_event(
            event_type="Ticket Updated",
            performed_by=changed_by,
            ticket_number=ticket_number,
            details={"changed_by": changed_by, "reason": reason}
        )
        return ticket

    def close_incident(self, ticket_number: str, closed_by: str = "system", resolution_notes: Optional[str] = None) -> MockTicket:
        """Closes an incident and sets closed_at timestamp."""
        return self.update_incident(
            ticket_number=ticket_number,
            changed_by=closed_by,
            status="Closed",
            resolution_notes=resolution_notes,
            reason="Ticket resolved and closed"
        )

    def resolve_incident(self, ticket_number: str, resolved_by: str = "system", resolution_notes: Optional[str] = None) -> MockTicket:
        """Resolves an incident."""
        return self.update_incident(
            ticket_number=ticket_number,
            changed_by=resolved_by,
            status="Resolved",
            resolution_notes=resolution_notes,
            reason="Incident resolved"
        )

    def reopen_incident(self, ticket_number: str, reopened_by: str = "system", reason: Optional[str] = None) -> MockTicket:
        """Reopens a resolved or closed incident."""
        return self.update_incident(
            ticket_number=ticket_number,
            changed_by=reopened_by,
            status="In Progress",
            reason=reason or "Ticket reopened"
        )

    def delete_incident(self, ticket_number: str) -> bool:
        """Deletes an incident (internal only)."""
        return self.repo.delete_ticket(ticket_number)
