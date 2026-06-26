from sqlalchemy.orm import Session
from app.database.models.ticket import Ticket
from app.database.models.notification import Notification
from datetime import datetime

class TicketRepository:
    def __init__(self, db: Session):
        self.db = db

    def save_ticket(
        self,
        ticket_id: str,
        category: str,
        description: str,
        issue_description: str,
        assigned_team: str,
        priority: str,
        sla_hours: int,
        status: str = "OPEN",
        servicenow_id: str = None,
        created_by: str = None
    ) -> Ticket:
        ticket = self.db.query(Ticket).filter(Ticket.ticket_id == ticket_id).first()
        if not ticket:
            ticket = Ticket(ticket_id=ticket_id)
            self.db.add(ticket)
            
        ticket.category = category
        ticket.description = description
        ticket.issue_description = issue_description
        ticket.assigned_team = assigned_team
        ticket.priority = priority
        ticket.sla_hours = sla_hours
        ticket.status = status
        ticket.servicenow_id = servicenow_id
        ticket.created_by = created_by
        ticket.created_at = datetime.utcnow()

        
        self.db.commit()
        self.db.refresh(ticket)
        return ticket

    def get_ticket(self, ticket_id: str) -> Ticket | None:
        return self.db.query(Ticket).filter(Ticket.ticket_id == ticket_id).first()

    def get_all_tickets(self) -> list[Ticket]:
        return self.db.query(Ticket).order_by(Ticket.id.asc()).all()

    def save_notification(
        self,
        notification_id: str,
        ticket_id: str,
        recipient: str,
        message: str,
        status: str = "SENT"
    ) -> Notification:
        from app.core.logging_context import correlation_id_ctx
        corr_id = correlation_id_ctx.get() or None
        notif = self.db.query(Notification).filter(Notification.notification_id == notification_id).first()
        if not notif:
            notif = Notification(notification_id=notification_id)
            self.db.add(notif)
            
        notif.ticket_id = ticket_id
        notif.recipient = recipient
        notif.message = message
        notif.status = status
        if corr_id:
            notif.correlation_id = corr_id
        notif.created_at = datetime.utcnow()
        
        self.db.commit()
        self.db.refresh(notif)
        return notif

    def get_all_notifications(self) -> list[Notification]:
        return self.db.query(Notification).order_by(Notification.id.asc()).all()
