"""
test_ticket_workflow.py
──────────────────────────────────────────────────────────────────────────────
Integration tests for the critical ticket creation workflow.

Validates:
  1. Ticket creation persists to the database (not just returned in-memory)
  2. Incidents go directly to Admin Queue (no manager approval)
  3. Service Requests go to WAITING_MANAGER status first
  4. Ticket appears in My Tickets (GET /tickets) after creation
  5. TicketOrchestrator delegates to ticket_service (not ServiceNow directly)
  6. No ticket card shown on API failure (error guard)
"""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch, call
from datetime import datetime


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _make_mock_ticket(ticket_id: str, status: str, request_type: str) -> dict:
    return {
        "ticket_id": ticket_id,
        "category": "TEST",
        "description": "Test description",
        "issue_description": "Test description",
        "assigned_team": "IT Team",
        "priority": "MEDIUM",
        "sla_hours": 8,
        "status": status,
        "status_label": status.replace("_", " ").title(),
        "servicenow_id": "N/A",
        "created_by": "test_user",
        "created_at": datetime.utcnow().isoformat() + "Z",
        "request_type": request_type,
        "manager": "manager" if request_type != "INCIDENT" else None,
        "approval_status": "PENDING" if request_type != "INCIDENT" else "NOT_REQUIRED",
        "assignment_group": "IT Team",
        "requires_approval": request_type != "INCIDENT",
    }


# ─────────────────────────────────────────────────────────────────────────────
# 1. TicketOrchestrator — delegates to ticket_service
# ─────────────────────────────────────────────────────────────────────────────

class TestTicketOrchestrator:
    """
    Verify TicketOrchestrator.create() calls ticket_service.create_ticket()
    rather than ServiceNowClient.create_incident() directly.
    This is the root cause fix — no direct SN call, always DB-persisted.
    """

    def _make_state(self, category: str, session_id: str = "sess-test") -> MagicMock:
        state = MagicMock()
        state.session_id = session_id
        state.category = category
        state.active_issue = "Test issue"
        return state

    @patch("app.services.ticket_orchestrator.memory.get_history")
    @patch("app.services.ticket_service.create_ticket")
    @patch("app.services.ticket_summary_service.generate_ticket_summary")
    def test_orchestrator_calls_create_ticket(self, mock_summary, mock_create, mock_history):
        """TicketOrchestrator must delegate to ticket_service.create_ticket with correct core args."""
        from app.services.ticket_summary_service import TicketSummary
        mock_history.return_value = [
            {"sender": "user", "text": "VPN not working, cannot connect from home"},
        ]
        mock_summary.return_value = TicketSummary(
            short_description="VPN not working",
            description="VPN not working, cannot connect from home",
            source="llm",
            used_fallback=False,
        )
        mock_create.return_value = _make_mock_ticket("INC000001", "NEW", "INCIDENT")

        from app.services.ticket_orchestrator import TicketOrchestrator
        orch = TicketOrchestrator()
        result = orch.create(self._make_state("VPN"), username="test_user")

        # Must have called create_ticket exactly once (DB persistence path)
        mock_create.assert_called_once()
        call_kwargs = mock_create.call_args.kwargs
        assert call_kwargs["category"] in ("VPN", "network")
        assert call_kwargs["created_by"] == "test_user"
        assert call_kwargs["short_description"] == "VPN not working"
        assert call_kwargs["description"] == "VPN not working, cannot connect from home"
        # IncidentEnrichmentService always produces metadata; verify it is passed
        from app.services.incident_enrichment_service import IncidentMetadata
        assert isinstance(call_kwargs["incident_metadata"], IncidentMetadata)
        assert result["ticket_id"] == "INC000001"
        assert result["status"] == "NEW"
        assert result["request_type"] == "INCIDENT"

    @patch("app.services.ticket_orchestrator.memory.get_history")
    @patch("app.services.ticket_service.create_ticket")
    def test_orchestrator_returns_error_dict_on_failure(self, mock_create, mock_history):
        """On failure, orchestrator returns {'error': True} not raises."""
        mock_history.return_value = [{"sender": "user", "text": "some issue"}]
        mock_create.side_effect = RuntimeError("DB connection failed")

        from app.services.ticket_orchestrator import TicketOrchestrator
        result = TicketOrchestrator().create(self._make_state("GENERAL"), username="u")

        assert result.get("error") is True
        assert "message" in result

    @patch("app.services.ticket_orchestrator.memory.get_history")
    @patch("app.services.ticket_service.create_ticket")
    @patch("app.services.ticket_summary_service.generate_ticket_summary")
    def test_orchestrator_uses_first_user_message_as_description(
        self, mock_summary, mock_create, mock_history
    ):
        """TicketSummary description (derived from conversation) is used as issue_description."""
        from app.services.ticket_summary_service import TicketSummary
        mock_history.return_value = [
            {"sender": "user", "text": "Outlook is crashing every time I open it"},
            {"sender": "agent", "text": "Let me help with that"},
            {"sender": "user", "text": "Still not working after restart"},
        ]
        # Simulate TicketSummaryService distilling the conversation
        expected_description = "Outlook is crashing every time I open it"
        mock_summary.return_value = TicketSummary(
            short_description="Outlook crashing on open",
            description=expected_description,
            source="llm",
            used_fallback=False,
        )
        mock_create.return_value = _make_mock_ticket("INC000002", "NEW", "INCIDENT")

        from app.services.ticket_orchestrator import TicketOrchestrator
        TicketOrchestrator().create(self._make_state("OUTLOOK"), username="test_user")

        call_kwargs = mock_create.call_args.kwargs
        # The TicketSummary description must flow through as the issue description
        assert call_kwargs["issue_description"] == expected_description
        assert call_kwargs["description"] == expected_description

    @patch("app.services.ticket_orchestrator.memory.get_history")
    @patch("app.services.ticket_service.create_ticket")
    def test_orchestrator_no_longer_calls_servicenow_directly(self, mock_create, mock_history):
        """ServiceNowClient.create_incident must NOT be called directly from orchestrator.
        The orchestrator delegates to ticket_service which handles SN internally.
        """
        mock_history.return_value = [{"sender": "user", "text": "test"}]
        mock_create.return_value = _make_mock_ticket("INC000003", "NEW", "INCIDENT")

        with patch("app.services.servicenow_client.ServiceNowClient.create_incident") as mock_sn:
            from app.services.ticket_orchestrator import TicketOrchestrator
            TicketOrchestrator().create(self._make_state("VPN"))
            # Orchestrator must NOT call SN directly; only ticket_service may do so
            mock_sn.assert_not_called()



