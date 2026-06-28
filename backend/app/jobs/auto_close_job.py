import logging
import os
from datetime import datetime, timedelta
from app.database.session import get_db
from app.database.models.ticket import Ticket
from app.services.timeline_service import TimelineService
from app.services.knowledge_generation_service import KnowledgeGenerationService

logger = logging.getLogger("it-agent-backend")

def run_auto_close_job():
    """
    Auto-Close Job: Automatically transitions tickets from RESOLVED to CLOSED
    after a configured duration (default: 5 days / 7200 minutes).
    Can be configured using the AUTO_CLOSE_MINUTES environment variable.
    """
    logger.info("Starting Auto-Close Resolved Tickets Job...")
    try:
        auto_close_minutes = int(os.getenv("AUTO_CLOSE_MINUTES", "7200"))
        cutoff = datetime.utcnow() - timedelta(minutes=auto_close_minutes)
        
        with get_db() as db:
            resolved_tickets = db.query(Ticket).filter(
                Ticket.status == "RESOLVED",
                Ticket.resolved_at <= cutoff
            ).all()
            
            closed_count = 0
            for ticket in resolved_tickets:
                ticket.status = "CLOSED"
                ticket.closed_at = datetime.utcnow()
                
                # Log timeline event
                TimelineService.log_event(
                    db=db,
                    ticket_id=ticket.ticket_id,
                    event_type="TICKET_CLOSED",
                    actor="system",
                    action="auto-close",
                    description=f"Ticket automatically closed after being in RESOLVED state for {auto_close_minutes} minutes.",
                    correlation_id=None
                )
                
                # Generate knowledge draft
                try:
                    logger.info("Triggering knowledge draft generation for ticket: %s", ticket.ticket_id)
                    KnowledgeGenerationService.generate_draft_for_ticket(db, ticket.ticket_id)
                except Exception as ex:
                    logger.error("Failed to generate knowledge draft for ticket %s: %s", ticket.ticket_id, ex)
                
                closed_count += 1
                
            db.commit()
            if closed_count > 0:
                logger.info("Auto-Close Job: Transitioned %d tickets to CLOSED.", closed_count)
            
        logger.info("Auto-Close Resolved Tickets Job completed successfully.")
    except Exception as e:
        logger.error("Auto-Close Resolved Tickets Job failed: %s", e)
        raise e
