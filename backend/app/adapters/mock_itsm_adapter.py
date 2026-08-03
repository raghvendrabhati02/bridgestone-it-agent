"""
mock_itsm_adapter.py
─────────────────────────────────────────────────────────────────────────────
Mock ITSM Adapter implementing ITSMAdapter interface.
Routes standard ITSM commands to the internal Mock ITSM Platform.
"""

import logging
from typing import Optional, Dict, Any, List
from app.adapters.itsm_adapter import ITSMAdapter
from app.mock_itsm.database import get_mock_itsm_db
from app.mock_itsm.services.mock_incident_service import MockIncidentService

logger = logging.getLogger("it-agent-backend")


class MockITSMAdapter(ITSMAdapter):
    def __init__(self):
        self.connected_state = True
        logger.info("MockITSMAdapter: Initialized successfully.")

    def connect(self) -> bool:
        self.connected_state = True
        return True

    def health_check(self) -> bool:
        try:
            with get_mock_itsm_db() as db:
                svc = MockIncidentService(db)
                svc.list_incidents(limit=1)
            return True
        except Exception as e:
            logger.error("MockITSMAdapter: Health check failed: %s", e)
            return False

    def disconnect(self) -> bool:
        self.connected_state = False
        return True

    def execute(self, action: str, **kwargs) -> Any:
        logger.info("MockITSMAdapter: Executing action '%s'", action)
        if action == "create_incident":
            return self.create_incident(
                category=kwargs.get("category", "General"),
                description=kwargs.get("description", ""),
                assignment_group=kwargs.get("assignment_group"),
                short_description=kwargs.get("short_description"),
                caller_id=kwargs.get("caller_id")
            )
        elif action == "get_incident":
            return self.get_incident(sys_id=kwargs.get("sys_id"))
        elif action == "update_incident":
            return self.update_incident(sys_id=kwargs.get("sys_id"), updates=kwargs.get("updates", {}))
        elif action == "close_incident":
            return self.close_incident(sys_id=kwargs.get("sys_id"), resolution_notes=kwargs.get("resolution_notes"))
        elif action == "get_all_incidents":
            return self.get_all_incidents()
        elif action == "create_service_request":
            return self.create_service_request(
                category=kwargs.get("category", "General"),
                description=kwargs.get("description", ""),
                action_type=kwargs.get("action_type")
            )
        elif action == "get_request":
            return self.get_request(sys_id=kwargs.get("sys_id"))
        elif action == "update_request":
            return self.update_request(sys_id=kwargs.get("sys_id"), updates=kwargs.get("updates", {}))
        elif action == "get_all_requests":
            return self.get_all_requests()
        raise NotImplementedError(f"Action '{action}' not supported by MockITSMAdapter")

    def _format_ticket_response(self, ticket) -> dict:
        if not ticket:
            return {}
        return {
            "success": True,
            "sys_id": ticket.ticket_number,
            "number": ticket.ticket_number,
            "ticket_id": ticket.ticket_number,
            "category": ticket.category,
            "subcategory": ticket.subcategory or "",
            "short_description": ticket.short_description or "",
            "description": ticket.description or "",
            "state": ticket.status,
            "status": ticket.status,
            "assignment_group": ticket.assigned_group or "",
            "assigned_engineer": ticket.assigned_engineer or "",
            "created_by": ticket.created_by or "",
            "priority": ticket.priority,
            "request_type": ticket.request_type,
            "approval_status": ticket.approval_status,
            "approved_by": ticket.approved_by or "",
            "created_at": ticket.created_at.isoformat() + "Z" if ticket.created_at else None,
            "updated_at": ticket.updated_at.isoformat() + "Z" if ticket.updated_at else None,
        }

    def create_incident(
        self,
        category: str,
        description: str,
        assignment_group: Optional[str] = None,
        short_description: Optional[str] = None,
        caller_id: Optional[str] = None,
        priority: Optional[str] = None,
        **kwargs
    ) -> dict:
        with get_mock_itsm_db() as db:
            svc = MockIncidentService(db)
            ticket = svc.create_incident(
                category=category,
                description=description,
                short_description=short_description,
                assigned_group=assignment_group,
                created_by=caller_id or "employee",
                priority=priority,
                request_type="INCIDENT",
                **kwargs
            )
            return self._format_ticket_response(ticket)

    def get_incident(self, sys_id: str) -> dict:
        with get_mock_itsm_db() as db:
            svc = MockIncidentService(db)
            ticket = svc.get_incident(sys_id)
            if not ticket:
                return {"success": False, "message": f"Incident {sys_id} not found."}
            return self._format_ticket_response(ticket)

    def update_incident(self, sys_id: str, updates: dict) -> dict:
        with get_mock_itsm_db() as db:
            svc = MockIncidentService(db)
            try:
                ticket = svc.update_incident(ticket_number=sys_id, **updates)
                return self._format_ticket_response(ticket)
            except ValueError as e:
                return {"success": False, "message": str(e)}

    def close_incident(self, sys_id: str, resolution_notes: Optional[str] = None) -> dict:
        with get_mock_itsm_db() as db:
            svc = MockIncidentService(db)
            try:
                ticket = svc.close_incident(ticket_number=sys_id, resolution_notes=resolution_notes)
                return self._format_ticket_response(ticket)
            except ValueError as e:
                return {"success": False, "message": str(e)}

    def get_all_incidents(self) -> list:
        with get_mock_itsm_db() as db:
            svc = MockIncidentService(db)
            tickets = svc.list_incidents(limit=500)
            return [self._format_ticket_response(t) for t in tickets]

    def create_service_request(
        self,
        category: str,
        description: str,
        action_type: Optional[str] = None,
        **kwargs
    ) -> dict:
        with get_mock_itsm_db() as db:
            svc = MockIncidentService(db)
            ticket = svc.create_incident(
                category=category,
                description=description,
                request_type="SERVICE_REQUEST",
                **kwargs
            )
            return self._format_ticket_response(ticket)

    def get_request(self, sys_id: str) -> dict:
        return self.get_incident(sys_id)

    def update_request(self, sys_id: str, updates: dict) -> dict:
        return self.update_incident(sys_id, updates)

    def get_all_requests(self) -> list:
        with get_mock_itsm_db() as db:
            svc = MockIncidentService(db)
            tickets = [t for t in svc.list_incidents(limit=500) if t.request_type == "SERVICE_REQUEST"]
            return [self._format_ticket_response(t) for t in tickets]
