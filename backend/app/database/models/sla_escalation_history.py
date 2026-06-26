from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean
from datetime import datetime
from app.database.base import Base


class SlaEscalationHistory(Base):
    """
    Persistent record of every SLA escalation event for a ticket.

    Each row represents one escalation level (1, 2 or 3) being triggered.
    The unique combination of (ticket_id, level) is enforced at the
    application layer via SlaEscalationRepository.has_level() so that we
    never create duplicate escalation entries.

    Fields
    ------
    id               : auto PK
    ticket_id        : the affected ticket (e.g. INC000042)
    level            : escalation level 1 / 2 / 3
    reason           : human-readable reason string
    triggered_by     : system component that triggered this (sla_monitor_job)
    notification_sent: True once the notification has been created successfully
    audit_logged     : True once the RBAC audit event has been written
    created_at       : UTC timestamp of escalation trigger
    """

    __tablename__ = "sla_escalation_history"

    id                = Column(Integer, primary_key=True, index=True, autoincrement=True)
    ticket_id         = Column(String(50),  nullable=False, index=True)
    level             = Column(Integer,     nullable=False)           # 1, 2, 3
    reason            = Column(Text,        nullable=True)
    triggered_by      = Column(String(100), nullable=False, default="sla_monitor_job")
    notification_sent = Column(Boolean,     nullable=False, default=False)
    audit_logged      = Column(Boolean,     nullable=False, default=False)
    created_at        = Column(DateTime,    nullable=False, default=datetime.utcnow)
