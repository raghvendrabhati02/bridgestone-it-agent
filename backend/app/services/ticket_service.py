import datetime
import logging
from app.services.assignment_service import get_assignment_team
from app.services.notification_service import create_notification
from app.services.sla_service import (
    calculate_priority,
    calculate_sla,
    store_sla_record
)
from app.adapters.servicenow_adapter import ServiceNowAdapter
from app.database.session import get_db
from app.database.repositories.ticket_repository import TicketRepository

logger = logging.getLogger("it-agent-backend")

# Initialize the ServiceNow adapter client
servicenow_client = ServiceNowAdapter()

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
    Creates an enhanced ticket with sequential ID (INC000001), 
    assigns IT support team, calculates priority and SLA, stores records in database,
    creates user and agent notifications, and returns details.
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
    
    # Create ServiceNow incident using adapter client
    try:
        snow_incident = servicenow_client.create_incident(
            category=category,
            description=issue_description,
            assignment_group=assigned_team
        )
        servicenow_id = snow_incident.get("sys_id", "N/A")
    except Exception as e:
        logger.error("Ticket Service: Failed to create ServiceNow incident. Error: %s", e)
        servicenow_id = "N/A"
        
    ticket = {
        "ticket_id": ticket_id,
        "category": category,
        "description": issue_description,
        "issue_description": issue_description,  # kept for backward compatibility
        "assigned_team": assigned_team,
        "priority": priority,
        "sla_hours": sla_hours,
        "status": "OPEN",
        "servicenow_id": servicenow_id,
        "created_by": created_by,
        "created_at": created_at
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
                status="OPEN",
                servicenow_id=servicenow_id,
                created_by=created_by
            )
            logger.info("Ticket Service: Persisted ticket %s to database", ticket_id)
    except Exception as e:
        logger.error("Ticket Service: Failed to persist ticket to database: %s", e)
        # Fallback to volatile memory list
        tickets.append(ticket)

        
    if servicenow_id != "N/A":
        local_to_snow_mapping[ticket_id] = servicenow_id
        
    # Automatically generate notifications for assigned team and employee
    create_notification(
        ticket_id=ticket_id,
        recipient=assigned_team,
        message=f"New {category} issue assigned."
    )
    create_notification(
        ticket_id=ticket_id,
        recipient="Employee",
        message=f"Your ticket {ticket_id} has been created and assigned."
    )

    # ── RBAC Audit — ticket creation ──────────────────────────────────────────
    try:
        from app.services.rbac_audit_service import log_rbac_event
        log_rbac_event(
            user=created_by or "unknown",
            role="EMPLOYEE",   # ticket creation is always by the requesting user
            action="create_ticket",
            ticket_id=ticket_id,
            old_state=None,
            new_state="OPEN",
            details={
                "category": category,
                "assigned_team": assigned_team,
                "priority": priority,
                "sla_hours": sla_hours,
            },
        )
    except Exception as e:
        logger.warning("Ticket Service: RBAC audit emit failed for %s: %s", ticket_id, e)

    return ticket

def get_all_tickets() -> list[dict]:
    """
    Returns the list of all created tickets.
    """
    try:
        with get_db() as db:
            repo = TicketRepository(db)
            db_tickets = repo.get_all_tickets()
            return [
                {
                    "ticket_id": t.ticket_id,
                    "category": t.category,
                    "description": t.description,
                    "issue_description": t.issue_description,
                    "assigned_team": t.assigned_team,
                    "priority": t.priority,
                    "sla_hours": t.sla_hours,
                    "status": t.status,
                    "servicenow_id": t.servicenow_id,
                    "created_by": t.created_by,
                    "created_at": t.created_at.isoformat() + "Z",
                    # ── SLA Escalation Engine fields ───────────────────────
                    "sla_state": t.sla_state or "HEALTHY",
                    "sla_breached": t.sla_breached or False,
                    "sla_breached_at": (
                        t.sla_breached_at.isoformat() + "Z" if t.sla_breached_at else None
                    ),
                }
                for t in db_tickets
            ]


    except Exception as e:
        logger.error("Ticket Service: Failed to get tickets from DB: %s", e)
        return tickets

def get_ticket(ticket_id: str):

    try:
        with get_db() as db:

            repo = TicketRepository(db)

            tickets = repo.get_all_tickets()

            for t in tickets:

                if t.ticket_id == ticket_id:

                    return {
                        "ticket_id": t.ticket_id,
                        "category": t.category,
                        "description": t.description,
                        "assigned_team": t.assigned_team,
                        "priority": t.priority,
                        "sla_hours": t.sla_hours,
                        "status": t.status,
                        "servicenow_id": t.servicenow_id
                    }

    except Exception as e:

        logger.error(
            "Ticket Service: Failed to fetch ticket %s : %s",
            ticket_id,
            e
        )

    return None
