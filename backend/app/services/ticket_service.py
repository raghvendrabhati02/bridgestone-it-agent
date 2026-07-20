import datetime
import logging
from app.services.assignment_service import get_assignment_team
from app.services.notification_service import create_notification
from app.services.sla_service import (
    calculate_priority,
    calculate_sla,
    store_sla_record
)
from app.services.itsm_classifier import classify_request
from app.services.servicenow_client import ServiceNowClient
from app.database.session import get_db
from app.database.repositories.ticket_repository import TicketRepository

logger = logging.getLogger("it-agent-backend")

# Initialize the ServiceNow client
servicenow_client = ServiceNowClient()

# In-memory mapping database: local_ticket_id -> servicenow_id
local_to_snow_mapping = {}

# Volatile fallback list
tickets = []
ticket_counter = 0

def init_ticket_counter():
    """Initializes ticket counter from database."""
    global ticket_counter
    try:
        with get_db() as db:
            repo = TicketRepository(db)
            all_t = repo.get_all_tickets()
            max_num = 0
            for t in all_t:
                try:
                    num = int(t.ticket_id[3:])
                    if num > max_num:
                        max_num = num
                except Exception:
                    pass
            ticket_counter = max_num
            logger.info("Ticket Service: Initialized ticket counter to %d from DB", ticket_counter)
    except Exception as e:
        logger.warning("Ticket Service: Failed to initialize ticket counter from database: %s", e)

# Run initialization once at import time
init_ticket_counter()

def create_ticket(category: str, issue_description: str, created_by: str = None) -> dict:
    """
    Creates an enterprise ticket with:
      - Sequential ID (INC000001)
      - Automatic ITSM classification (INCIDENT / SERVICE_REQUEST / PRIVILEGED_ACTION)
      - Priority and SLA calculation
      - Database persistence
      - Notifications
      - RBAC audit log
    Returns full ticket details dict.
    """
    global ticket_counter
    ticket_counter += 1

    try:
        from app.core.metrics import BUSINESS_TICKETS_CREATED_TOTAL
        BUSINESS_TICKETS_CREATED_TOTAL.inc()
    except Exception:
        pass

    ticket_id = f"INC{ticket_counter:06d}"
    assigned_team = get_assignment_team(category)
    created_at = datetime.datetime.utcnow().isoformat() + "Z"

    # SLA calculations
    priority = calculate_priority(category, issue_description)
    sla_hours = calculate_sla(priority)
    store_sla_record(ticket_id, priority, sla_hours)

    # ── Automatic ITSM classification ─────────────────────────────────────
    classification = classify_request(category, issue_description)
    request_type = classification.request_type
    approval_status = classification.approval_status
    manager = classification.manager
    status = classification.initial_status

    logger.info(
        "Ticket Service: Classified %s as %s (approval=%s, status=%s)",
        ticket_id, request_type, approval_status, status
    )

    # Create ServiceNow incident using adapter client
    try:
        snow_incident = servicenow_client.create_incident(
            category=category,
            description=issue_description,
            assignment_group=assigned_team
        )
        if isinstance(snow_incident, dict) and not snow_incident.get("success", True):
            raise RuntimeError(snow_incident.get("message", "ServiceNow error"))
        servicenow_id = snow_incident.get("sys_id", "N/A")
    except Exception as e:
        logger.error("Ticket Service: Failed to create ServiceNow incident. Error: %s", e)
        servicenow_id = "N/A"

    # Human-readable status label shown to the employee
    status_label = {
        "NEW": "Open — Assigned to IT Team",
        "AI_DIAGNOSING": "AI Diagnosing Issue",
        "ADMIN_REQUIRED": "Administrator Privileges Required",
        "WAITING_MANAGER": "Pending Manager Approval",
        "WAITING_MANAGER_APPROVAL": "Pending Manager Approval",
        "WAITING_ADMIN": "Pending IT Admin Approval",
        "WAITING_ADMIN_APPROVAL": "Pending IT Admin Approval",
        "ADMIN_APPROVED": "Admin Approved — Generating LAPS Credentials",
        "TEMP_ADMIN_GRANTED": "Temporary Admin Access Granted",
        "EXECUTION_READY": "Ready for Execution",
        "EXECUTING": "Executing with Elevated Privileges",
        "APPROVED": "Approved",
        "ASSIGNED": "Assigned to IT Team",
        "IN_PROGRESS": "In Progress",
        "COMPLETED": "Task Completed",
        "RESOLVED": "Resolved",
        "FULFILLED": "Fulfilled",
        "CLOSED": "Closed",
        "REJECTED": "Rejected",
    }.get(status, status.replace("_", " ").title())

    ticket = {
        "ticket_id": ticket_id,
        "category": category,
        "description": issue_description,
        "issue_description": issue_description,  # backward compatibility
        "assigned_team": assigned_team,
        "priority": priority,
        "sla_hours": sla_hours,
        "status": status,
        "status_label": status_label,
        "servicenow_id": servicenow_id,
        "created_by": created_by,
        "created_at": created_at,
        "request_type": request_type,
        "manager": manager,
        "approval_status": approval_status,
        "assignment_group": assigned_team,
        "requires_approval": classification.requires_approval,
    }

    # Persist in Database
    try:
        with get_db() as db:
            repo = TicketRepository(db)
            repo.save_ticket(
                ticket_id=ticket_id,
                category=category,
                description=issue_description,
                issue_description=issue_description,
                assigned_team=assigned_team,
                priority=priority,
                sla_hours=sla_hours,
                status=status,
                servicenow_id=servicenow_id,
                created_by=created_by,
                request_type=request_type,
                manager=manager,
                approval_status=approval_status,
                assignment_group=assigned_team
            )
            logger.info("Ticket Service: Persisted ticket %s to database", ticket_id)
    except Exception as e:
        logger.error("Ticket Service: Failed to persist ticket to database: %s", e)
        tickets.append(ticket)

    if servicenow_id != "N/A":
        local_to_snow_mapping[ticket_id] = servicenow_id

    # Notifications
    create_notification(
        ticket_id=ticket_id,
        recipient=assigned_team,
        message=f"New {category} {request_type.lower().replace('_', ' ')} assigned."
    )
    create_notification(
        ticket_id=ticket_id,
        recipient="Employee",
        message=f"Your ticket {ticket_id} has been created. Status: {status}."
    )
    if classification.requires_approval:
        create_notification(
            ticket_id=ticket_id,
            recipient="manager",
            message=f"[Approval Required] {ticket_id}: {category} {request_type.replace('_', ' ')} awaiting your approval."
        )

    # RBAC Audit
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
                "category": category,
                "assigned_team": assigned_team,
                "priority": priority,
                "sla_hours": sla_hours,
                "request_type": request_type,
                "approval_status": approval_status,
            },
        )
    except Exception as e:
        logger.warning("Ticket Service: RBAC audit emit failed for %s: %s", ticket_id, e)

    return ticket


