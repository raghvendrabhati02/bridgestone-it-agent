from sqlalchemy import Column, Integer, String, DateTime, UniqueConstraint
from datetime import datetime
from app.database.base import Base


class SlaAuditEvent(Base):
    """
    Deduplication table for SLA state-transition events.

    Every time a warning / breach / escalation milestone is about to be
    triggered for a ticket, we first check this table.  If the event has
    already been recorded we skip it — preventing duplicate notifications
    and audit log noise across scheduler runs.

    Event Types
    -----------
    WARNING_75      – SLA has reached 75 % consumed
    WARNING_90      – SLA has reached 90 % consumed
    BREACHED        – SLA has exceeded 100 % (breach)
    ESCALATED_L1    – Level-1 escalation triggered (immediately after breach)
    ESCALATED_L2    – Level-2 escalation triggered (30 min after breach)
    ESCALATED_L3    – Level-3 escalation triggered (60 min after breach)

    The unique constraint on (ticket_id, event_type) guarantees at-most-once
    semantics at the database level as a safety net in addition to the
    application-layer check.
    """

    __tablename__ = "sla_audit_events"

    id         = Column(Integer,  primary_key=True, index=True, autoincrement=True)
    ticket_id  = Column(String(50), nullable=False, index=True)
    event_type = Column(String(50), nullable=False)  # WARNING_75 | WARNING_90 | BREACHED | ESCALATED_Ln
    created_at = Column(DateTime,   nullable=False,  default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("ticket_id", "event_type", name="uq_sla_audit_ticket_event"),
    )