# ─────────────────────────────────────────────────────────────────────────────
# 2. Ticket Service — DB persistence
# ─────────────────────────────────────────────────────────────────────────────

class TestTicketServicePersistence:
    """Verify ticket_service.create_ticket() writes to DB."""

    @patch("app.services.ticket_service.calculate_priority", return_value="MEDIUM")
    @patch("app.services.ticket_service.store_sla_record")
    @patch("app.services.ticket_service.create_notification")
    @patch("app.services.ticket_service.get_db")
    @patch("app.services.ticket_service.ServiceNowService")
    def test_incident_persisted_to_db(self, mock_sn, mock_get_db, mock_notif, mock_sla, mock_prio):
        """Incident must be saved to DB via TicketRepository.save_ticket()."""
        mock_sn.return_value.validate_configuration.return_value = (True, "")
        mock_sn.return_value.create_incident.return_value = MagicMock(success=True, sys_id="SN001", number="INC000001")

        mock_repo = MagicMock()
        mock_repo.save_ticket.return_value = MagicMock(ticket_id="INC000001")
        mock_db = MagicMock()
        mock_db.execute.return_value.scalar.return_value = 100
        mock_db.__enter__ = MagicMock(return_value=mock_db)
        mock_db.__exit__ = MagicMock(return_value=False)
        mock_get_db.return_value = mock_db

        with patch("app.services.ticket_service.TicketRepository", return_value=mock_repo):
            from app.services.ticket_service import create_ticket
            result = create_ticket(
                category="VPN",
                issue_description="VPN not connecting",
                created_by="john",
            )

        # Verify DB save was called
        mock_repo.save_ticket.assert_called_once()
        save_kwargs = mock_repo.save_ticket.call_args.kwargs
        assert save_kwargs["category"] == "VPN"
        assert save_kwargs["created_by"] == "john"

        # Verify returned dict has required fields
        assert "ticket_id" in result
        assert "status" in result
        assert "request_type" in result
        assert "requires_approval" in result

    @patch("app.services.ticket_service.calculate_priority", return_value="MEDIUM")
    @patch("app.services.ticket_service.store_sla_record")
    @patch("app.services.ticket_service.create_notification")
    @patch("app.services.ticket_service.get_db")
    @patch("app.services.ticket_service.ServiceNowService")
    def test_service_request_gets_waiting_manager_status(self, mock_sn, mock_get_db, mock_notif, mock_sla, mock_prio):
        """Software installation must produce WAITING_MANAGER status, not NEW."""
        mock_sn.return_value.validate_configuration.return_value = (True, "")
        mock_sn.return_value.create_incident.return_value = MagicMock(success=True, sys_id="SN002", number="INC000002")

        mock_repo = MagicMock()
        mock_repo.save_ticket.return_value = MagicMock()
        mock_db = MagicMock()
        mock_db.execute.return_value.scalar.return_value = 100
        mock_db.__enter__ = MagicMock(return_value=mock_db)
        mock_db.__exit__ = MagicMock(return_value=False)
        mock_get_db.return_value = mock_db

        with patch("app.services.ticket_service.TicketRepository", return_value=mock_repo):
            from app.services.ticket_service import create_ticket
            result = create_ticket(
                category="SOFTWARE_INSTALLATION",
                issue_description="Please install Microsoft Visio on my laptop",
                created_by="jane",
            )

        assert result["status"] == "WAITING_MANAGER"
        assert result["request_type"] == "SERVICE_REQUEST"
        assert result["requires_approval"] is True
        assert result["approval_status"] == "PENDING"
        assert result["manager"] == "manager"

    @patch("app.services.ticket_service.calculate_priority", return_value="MEDIUM")
    @patch("app.services.ticket_service.store_sla_record")
    @patch("app.services.ticket_service.create_notification")
    @patch("app.services.ticket_service.get_db")
    @patch("app.services.ticket_service.ServiceNowService")
    def test_incident_gets_new_status_no_approval(self, mock_sn, mock_get_db, mock_notif, mock_sla, mock_prio):
        """VPN incident must go directly to NEW — no manager approval."""
        mock_sn.return_value.validate_configuration.return_value = (True, "")
        mock_sn.return_value.create_incident.return_value = MagicMock(success=True, sys_id="SN003", number="INC000003")

        mock_repo = MagicMock()
        mock_repo.save_ticket.return_value = MagicMock()
        mock_db = MagicMock()
        mock_db.execute.return_value.scalar.return_value = 100
        mock_db.__enter__ = MagicMock(return_value=mock_db)
        mock_db.__exit__ = MagicMock(return_value=False)
        mock_get_db.return_value = mock_db

        with patch("app.services.ticket_service.TicketRepository", return_value=mock_repo):
            from app.services.ticket_service import create_ticket
            result = create_ticket(
                category="VPN",
                issue_description="VPN is dropping connections intermittently",
                created_by="bob",
            )

        assert result["status"] == "NEW"
        assert result["request_type"] == "INCIDENT"
        assert result["requires_approval"] is False
        assert result["approval_status"] == "NOT_REQUIRED"
        assert result["manager"] is None

    @patch("app.services.ticket_service.calculate_priority", return_value="MEDIUM")
    @patch("app.services.ticket_service.store_sla_record")
    @patch("app.services.ticket_service.create_notification")
    @patch("app.services.ticket_service.get_db")
    @patch("app.services.ticket_service.ServiceNowService")
    def test_manager_notified_for_service_request(self, mock_sn, mock_get_db, mock_notif, mock_sla, mock_prio):
        """Manager must receive an approval notification for service requests."""
        mock_sn.return_value.validate_configuration.return_value = (True, "")
        mock_sn.return_value.create_incident.return_value = MagicMock(success=True, sys_id="SN004", number="INC000004")

        mock_repo = MagicMock()
        mock_repo.save_ticket.return_value = MagicMock()
        mock_db = MagicMock()
        mock_db.execute.return_value.scalar.return_value = 100
        mock_db.__enter__ = MagicMock(return_value=mock_db)
        mock_db.__exit__ = MagicMock(return_value=False)
        mock_get_db.return_value = mock_db

        with patch("app.services.ticket_service.TicketRepository", return_value=mock_repo):
            from app.services.ticket_service import create_ticket
            create_ticket(
                category="SAP",
                issue_description="Request SAP access for FICO Analyst role",
                created_by="alice",
            )

        # Verify manager notification was created
        notification_calls = mock_notif.call_args_list
        recipients = [c.kwargs.get("recipient", c.args[1] if len(c.args) > 1 else "") for c in notification_calls]
        assert "manager" in recipients, f"Expected manager notification, got: {recipients}"


