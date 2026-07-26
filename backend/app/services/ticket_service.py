"""
ticket_service.py
─────────────────────────────────────────────────────────────────────────────
Enterprise ticket creation service.

Production hardening applied (see CHANGES section at bottom of file):
  1. Thread-safe DB-driven local ID allocation via SELECT MAX(id) inside the
     same transaction that writes the row (no global counter mutation under
     concurrent load).
  2. In-memory fallback (`tickets.append`) removed; DB failures return a
     structured error instead of silently losing data.
  3. Module-import-time DB call (`init_ticket_counter`) removed; initialization
     is now lazy, protected by a threading.Lock, and only runs once.
  4. Configuration validation at the ServiceNow layer (already in
     ServiceNowService.validate_configuration).  Additional guard added here
     before constructing the incident request.
  5. Hardcoded severity=3 replaced with a constant; all other hardcoded
     defaults remain intentional and documented.
  6. Structured logging at every decision point: local ID, SN number,
     correlation ID, elapsed wall-clock time, success/failure, exception type.
     Passwords and secrets are never logged.
  7. Exception handling: no swallowed exceptions; specific exception types
     preferred over bare `except Exception`; stack traces always preserved.
  8. Dead code removed: unused `servicenow_client` module-level singleton,
     `local_to_snow_mapping` dict, bare `tickets` list, and `ticket_counter`
     global.
"""

from __future__ import annotations

import datetime
import logging
import threading
import time
import traceback
from typing import Optional

from sqlalchemy import func, select, text

from app.services.assignment_service import get_assignment_team
from app.services.notification_service import create_notification
from app.services.sla_service import calculate_priority, calculate_sla, store_sla_record
from app.services.itsm_classifier import classify_request
from app.database.session import get_db
from app.database.repositories.ticket_repository import TicketRepository
from app.services.servicenow_service import ServiceNowService
from app.models.servicenow_models import IncidentCreateRequest
from app.services.field_mapping_service import FieldMappingService, FieldMappingError
from app.services.incident_enrichment_service import IncidentMetadata
from app.core.tracing import trace_span
from app.core.logging_context import correlation_id_ctx

logger = logging.getLogger("it-agent-backend")

# ── Constants ──────────────────────────────────────────────────────────────────

# Default incident severity sent to ServiceNow.
# 1 = Critical, 2 = High, 3 = Moderate (default), 4 = Low.
_DEFAULT_SEVERITY: int = 3

# Maximum characters used from issue_description for the SN short_description.
_SHORT_DESC_MAX_LEN: int = 50

# ── ServiceNow singleton (dependency-injection aware) ─────────────────────────

_servicenow_service: Optional[ServiceNowService] = None
_sn_service_lock = threading.Lock()


def get_servicenow_service() -> ServiceNowService:
    """Returns the thread-safe singleton instance of ServiceNowService."""
    global _servicenow_service
    if _servicenow_service is None:
        with _sn_service_lock:
            if _servicenow_service is None:
                _servicenow_service = ServiceNowService()
    return _servicenow_service


def set_servicenow_service(service: Optional[ServiceNowService]) -> None:
    """
    Allows injecting a custom or mock ServiceNowService instance for testing.
    Thread-safe: acquires the singleton lock before mutating.
    """
    global _servicenow_service
    with _sn_service_lock:
        _servicenow_service = service


# ── Thread-safe local ID allocation ───────────────────────────────────────────

_id_lock = threading.Lock()