def get_all_tickets() -> list[dict]:
    """Returns the list of all tickets with ITSM fields."""
    try:
        with get_db() as db:
            repo = TicketRepository(db)
            db_tickets = repo.get_all_tickets()
            return [_ticket_to_dict(t) for t in db_tickets]
    except Exception as e:
        logger.error("Ticket Service: Failed to get tickets from DB: %s", e)
        return tickets


def get_ticket(ticket_id: str):
    try:
        with get_db() as db:
            repo = TicketRepository(db)
            all_t = repo.get_all_tickets()
            for t in all_t:
                if t.ticket_id == ticket_id:
                    return _ticket_to_dict(t)
    except Exception as e:
        logger.error("Ticket Service: Failed to fetch ticket %s: %s", ticket_id, e)
    return None


def _ticket_to_dict(t) -> dict:
    """Convert a Ticket ORM object to a serializable dict with all ITSM fields."""
    return {
        "ticket_id": t.ticket_id,
        "category": t.category,
        "description": t.description,
        "issue_description": t.issue_description,
        "assigned_team": t.assigned_team,
        "assigned_engineer": t.assigned_engineer,
        "priority": t.priority,
        "sla_hours": t.sla_hours,
        "status": t.status,
        "servicenow_id": t.servicenow_id,
        "created_by": t.created_by,
        "created_at": t.created_at.isoformat() + "Z",
        "updated_at": t.updated_at.isoformat() + "Z" if t.updated_at else t.created_at.isoformat() + "Z",
        "resolved_at": t.resolved_at.isoformat() + "Z" if t.resolved_at else None,
        "closed_at": t.closed_at.isoformat() + "Z" if t.closed_at else None,
        # ITSM Workflow fields
        "request_type": t.request_type,
        "manager": t.manager,
        "approval_status": t.approval_status,
        "assignment_group": t.assignment_group or t.assigned_team,
        # SLA
        "sla_state": t.sla_state or "HEALTHY",
        "sla_breached": t.sla_breached or False,
        "sla_breached_at": t.sla_breached_at.isoformat() + "Z" if t.sla_breached_at else None,
    }
