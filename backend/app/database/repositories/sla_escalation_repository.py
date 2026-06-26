"""
SLA Escalation Repository
=========================
Handles persistence and retrieval of SlaEscalationHistory records.

Each row represents one escalation level (1/2/3) being triggered for a ticket.
Deduplication is enforced via has_level() before any new insert.
"""

from datetime import datetime
from typing import List, Optional

from sqlalchemy.orm import Session

from app.database.models.sla_escalation_history import SlaEscalationHistory


class SlaEscalationRepository:
    def __init__(self, db: Session):
        self.db = db

    # ── Write operations ─────────────────────────────────────────────────────

    def save(
        self,
        ticket_id: str,
        level: int,
        reason: str,
        triggered_by: str = "sla_monitor_job",
        notification_sent: bool = False,
        audit_logged: bool = False,
    ) -> SlaEscalationHistory:
        """
        Persists a new SlaEscalationHistory row.

        Callers should call has_level() first to prevent duplicates; this
        method does NOT enforce uniqueness itself.
        """
        record = SlaEscalationHistory(
            ticket_id=ticket_id,
            level=level,
            reason=reason,
            triggered_by=triggered_by,
            notification_sent=notification_sent,
            audit_logged=audit_logged,
            created_at=datetime.utcnow(),
        )
        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)
        return record

    # ── Read operations ──────────────────────────────────────────────────────

    def has_level(self, ticket_id: str, level: int) -> bool:
        """
        Returns True if an escalation record already exists for
        (ticket_id, level), preventing duplicate escalation entries.
        """
        return (
            self.db.query(SlaEscalationHistory)
            .filter(
                SlaEscalationHistory.ticket_id == ticket_id,
                SlaEscalationHistory.level == level,
            )
            .first()
            is not None
        )

    def get_by_ticket(self, ticket_id: str) -> List[SlaEscalationHistory]:
        """Returns all escalation records for a specific ticket, ordered by level."""
        return (
            self.db.query(SlaEscalationHistory)
            .filter(SlaEscalationHistory.ticket_id == ticket_id)
            .order_by(SlaEscalationHistory.level.asc())
            .all()
        )

    def get_all(self) -> List[SlaEscalationHistory]:
        """Returns all escalation records ordered newest-first."""
        return (
            self.db.query(SlaEscalationHistory)
            .order_by(SlaEscalationHistory.created_at.desc())
            .all()
        )

    def get_max_level(self, ticket_id: str) -> int:
        """
        Returns the highest escalation level already recorded for a ticket.
        Returns 0 if no escalation has occurred.
        """
        records = self.get_by_ticket(ticket_id)
        if not records:
            return 0
        return max(r.level for r in records)