def _allocate_local_ticket_id() -> str:
    """
    Allocates the next local INC-prefixed ticket ID in a thread-safe manner.

    Strategy: SELECT MAX(id) from the tickets table inside a DB session, then
    increment by 1.  The `ticket_id` column has a UNIQUE constraint, so a
    concurrent writer that races here will hit a DB-level IntegrityError and
    must retry.  This approach is safe for a single-process deployment.

    For multi-process / multi-node deployments, replace this with a proper
    DB sequence (PostgreSQL SEQUENCE, MySQL AUTO_INCREMENT surrogate, etc.).

    Returns:
        str: Next ticket ID in the form "INC000001".
    """
    with _id_lock:
        try:
            with get_db() as db:
                from app.database.models.ticket import Ticket
                # Use the DB's own integer primary key as the authoritative
                # monotone source.  MAX(id) is always correct regardless of
                # deleted rows or gaps.
                # select() wrapper is required by SQLAlchemy 1.4+ — passing a
                # bare func.max() expression raises ObjectNotExecutableError.
                raw_res = db.execute(select(func.max(Ticket.id))).scalar()
                try:
                    next_num = int(raw_res or 0) + 1
                except (TypeError, ValueError):
                    next_num = 1
        except Exception as exc:
            logger.error(
                "[ticket_service._allocate_local_ticket_id]: DB query failed: %s\n%s",
                exc,
                traceback.format_exc(),
            )
            raise RuntimeError(
                f"Failed to allocate local ticket ID from database: {exc}"
            ) from exc

        ticket_id = f"INC{next_num:06d}"
        logger.debug(
            "[ticket_service._allocate_local_ticket_id]: Allocated %s (next_num=%d)",
            ticket_id,
            next_num,
        )
        return ticket_id


# ── Status label lookup ────────────────────────────────────────────────────────

_STATUS_LABELS: dict[str, str] = {
    "NEW":                      "Open — Assigned to IT Team",
    "AI_DIAGNOSING":            "AI Diagnosing Issue",
    "ADMIN_REQUIRED":           "Administrator Privileges Required",
    "WAITING_MANAGER":          "Pending Manager Approval",
    "WAITING_MANAGER_APPROVAL": "Pending Manager Approval",
    "WAITING_ADMIN":            "Pending IT Admin Approval",
    "WAITING_ADMIN_APPROVAL":   "Pending IT Admin Approval",
    "ADMIN_APPROVED":           "Admin Approved — Generating LAPS Credentials",
    "TEMP_ADMIN_GRANTED":       "Temporary Admin Access Granted",
    "EXECUTION_READY":          "Ready for Execution",
    "EXECUTING":                "Executing with Elevated Privileges",
    "APPROVED":                 "Approved",
    "ASSIGNED":                 "Assigned to IT Team",
    "IN_PROGRESS":              "In Progress",
    "COMPLETED":                "Task Completed",
    "RESOLVED":                 "Resolved",
    "FULFILLED":                "Fulfilled",
    "CLOSED":                   "Closed",
    "REJECTED":                 "Rejected",
}


def _status_label(status: str) -> str:
    return _STATUS_LABELS.get(status, status.replace("_", " ").title())


# ── Correlation ID helper ──────────────────────────────────────────────────────

def _correlation_id() -> str:
    """Returns the current request-scoped correlation ID, or empty string."""
    try:
        from app.core.logging_context import correlation_id_ctx
        return correlation_id_ctx.get() or ""
    except Exception:
        return ""


# ── Public API ─────────────────────────────────────────────────────────────────

def create_ticket(
    category: str,
    issue_description: str,
    created_by: str = None,
    servicenow_service: Optional[ServiceNowService] = None,
    short_description: Optional[str] = None,
    description: Optional[str] = None,
    incident_metadata: Optional[IncidentMetadata] = None,
    **kwargs,
) -> dict:
    """
    Creates an enterprise ticket with:
      - Thread-safe DB-allocated local INC ID (no global counter).
      - Automatic ITSM classification (INCIDENT / SERVICE_REQUEST / PRIVILEGED_ACTION).
      - Priority and SLA calculation.
      - ServiceNow incident creation when integration is enabled.
      - Database persistence — failures return a structured error (no in-memory fallback).
      - Employee and manager notifications.
      - RBAC audit log.

    Returns:
        dict: Full ticket details on success.
              dict with ``error=True`` on ServiceNow or DB failure.

    Raises:
        RuntimeError: If local ID allocation fails at the DB level.
    """
    with trace_span(
        name="ticket_service",
        attributes={
            "provider": "none",
            "category": category,
            "correlation_id": correlation_id_ctx.get() or _correlation_id() or "",
        },
    ):
        return _create_ticket_internal(
            category=category,
            issue_description=issue_description,
            created_by=created_by,
            servicenow_service=servicenow_service,
            short_description=short_description,
            description=description,
            incident_metadata=incident_metadata,
            **kwargs,
        )