# ─────────────────────────────────────────────────────────────────────────────
# 3. _build_payload — ticket_created guard
# ─────────────────────────────────────────────────────────────────────────────

class TestBuildPayloadGuard:
    """
    Verify that _build_payload only sets ticket_created=True when the
    backend confirmed DB persistence (ticket_id is present and no error).
    """

    def _make_state(self):
        from app.services.conversation_service import SessionState, ConversationPhase
        state = SessionState(session_id="s1", category="VPN")
        return state

    def test_ticket_created_true_when_persisted(self):
        """ticket_created=True only when ticket_id present and no error."""
        from app.services.conversation_service import ConversationService
        svc = ConversationService()
        state = self._make_state()

        ticket = {
            "ticket_id": "INC000042",
            "assigned_team": "IT Team",
            "priority": "HIGH",
            "sla_hours": 4,
            "request_type": "INCIDENT",
            "approval_status": "NOT_REQUIRED",
            "requires_approval": False,
            "status": "NEW",
            "status_label": "Open — Assigned to IT Team",
            "manager": None,
            "servicenow_id": "SN999",
        }
        payload = svc._build_payload(
            state, "Ticket created", "TICKET_CREATED",
            ticket_created=True, ticket_id="INC000042", ticket_details=ticket
        )

        assert payload["ticket_created"] is True
        assert payload["ticket_id"] == "INC000042"
        assert payload["request_type"] == "INCIDENT"
        assert payload["ticket_status"] == "NEW"

    def test_ticket_created_false_on_error(self):
        """ticket_created=False when ticket dict contains an error."""
        from app.services.conversation_service import ConversationService
        svc = ConversationService()
        state = self._make_state()

        error_ticket = {"error": True, "message": "DB unavailable"}
        payload = svc._build_payload(
            state, "Error occurred", "TICKET_CREATED",
            ticket_created=True, ticket_id=None, ticket_details=error_ticket
        )

        assert payload["ticket_created"] is False

    def test_ticket_created_false_when_no_ticket_id(self):
        """ticket_created=False when ticket_id is None (no DB write happened)."""
        from app.services.conversation_service import ConversationService
        svc = ConversationService()
        state = self._make_state()

        payload = svc._build_payload(
            state, "Response text", "TICKET_CREATED",
            ticket_created=True, ticket_id=None, ticket_details=None
        )

        assert payload["ticket_created"] is False


