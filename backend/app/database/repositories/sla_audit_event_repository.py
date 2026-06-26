"""
SLA Audit Event Repository
==========================
Handles the deduplication table for SLA state-transition events.

Every time a warning / breach / escalation milestone is about to fire,
the service first calls has_event() to check whether the event was already
recorded. Only if it is absent does it call record_event() and then proceed
to create the notification + RBAC audit log.

The SQLAlchemy model also carries a database-level UNIQUE constraint on
(ticket_id, event_type) as a safety net.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database.models.sla_audit_event import SlaAuditEvent


class SlaAuditEventRepository:
    def __init__(self, db: Session):
        self.db = db

    # ── Read ─────────────────────────────────────────────────────────────────

    def has_event(self, ticket_id: str, event_type: str) -> bool:
        """
        Returns True if an SlaAuditEvent already exists for
        (ticket_id, event_type).  Use this before sending any notification
        to ensure at-most-once semantics.
        """
        return (
            self.db.query(SlaAuditEvent)
            .filter(
                SlaAuditEvent.ticket_id == ticket_id,
                SlaAuditEvent.event_type == event_type,
            )
            .first()
            is not None
        )

    # ── Write ─────────────────────────────────────────────────────────────────

    def record_event(self, ticket_id: str, event_type: str) -> Optional[SlaAuditEvent]:
        """
        Inserts a new SlaAuditEvent row.

        Returns the created record, or None if a duplicate already exists
        (handles race conditions at the DB-constraint level gracefully).
        """
        try:
            event = SlaAuditEvent(
                ticket_id=ticket_id,
                event_type=event_type,
                created_at=datetime.utcnow(),
            )
            self.db.add(event)
            self.db.commit()
            self.db.refresh(event)
            return event
        except IntegrityError:
            # DB-level unique constraint triggered (race condition protection)
            self.db.rollback()
            return None