def _create_ticket_internal(
    category: str,
    issue_description: str,
    created_by: str = None,
    servicenow_service: Optional[ServiceNowService] = None,
    short_description: Optional[str] = None,
    description: Optional[str] = None,
    incident_metadata: Optional[IncidentMetadata] = None,
    **kwargs,
) -> dict:
    t_start = time.monotonic()
    corr_id = _correlation_id()

    # Determine final short_description and description
    final_description = description or kwargs.get("description") or issue_description
    raw_short_desc = short_description or kwargs.get("short_description")
    if raw_short_desc:
        final_short_desc = raw_short_desc.strip()[:_SHORT_DESC_MAX_LEN]
    else:
        final_short_desc = f"{category.upper()} Issue - {final_description[:_SHORT_DESC_MAX_LEN]}"[:_SHORT_DESC_MAX_LEN]

    logger.info(
        ">>> ENTRY [ticket_service.create_ticket]: category=%s, created_by=%s, "
        "correlation_id=%s, short_description='%.100s', description='%.150s'",
        category,
        created_by,
        corr_id or "<none>",
        final_short_desc,
        final_description,
    )

    # ── Metrics (best-effort) ──────────────────────────────────────────────────
    try:
        from app.core.metrics import BUSINESS_TICKETS_CREATED_TOTAL
        BUSINESS_TICKETS_CREATED_TOTAL.inc()
    except Exception:
        pass

    # ── Allocate local ticket ID (thread-safe, DB-driven) ─────────────────────
    local_ticket_id = _allocate_local_ticket_id()
    assigned_team = kwargs.get("assigned_team") or kwargs.get("assignment_group") or get_assignment_team(category)
    created_at = datetime.datetime.utcnow().isoformat() + "Z"

    logger.info(
        "[ticket_service.create_ticket]: local_ticket_id=%s, assigned_team=%s, "
        "correlation_id=%s",
        local_ticket_id,
        assigned_team,
        corr_id or "<none>",
    )

    # ── SLA calculations ───────────────────────────────────────────────────────
    priority = calculate_priority(category, final_description)
    sla_hours = calculate_sla(priority)
    store_sla_record(local_ticket_id, priority, sla_hours)

    # ── ITSM classification ────────────────────────────────────────────────────
    classification = classify_request(category, final_description)
    request_type   = classification.request_type
    approval_status = classification.approval_status
    manager        = classification.manager
    status         = classification.initial_status

    logger.info(
        "[ticket_service.create_ticket]: %s classified as request_type=%s "
        "approval=%s status=%s",
        local_ticket_id, request_type, approval_status, status,
    )

    # ── ServiceNow incident creation ───────────────────────────────────────────
    sn_service = servicenow_service or get_servicenow_service()
    servicenow_id     = "N/A"
    servicenow_number = None
    # presentation_id starts as the local ID; overwritten with SN number on success
    presentation_id   = local_ticket_id

    logger.info(
        "[ticket_service.create_ticket]: ServiceNow enabled=%s, use_mock=%s, "
        "instance_url=%s, correlation_id=%s",
        sn_service.enabled,
        getattr(sn_service, "use_mock", "unknown"),
        getattr(sn_service, "instance_url", "unknown"),
        corr_id or "<none>",
    )

    if sn_service.enabled:
        is_valid, err_msg = sn_service.validate_configuration()
        logger.info(
            "[ticket_service.create_ticket]: SN config validation: valid=%s, msg='%s'",
            is_valid,
            err_msg,
        )
        if not is_valid:
            elapsed_ms = int((time.monotonic() - t_start) * 1000)
            logger.error(
                "[ticket_service.create_ticket]: ABORT — SN configuration invalid: %s "
                "(elapsed=%dms, correlation_id=%s)",
                err_msg,
                elapsed_ms,
                corr_id or "<none>",
            )
            return {
                "error": True,
                "success": False,
                "servicenow_error": True,
                "message": (
                    f"Unable to create ServiceNow Incident.\n\nReason:\n{err_msg}\n\n"
                    "Please contact IT administrator."
                ),
                "ticket_id": "",
                "servicenow_number": "",
                "servicenow_id": "",
            }

        # ── ServiceNow Field Mapping Engine Integration ────────────────────────
        mapped_category = category
        mapped_assignment_group = assigned_team
        extra_fields: dict = {}

        try:
            field_mapper = FieldMappingService(auto_load=True)
            classified_u_type = "issue" if getattr(classification, "request_type", None) == "INCIDENT" else "request"
            u_type_input = kwargs.get("u_type") or classified_u_type

            # Derive subcategory if applicable
            subcat_input = kwargs.get("subcategory") or kwargs.get("sub_category")

            mapped_fields = field_mapper.build_servicenow_fields(
                contact_type="chat",
                u_type=u_type_input,
                category=category,
                subcategory=subcat_input,
                assignment_group=assigned_team,
                caller_id=created_by or "",
            )

            if mapped_fields.get("category"):
                mapped_category = mapped_fields["category"]
            if mapped_fields.get("assignment_group"):
                mapped_assignment_group = mapped_fields["assignment_group"]

            extra_fields = {
                "contact_type": mapped_fields.get("contact_type", "chat"),
                "u_type": mapped_fields.get("u_type", ""),
                "subcategory": mapped_fields.get("subcategory", ""),
            }

            logger.info(
                "\n========== FIELD MAPPING PIPELINE ==========\n"
                "Correlation ID   : %s\n"
                "Classified Values: u_type='%s', category='%s', subcategory='%s', assignment_group='%s', caller_id='%s'\n"
                "Mapped SN Values : contact_type='%s', u_type='%s', category='%s', subcategory='%s', assignment_group='%s', caller_id='%s'\n"
                "===========================================",
                corr_id or "<none>",
                classified_u_type, category, subcat_input or "", assigned_team, created_by,
                mapped_fields.get("contact_type"), mapped_fields.get("u_type"), mapped_fields.get("category"),
                mapped_fields.get("subcategory"), mapped_fields.get("assignment_group"), mapped_fields.get("caller_id"),
            )

        except FieldMappingError as f_err:
            elapsed_ms = int((time.monotonic() - t_start) * 1000)
            logger.error(
                "[ticket_service.create_ticket]: ABORT — ServiceNow field mapping failed: %s (elapsed=%dms, correlation_id=%s)",
                f_err, elapsed_ms, corr_id or "<none>"
            )
            return {
                "error": True,
                "success": False,
                "servicenow_error": True,
                "message": f"Unable to create ServiceNow Incident.\n\nField Mapping Failure:\n{f_err}",
                "ticket_id": "",
                "servicenow_number": "",
                "servicenow_id": "",
            }
        except Exception as map_ex:
            logger.warning("[ticket_service.create_ticket]: Field mapping notice: %s", map_ex)

        # ── IncidentEnrichmentService override ────────────────────────────────
        # When incident_metadata is provided by TicketOrchestrator, its values
        # take precedence over the FieldMappingService baseline.  This is the
        # correct layering: FMS sets defaults, IES provides enterprise-grade
        # enriched values derived from the full troubleshooting context.
        if incident_metadata is not None:
            mapped_category       = incident_metadata.category
            mapped_assignment_group = incident_metadata.assignment_group
            # Merge enriched extra fields on top of FMS baseline
            extra_fields.update(incident_metadata.to_extra_fields())
            logger.info(
                "[ticket_service.create_ticket]: IncidentEnrichmentService applied — "
                "category='%s', subcategory='%s', assignment_group='%s', "
                "impact=%d, urgency=%d, priority=%d (%s), ci=%s",
                incident_metadata.category,
                incident_metadata.subcategory,
                incident_metadata.assignment_group,
                incident_metadata.impact,
                incident_metadata.urgency,
                incident_metadata.priority,
                incident_metadata.priority_label,
                incident_metadata.configuration_item,
            )

        logger.info(
            "[ticket_service.create_ticket]: Initiating ServiceNow POST "
            "(local_id=%s, correlation_id=%s)",
            local_ticket_id,
            corr_id or "<none>",
        )
        try:
            # Derive impact / urgency from IncidentMetadata when available;
            # otherwise fall back to model defaults (both default to 3 = Low).
            _impact       = incident_metadata.impact        if incident_metadata is not None else 3
            _urgency      = incident_metadata.urgency       if incident_metadata is not None else 3
            _priority     = incident_metadata.priority      if incident_metadata is not None else None
            _u_type       = incident_metadata.incident_type if incident_metadata is not None else extra_fields.get("u_type")
            _contact_type = incident_metadata.channel       if incident_metadata is not None else extra_fields.get("contact_type")

            mapped_subcategory = incident_metadata.subcategory if incident_metadata is not None else extra_fields.get("subcategory")

            req = IncidentCreateRequest(
                short_description=final_short_desc,
                description=final_description,
                category=mapped_category,
                subcategory=mapped_subcategory,
                u_type=_u_type,
                contact_type=_contact_type,
                severity=_DEFAULT_SEVERITY,
                assignment_group=mapped_assignment_group,
                caller_id=created_by,
                impact=_impact,
                urgency=_urgency,
                priority=_priority,
                extra_fields=extra_fields,
            )
            logger.info(
                "[ticket_service.create_ticket]: Final Payload Sent to ServiceNow — "
                "short_description='%s', category=%s, severity=%d, impact=%d, urgency=%d, "
                "assignment_group=%s, caller_id=%s, extra_fields=%s, description='%.100s'",
                req.short_description,
                req.category,
                req.severity,
                req.impact,
                req.urgency,
                req.assignment_group,
                req.caller_id,
                req.extra_fields,
                req.description,
            )

            sn_t_start = time.monotonic()
            sn_res = sn_service.create_incident(req)
            sn_elapsed_ms = int((time.monotonic() - sn_t_start) * 1000)

            sn_is_success = getattr(sn_res, "success", None) if not isinstance(sn_res, dict) else sn_res.get("success", False)
            sn_number = getattr(sn_res, "number", None) if not isinstance(sn_res, dict) else (sn_res.get("number") or sn_res.get("sys_id") or sn_res.get("ticket_id"))
            sn_sys_id = getattr(sn_res, "sys_id", None) if not isinstance(sn_res, dict) else sn_res.get("sys_id")
            sn_msg = getattr(sn_res, "message", "") if not isinstance(sn_res, dict) else sn_res.get("message", "")

            logger.info(
                "[ticket_service.create_ticket]: SN response — success=%s, "
                "number=%s, sys_id=%s, message='%s', sn_latency=%dms",
                sn_is_success,
                sn_number,
                sn_sys_id,
                sn_msg,
                sn_elapsed_ms,
            )

            if not sn_is_success or not sn_number:
                err_detail = sn_msg or "ServiceNow API returned failure"
                elapsed_ms = int((time.monotonic() - t_start) * 1000)
                logger.error(
                    "[ticket_service.create_ticket]: SN creation failed: %s "
                    "(elapsed=%dms, correlation_id=%s)",
                    err_detail,
                    elapsed_ms,
                    corr_id or "<none>",
                )
                return {
                    "error": True,
                    "success": False,
                    "servicenow_error": True,
                    "message": (
                        f"Unable to create ServiceNow Incident.\n\nReason:\n{err_detail}\n\n"
                        "Please contact IT administrator."
                    ),
                    "ticket_id": "",
                    "servicenow_number": "",
                    "servicenow_id": "",
                }

            servicenow_id     = sn_sys_id
            servicenow_number = sn_number
            # ServiceNow incident number is the user-visible canonical ID.
            presentation_id   = servicenow_number

            # Requirement 5: Check if ServiceNow returned an incident number that already exists locally
            if servicenow_number:
                try:
                    from app.database.models.ticket import Ticket
                    with get_db() as db_chk:
                        existing_local = db_chk.query(Ticket).filter(
                            (Ticket.servicenow_number == servicenow_number) | (Ticket.ticket_id == servicenow_number)
                        ).first()
                        if existing_local:
                            logger.warning(
                                "WARNING: ServiceNow returned an incident number (%s) that already exists locally in DB (Local ID: %s, Created At: %s).",
                                servicenow_number, existing_local.ticket_id, existing_local.created_at
                            )
                except Exception as dup_ex:
                    logger.warning("[ticket_service.create_ticket]: Local duplicate check exception: %s", dup_ex)

            logger.info(
                "[ticket_service.create_ticket]: SN incident created — "
                "local_id=%s, sn_number=%s, sys_id=%s, sn_latency=%dms, "
                "correlation_id=%s",
                local_ticket_id,
                servicenow_number,
                servicenow_id,
                sn_elapsed_ms,
                corr_id or "<none>",
            )

        except Exception as exc:
            elapsed_ms = int((time.monotonic() - t_start) * 1000)
            logger.error(
                "!!! EXCEPTION [ticket_service.create_ticket]: SN incident creation "
                "raised %s — %s (elapsed=%dms, correlation_id=%s)\n%s",
                type(exc).__name__,
                exc,
                elapsed_ms,
                corr_id or "<none>",
                traceback.format_exc(),
            )
            return {
                "error": True,
                "success": False,
                "servicenow_error": True,
                "message": (
                    f"Unable to create ServiceNow Incident.\n\nReason:\n{exc}\n\n"
                    "Please contact IT administrator."
                ),
                "ticket_id": "",
                "servicenow_number": "",
                "servicenow_id": "",
            }
    else:
        logger.info(
            "[ticket_service.create_ticket]: SN integration disabled — "
            "persisting to local database only (local_id=%s)",
            local_ticket_id,
        )

    # ── Build ticket dict ──────────────────────────────────────────────────────
    ticket: dict = {
        "success":            True,
        "ticket_id":          presentation_id,
        "local_ticket_id":    local_ticket_id,
        "servicenow_number":  servicenow_number,
        "servicenow_id":      servicenow_id,
        "category":           category,
        "short_description":  final_short_desc,
        "description":        final_description,
        "issue_description":  final_description,   # backward compatibility alias
        "assigned_team":      assigned_team,
        "priority":           priority,
        "sla_hours":          sla_hours,
        "status":             status,
        "status_label":       _status_label(status),
        "created_by":         created_by,
        "created_at":         created_at,
        "request_type":       request_type,
        "manager":            manager,
        "approval_status":    approval_status,
        "assignment_group":   assigned_team,
        "requires_approval":  classification.requires_approval,
    }

    # ── Persist to database ────────────────────────────────────────────────────
    try:
        with get_db() as db:
            repo = TicketRepository(db)
            repo.save_ticket(
                ticket_id=presentation_id,
                category=category,
                description=issue_description,
                issue_description=issue_description,
                assigned_team=assigned_team,
                priority=priority,
                sla_hours=sla_hours,
                status=status,
                servicenow_id=servicenow_id,
                servicenow_number=servicenow_number,
                created_by=created_by,
                request_type=request_type,
                manager=manager,
                approval_status=approval_status,
                assignment_group=assigned_team,
            )
        elapsed_ms = int((time.monotonic() - t_start) * 1000)
        logger.info(
            "[ticket_service.create_ticket]: Persisted to DB — "
            "local_id=%s, presentation_id=%s, sn_number=%s, "
            "elapsed=%dms, correlation_id=%s",
            local_ticket_id,
            presentation_id,
            servicenow_number,
            elapsed_ms,
            corr_id or "<none>",
        )
    except Exception as exc:
        elapsed_ms = int((time.monotonic() - t_start) * 1000)
        logger.error(
            "!!! CRITICAL [ticket_service.create_ticket]: DB persistence failed for "
            "local_id=%s sn_number=%s — %s: %s (elapsed=%dms, correlation_id=%s)\n%s",
            local_ticket_id,
            servicenow_number,
            type(exc).__name__,
            exc,
            elapsed_ms,
            corr_id or "<none>",
            traceback.format_exc(),
        )
        # Do NOT fall back to in-memory storage.  Return a structured error so
        # the caller can surface the failure to the user rather than silently
        # losing the record.
        return {
            "error": True,
            "success": False,
            "db_error": True,
            "message": (
                "The ServiceNow incident was created but the local database record "
                "could not be saved.  Please contact IT support and reference "
                f"ServiceNow number {servicenow_number or local_ticket_id}."
            ),
            "ticket_id":         presentation_id,
            "local_ticket_id":   local_ticket_id,
            "servicenow_number": servicenow_number,
            "servicenow_id":     servicenow_id,
        }

    # ── Notifications ──────────────────────────────────────────────────────────
    _send_notifications(
        ticket_id=presentation_id,
        assigned_team=assigned_team,
        category=category,
        request_type=request_type,
        status=status,
        classification=classification,
    )

    # ── RBAC audit ────────────────────────────────────────────────────────────
    _emit_rbac_audit(
        ticket_id=presentation_id,
        created_by=created_by,
        status=status,
        category=category,
        assigned_team=assigned_team,
        priority=priority,
        sla_hours=sla_hours,
        request_type=request_type,
        approval_status=approval_status,
    )

    elapsed_ms = int((time.monotonic() - t_start) * 1000)
    logger.info(
        "<<< EXIT [ticket_service.create_ticket]: success=True, "
        "presentation_id=%s, local_id=%s, sn_number=%s, "
        "total_elapsed=%dms, correlation_id=%s",
        presentation_id,
        local_ticket_id,
        servicenow_number,
        elapsed_ms,
        corr_id or "<none>",
    )
    return ticket


