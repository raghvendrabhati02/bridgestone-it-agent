import logging
from datetime import datetime
from sqlalchemy.orm import Session
from app.database.models.workflow_models import TicketTimeline
from app.core.logging_context import correlation_id_ctx, user_ctx

logger = logging.getLogger("it-agent-backend")

class TimelineService:
    @staticmethod
    def log_event(
        db: Session,
        ticket_id: str,
        event_type: str,
        actor: str = None,
        action: str = None,
        description: str = "",
        correlation_id: str = None
    ) -> TicketTimeline:
        """
        Appends an event to the ticket timeline and handles default context resolution.
        """
        # Resolve actor, action and correlation_id defaults from context variables if not provided
        if not actor or actor == "anonymous":
            actor = user_ctx.get() or "system"
        if not correlation_id:
            correlation_id = correlation_id_ctx.get() or None
        if not action:
            action = event_type.lower().replace("_", " ")

        event = TicketTimeline(
            ticket_id=ticket_id,
            event_type=event_type,
            actor=actor,
            action=action,
            description=description,
            correlation_id=correlation_id,
            created_at=datetime.utcnow()
        )
        
        db.add(event)
        try:
            db.flush()  # flush to generate ID without committing outer transaction
            logger.info(
                "Timeline Logged: [%s] Ticket %s, Actor=%s, Action=%s, CorrId=%s",
                event_type, ticket_id, actor, action, correlation_id
            )
        except Exception as e:
            logger.error("Failed to log timeline event for ticket %s: %s", ticket_id, e)
            
        return event

    @staticmethod
    def get_timeline(db: Session, ticket_id: str):
        """
        Returns chronological events for a ticket.
        """
        return db.query(TicketTimeline).filter(
            TicketTimeline.ticket_id == ticket_id
        ).order_by(TicketTimeline.created_at.asc()).all()