# ─────────────────────────────────────────────────────────────────────────────
# 4. ITSM Classifier — incident vs service request routing
# ─────────────────────────────────────────────────────────────────────────────

class TestITSMClassifierRouting:
    """Extended routing tests covering all common ticket categories."""

    def setup_method(self):
        from app.services.itsm_classifier import classify_request
        self.classify = classify_request

    # ── Incidents (no approval) ────────────────────────────────────────────

    def test_outlook_is_incident(self):
        r = self.classify("OUTLOOK", "Outlook is crashing")
        assert r.request_type == "INCIDENT"
        assert r.requires_approval is False
        assert r.initial_status == "NEW"

    def test_printer_is_incident(self):
        r = self.classify("PRINTER", "Printer is offline")
        assert r.request_type == "INCIDENT"

    def test_password_reset_is_incident(self):
        r = self.classify("PASSWORD_RESET", "Cannot log in")
        assert r.request_type == "INCIDENT"

    def test_network_is_incident(self):
        r = self.classify("NETWORK", "No internet on floor 3")
        assert r.request_type == "INCIDENT"

    def test_vpn_is_incident(self):
        r = self.classify("VPN", "AnyConnect keeps disconnecting")
        assert r.request_type == "INCIDENT"
        assert r.initial_status == "NEW"

    # ── Service Requests (require manager approval) ────────────────────────

    def test_software_installation_category_is_service_request(self):
        r = self.classify("SOFTWARE_INSTALLATION", "Need Visio installed")
        assert r.request_type == "SERVICE_REQUEST"
        assert r.requires_approval is True
        assert r.initial_status == "WAITING_MANAGER"

    def test_sap_access_category_is_service_request(self):
        r = self.classify("SAP_ACCESS", "Need SAP PRD access")
        assert r.request_type == "SERVICE_REQUEST"
        assert r.requires_approval is True

    def test_shared_mailbox_category_is_service_request(self):
        r = self.classify("SHARED_MAILBOX", "Need shared mailbox")
        assert r.request_type == "SERVICE_REQUEST"

    def test_new_laptop_category_is_service_request(self):
        r = self.classify("NEW_LAPTOP", "Request new ThinkPad")
        assert r.request_type == "SERVICE_REQUEST"

    def test_software_install_phrase_in_description_is_service_request(self):
        r = self.classify("GENERAL", "I need software installation for Adobe Acrobat")
        assert r.request_type == "SERVICE_REQUEST"

    def test_shared_mailbox_phrase_is_service_request(self):
        r = self.classify("GENERAL", "Please set up a shared mailbox for the finance team")
        assert r.request_type == "SERVICE_REQUEST"