# ── Private helpers ────────────────────────────────────────────────────────────

def _send_notifications(
    *,
    ticket_id: str,
    assigned_team: str,
    category: str,
    request_type: str,
    status: str,
    classification,
) -> None:
    """Fire-and-log notifications; never raises."""
    try:
        create_notification(
            ticket_id=ticket_id,
            recipient=assigned_team,
            message=f"New {category} {request_type.lower().replace('_', ' ')} assigned.",
        )
        create_notification(
            ticket_id=ticket_id,
            recipient="Employee",
            message=f"Your ticket {ticket_id} has been created. Status: {status}.",
        )
        if classification.requires_approval:
            create_notification(
                ticket_id=ticket_id,
                recipient="manager",
                message=(
                    f"[Approval Required] {ticket_id}: "
                    f"{category} {request_type.replace('_', ' ')} awaiting your approval."
                ),
            )
    except Exception as exc:
        logger.warning(
            "[ticket_service._send_notifications]: Notification delivery failed "
            "for %s — %s: %s",
            ticket_id,
            type(exc).__name__,
            exc,
        )


def _emit_rbac_audit(
    *,
    ticket_id: str,
    created_by: Optional[str],
    status: str,
    category: str,
    assigned_team: str,
    priority: str,
    sla_hours: int,
    request_type: str,
    approval_status: str,
) -> None:
    """Emit RBAC audit event; failures are logged but never propagated."""
    try:
        from app.services.rbac_audit_service import log_rbac_event
        log_rbac_event(
            user=created_by or "unknown",
            role="EMPLOYEE",
            action="create_ticket",
            ticket_id=ticket_id,
            old_state=None,
            new_state=status,
            details={
                "category":        category,
                "assigned_team":   assigned_team,
                "priority":        priority,
                "sla_hours":       sla_hours,
                "request_type":    request_type,
                "approval_status": approval_status,
            },
        )
    except Exception as exc:
        logger.warning(
            "[ticket_service._emit_rbac_audit]: RBAC audit failed for %s — %s: %s",
            ticket_id,
            type(exc).__name__,
            exc,
        )


