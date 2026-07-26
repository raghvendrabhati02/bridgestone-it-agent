"""
ticket_orchestrator.py
─────────────────────────────────────────────────────────────────────────────
Single responsibility: create a ticket from a conversation session.

FIXED: Now delegates to ticket_service.create_ticket() which handles:
  • Sequential INC/REQ ID generation
  • ITSM classification (INCIDENT vs SERVICE_REQUEST)
  • Database persistence
  • WAITING_MANAGER status for service requests
  • SLA calculation and assignment
  • Notifications to employee and manager
  • RBAC audit log

Design contract:
  • Retrieves issue description from conversation history (first user turn).
  • Delegates to ticket_service.create_ticket().
  • Never raises — returns an empty dict on failure so callers can handle gracefully.
"""

from __future__ import annotations

import logging
import traceback
from typing import TYPE_CHECKING, Optional

import app.services.conversation_memory as memory

if TYPE_CHECKING:
    from app.services.conversation_service import SessionState

logger = logging.getLogger("it-agent-backend")


class TicketOrchestrator:
    """Orchestrates ticket creation from a conversation session."""

    def create(
        self, state: "SessionState", username: Optional[str] = None
    ) -> dict:
        """
        Create a ticket for the current session's issue.

        Delegates to ticket_service.create_ticket() to ensure:
          - Database persistence
          - Correct INC/REQ ID generation
          - ITSM classification (INCIDENT vs SERVICE_REQUEST)
          - WAITING_MANAGER status for service requests
          - SLA and notification handling

        Returns the full ticket details dict, or {"error": True} on failure.
        """
        from app.services.ticket_service import create_ticket
        import time, uuid
        from app.core.logging_context import correlation_id_ctx
        t_start = time.monotonic()
        corr_id = correlation_id_ctx.get()
        if not corr_id:
            corr_id = f"corr-{uuid.uuid4().hex[:8]}"
            correlation_id_ctx.set(corr_id)

        logger.info(
            ">>> ENTRY [TicketOrchestrator.create] | Correlation ID: %s | session_id=%s, username=%s, category=%s, phase=%s",
            corr_id,
            state.session_id,
            username,
            state.category,
            getattr(state.phase, 'value', str(state.phase)),
        )

        # Build issue description & intelligent ticket summary from conversation history and state
        hist = memory.get_history(state.session_id) or []

        # Generate intelligent, grounded TicketSummary via TicketSummaryService
        from app.services.ticket_summary_service import generate_ticket_summary
        summary = generate_ticket_summary(
            conversation_history=hist,
            troubleshooting_state=state,
        )

        logger.info(
            "\n===== STAGE 1: TICKET SUMMARY =====\n"
            "Source           : %s\n"
            "Short Description: %s\n"
            "Description      : %.150s...\n"
            "===================================",
            summary.source,
            summary.short_description,
            summary.description,
        )

        # Run ClassificationService on TicketSummary.description as canonical input
        from app.services.classification_service import ClassificationService
        from app.models.classification_models import ClassificationRequest

        classifier = ClassificationService()
        cls_req = ClassificationRequest(
            description=summary.description or summary.short_description,
            category_hint=None,
        )
        classification = classifier.classify(cls_req)

        logger.info(
            "\n===== STAGE 2: CLASSIFICATION RESULT =====\n"
            "u_type          : %s\n"
            "category        : %s\n"
            "subcategory     : %s\n"
            "assignment_group: %s\n"
            "confidence      : %.2f\n"
            "reasoning       : %s\n"
            "==========================================",
            classification.u_type,
            classification.category,
            classification.subcategory,
            classification.assignment_group,
            classification.confidence,
            classification.reasoning,
        )

        # Generate fully-enriched IncidentMetadata using classification as primary source of truth
        from app.services.incident_enrichment_service import IncidentEnrichmentService
        enrichment_service = IncidentEnrichmentService()
        incident_metadata = enrichment_service.enrich(
            category=classification.category,
            classification=classification,
            troubleshooting_state=state,
        )

        logger.info(
            "\n===== STAGE 3: ENRICHMENT RESULT (IncidentMetadata) =====\n"
            "category        : %s\n"
            "subcategory     : %s\n"
            "assignment_group: %s\n"
            "impact          : %d\n"
            "urgency         : %d\n"
            "priority        : %d (%s)\n"
            "cmdb_ci         : %s\n"
            "incident_type   : %s\n"
            "=========================================================",
            incident_metadata.category,
            incident_metadata.subcategory,
            incident_metadata.assignment_group,
            incident_metadata.impact,
            incident_metadata.urgency,
            incident_metadata.priority,
            incident_metadata.priority_label,
            incident_metadata.configuration_item,
            incident_metadata.incident_type,
        )

        try:
            ticket = create_ticket(
                category=incident_metadata.category,
                issue_description=summary.description,
                created_by=username,
                short_description=summary.short_description,
                description=summary.description,
                incident_metadata=incident_metadata,
            )
            elapsed_ms = int((time.monotonic() - t_start) * 1000)

            logger.info(
                "<<< EXIT [TicketOrchestrator.create] | Correlation ID: %s | Elapsed: %dms | ticket_id=%s, request_type=%s, "
                "status=%s, servicenow_number=%s, servicenow_id=%s, error=%s",
                corr_id,
                elapsed_ms,
                ticket.get("ticket_id"),
                ticket.get("request_type"),
                ticket.get("status"),
                ticket.get("servicenow_number"),
                ticket.get("servicenow_id"),
                ticket.get("error"),
            )
            return ticket

        except Exception as exc:
            elapsed_ms = int((time.monotonic() - t_start) * 1000)
            logger.error(
                "!!! EXCEPTION [TicketOrchestrator.create] | Correlation ID: %s | Elapsed: %dms | Error: %s\n%s",
                corr_id,
                elapsed_ms,
                exc,
                traceback.format_exc(),
            )
            return {
                "error": True,
                "message": (
                    "I am sorry, but the ticketing system is currently unavailable. "
                    "Please try again later, or contact the IT Helpdesk directly."
                ),
            }