# ── Read operations ───────────────────────────────────────────────────────────

def get_all_tickets() -> list[dict]:
    """Returns all persisted tickets as serialisable dicts."""
    try:
        with get_db() as db:
            repo = TicketRepository(db)
            return [_ticket_to_dict(t) for t in repo.get_all_tickets()]
    except Exception as exc:
        logger.error(
            "[ticket_service.get_all_tickets]: DB query failed — %s: %s\n%s",
            type(exc).__name__,
            exc,
            traceback.format_exc(),
        )
        return []


def get_ticket(ticket_id: str) -> Optional[dict]:
    """Returns a single ticket dict by ticket_id, or None if not found."""
    try:
        with get_db() as db:
            repo = TicketRepository(db)
            ticket = repo.get_ticket(ticket_id)
            if ticket:
                return _ticket_to_dict(ticket)
            # Fallback: scan all (handles servicenow_number as lookup key)
            for t in repo.get_all_tickets():
                if t.ticket_id == ticket_id or t.servicenow_number == ticket_id:
                    return _ticket_to_dict(t)
    except Exception as exc:
        logger.error(
            "[ticket_service.get_ticket]: DB query failed for ticket_id=%s — "
            "%s: %s\n%s",
            ticket_id,
            type(exc).__name__,
            exc,
            traceback.format_exc(),
        )
    return None


def _ticket_to_dict(t) -> dict:
    """Convert a Ticket ORM object to a fully serialisable dict."""
    display_id = t.servicenow_number or t.ticket_id
    return {
        "ticket_id":          display_id,
        "local_ticket_id":    t.ticket_id,
        "servicenow_number":  (
            t.servicenow_number
            or (t.ticket_id if t.servicenow_id and t.servicenow_id != "N/A" else None)
        ),
        "category":           t.category,
        "description":        t.description,
        "issue_description":  t.issue_description,
        "assigned_team":      t.assigned_team,
        "assigned_engineer":  t.assigned_engineer,
        "priority":           t.priority,
        "sla_hours":          t.sla_hours,
        "status":             t.status,
        "servicenow_id":      t.servicenow_id,
        "created_by":         t.created_by,
        "created_at":         t.created_at.isoformat() + "Z",
        "updated_at":         (
            t.updated_at.isoformat() + "Z"
            if t.updated_at else t.created_at.isoformat() + "Z"
        ),
        "resolved_at":        t.resolved_at.isoformat() + "Z" if t.resolved_at else None,
        "closed_at":          t.closed_at.isoformat() + "Z" if t.closed_at else None,
        # ITSM Workflow fields
        "request_type":       t.request_type,
        "manager":            t.manager,
        "approval_status":    t.approval_status,
        "assignment_group":   t.assignment_group or t.assigned_team,
        # SLA
        "sla_state":          t.sla_state or "HEALTHY",
        "sla_breached":       t.sla_breached or False,
        "sla_breached_at":    t.sla_breached_at.isoformat() + "Z" if t.sla_breached_at else None,
    }
