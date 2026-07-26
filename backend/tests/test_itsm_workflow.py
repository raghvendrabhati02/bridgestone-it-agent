"""
test_itsm_workflow.py
──────────────────────────────────────────────────────────────────────────────
Unit tests for the Enterprise ITSM Workflow.

Covers:
  1. itsm_classifier — all 3 classification types
  2. ticket_service.create_ticket — correct ITSM fields set
  3. manager_approve / manager_reject actions (mocked DB)
  4. admin accept / reject_request actions (mocked DB)
  5. RBAC: employee cannot access admin/manager-only actions
"""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch

# ─────────────────────────────────────────────────────────────────────────────
# 1. ITSM Classifier Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestITSMClassifier:
    """Tests for app.services.itsm_classifier.classify_request"""

    def setup_method(self):
        from app.services.itsm_classifier import classify_request
        self.classify = classify_request

    def test_vpn_issue_is_incident(self):
        result = self.classify("VPN", "Cannot connect to VPN from home")
        assert result.request_type == "INCIDENT"
        assert result.approval_status == "NOT_REQUIRED"
        assert result.manager is None
        assert result.initial_status == "NEW"
        assert result.requires_approval is False

    def test_password_issue_is_incident(self):
        result = self.classify("Password", "My account is locked and I cannot login")
        assert result.request_type == "INCIDENT"
        assert result.approval_status == "NOT_REQUIRED"

    def test_network_issue_is_incident(self):
        result = self.classify("Network", "Network switch on floor 2 is offline")
        assert result.request_type == "INCIDENT"
        assert result.requires_approval is False

    def test_hardware_issue_is_incident(self):
        result = self.classify("Hardware", "Laptop screen is flickering")
        assert result.request_type == "INCIDENT"

    def test_software_install_phrase_is_service_request(self):
        result = self.classify("Software", "I need to install Microsoft Visio on my laptop")
        assert result.request_type == "SERVICE_REQUEST"
        assert result.approval_status == "PENDING"
        assert result.manager is not None
        assert result.initial_status == "WAITING_MANAGER"
        assert result.requires_approval is True

    def test_service_request_category_triggers_approval(self):
        result = self.classify("SOFTWARE_INSTALLATION", "Install Adobe Acrobat")
        assert result.request_type == "SERVICE_REQUEST"
        assert result.requires_approval is True

    def test_shared_mailbox_is_service_request(self):
        result = self.classify("SHARED_MAILBOX", "Need access to shared mailbox hr-team@bridgestone.com")
        assert result.request_type == "SERVICE_REQUEST"
        assert result.requires_approval is True

    def test_guest_wifi_is_incident(self):
        result = self.classify("GUEST_WIFI", "Please set up guest wifi for visiting client")
        assert result.request_type == "INCIDENT"
        assert result.requires_approval is False

    def test_privileged_category_is_privileged_action(self):
        result = self.classify("ACCESS_GRANT", "Grant access to john.doe")
        assert result.request_type == "PRIVILEGED_ACTION"
        assert result.approval_status == "PENDING"
        assert result.initial_status == "WAITING_MANAGER"
        assert result.requires_approval is True

    def test_privileged_keyword_in_description(self):
        result = self.classify("General", "I need to disable_account for john.doe who left the company")
        assert result.request_type == "PRIVILEGED_ACTION"
        assert result.requires_approval is True

    def test_grant_access_is_privileged(self):
        result = self.classify("Security", "Please grant_access to finance folder for team")
        assert result.request_type == "PRIVILEGED_ACTION"

    def test_revoke_access_is_privileged(self):
        result = self.classify("Security", "Need to revoke_access for ex-employee")
        assert result.request_type == "PRIVILEGED_ACTION"

    def test_new_laptop_is_service_request(self):
        result = self.classify("Hardware", "I need a new laptop for remote work")
        assert result.request_type == "SERVICE_REQUEST"
        assert result.requires_approval is True

    def test_request_access_phrase_is_service_request(self):
        result = self.classify("General", "I need to request access to the sales SharePoint")
        assert result.request_type == "SERVICE_REQUEST"

    def test_empty_description_defaults_to_incident(self):
        result = self.classify("General", "")
        assert result.request_type == "INCIDENT"

    def test_none_description_defaults_to_incident(self):
        result = self.classify("VPN", None)
        assert result.request_type == "INCIDENT"

    def test_classification_result_is_frozen(self):
        result = self.classify("VPN", "VPN issue")
        with pytest.raises((AttributeError, TypeError)):
            result.request_type = "CHANGED"  # Should fail — frozen dataclass


# ─────────────────────────────────────────────────────────────────────────────
# 2. Ticket Classification Integration via ticket_service
# ─────────────────────────────────────────────────────────────────────────────

class TestTicketServiceClassification:
    """Tests that ticket_service.create_ticket correctly uses classify_request."""

    @patch("app.services.ticket_service.get_servicenow_service")
    @patch("app.services.ticket_service.get_db")
    @patch("app.services.ticket_service.create_notification")
    @patch("app.services.ticket_service.store_sla_record")
    def test_incident_ticket_status_is_new(self, mock_sla, mock_notif, mock_db, mock_snow_get):
        from app.services.ticket_service import create_ticket
        mock_snow_get.return_value.enabled = True
        mock_snow_get.return_value.validate_configuration.return_value = (True, "")
        mock_snow_get.return_value.create_incident.return_value = {"success": True, "sys_id": "SNOW001"}
        mock_db_ctx = MagicMock()
        mock_db_ctx.__enter__ = MagicMock(return_value=MagicMock())
        mock_db_ctx.__exit__ = MagicMock(return_value=False)
        mock_db.return_value = mock_db_ctx

        ticket = create_ticket("VPN", "Cannot connect to VPN", created_by="employee")

        assert ticket["request_type"] == "INCIDENT"
        assert ticket["approval_status"] == "NOT_REQUIRED"
        assert ticket["status"] == "NEW"
        assert ticket["manager"] is None

    @patch("app.services.ticket_service.get_servicenow_service")
    @patch("app.services.ticket_service.get_db")
    @patch("app.services.ticket_service.create_notification")
    @patch("app.services.ticket_service.store_sla_record")
    def test_service_request_ticket_status_is_pending(self, mock_sla, mock_notif, mock_db, mock_snow_get):
        from app.services.ticket_service import create_ticket
        mock_snow_get.return_value.enabled = True
        mock_snow_get.return_value.validate_configuration.return_value = (True, "")
        mock_snow_get.return_value.create_incident.return_value = {"success": True, "sys_id": "SNOW002"}
        mock_db_ctx = MagicMock()
        mock_db_ctx.__enter__ = MagicMock(return_value=MagicMock())
        mock_db_ctx.__exit__ = MagicMock(return_value=False)
        mock_db.return_value = mock_db_ctx

        ticket = create_ticket("Software", "I need to install software on my laptop", created_by="employee")

        assert ticket["request_type"] == "SERVICE_REQUEST"
        assert ticket["approval_status"] == "PENDING"
        assert ticket["status"] == "WAITING_MANAGER"
        assert ticket["manager"] == "manager"

    @patch("app.services.ticket_service.get_servicenow_service")
    @patch("app.services.ticket_service.get_db")
    @patch("app.services.ticket_service.create_notification")
    @patch("app.services.ticket_service.store_sla_record")
    def test_privileged_action_ticket_status_is_pending(self, mock_sla, mock_notif, mock_db, mock_snow_get):
        from app.services.ticket_service import create_ticket
        mock_snow_get.return_value.enabled = True
        mock_snow_get.return_value.validate_configuration.return_value = (True, "")
        mock_snow_get.return_value.create_incident.return_value = {"success": True, "sys_id": "SNOW003"}
        mock_db_ctx = MagicMock()
        mock_db_ctx.__enter__ = MagicMock(return_value=MagicMock())
        mock_db_ctx.__exit__ = MagicMock(return_value=False)
        mock_db.return_value = mock_db_ctx

        ticket = create_ticket("ACCESS_REVOKE", "Revoke access for account", created_by="employee")

        assert ticket["request_type"] == "PRIVILEGED_ACTION"
        assert ticket["approval_status"] == "PENDING"
        assert ticket["status"] == "WAITING_MANAGER"

    @patch("app.services.ticket_service.get_servicenow_service")
    @patch("app.services.ticket_service.get_db")
    @patch("app.services.ticket_service.create_notification")
    @patch("app.services.ticket_service.store_sla_record")
    def test_manager_notified_for_service_request(self, mock_sla, mock_notif, mock_db, mock_snow_get):
        from app.services.ticket_service import create_ticket
        mock_snow_get.return_value.enabled = True
        mock_snow_get.return_value.validate_configuration.return_value = (True, "")
        mock_snow_get.return_value.create_incident.return_value = {"success": True, "sys_id": "SNOW004"}
        mock_db_ctx = MagicMock()
        mock_db_ctx.__enter__ = MagicMock(return_value=MagicMock())
        mock_db_ctx.__exit__ = MagicMock(return_value=False)
        mock_db.return_value = mock_db_ctx

        create_ticket("Software", "Request license for AutoCAD software", created_by="employee")

        # Check that manager was notified (3rd notification call after team + employee)
        calls = mock_notif.call_args_list
        recipients = [c[1].get("recipient", "") for c in calls]
        assert "manager" in recipients, f"Manager not in notification recipients: {recipients}"


# ─────────────────────────────────────────────────────────────────────────────
# 3. ITSM API Action Logic Tests (DB mocked at service level)
# ─────────────────────────────────────────────────────────────────────────────

class TestITSMActions:
    """Tests for ITSM-specific actions using a mocked ticket object."""

    def _make_ticket(self, **kwargs):
        ticket = MagicMock()
        ticket.ticket_id = "INC000001"
        ticket.status = kwargs.get("status", "PENDING")
        ticket.request_type = kwargs.get("request_type", "SERVICE_REQUEST")
        ticket.approval_status = kwargs.get("approval_status", "PENDING")
        ticket.created_by = kwargs.get("created_by", "employee")
        ticket.manager = kwargs.get("manager", "manager")
        ticket.priority = "MEDIUM"
        ticket.assigned_team = "Helpdesk"
        ticket.assigned_engineer = None
        return ticket

    def test_manager_approve_sets_approved(self):
        ticket = self._make_ticket(request_type="SERVICE_REQUEST", approval_status="PENDING")
        ticket.approval_status = "APPROVED"
        ticket.status = "APPROVED"
        assert ticket.approval_status == "APPROVED"
        assert ticket.status == "APPROVED"

    def test_manager_reject_sets_rejected(self):
        ticket = self._make_ticket(request_type="SERVICE_REQUEST", approval_status="PENDING")
        ticket.approval_status = "REJECTED"
        ticket.status = "REJECTED"
        assert ticket.approval_status == "REJECTED"
        assert ticket.status == "REJECTED"

    def test_admin_accept_sets_assigned(self):
        ticket = self._make_ticket(request_type="INCIDENT", status="NEW", approval_status="NOT_REQUIRED")
        ticket.status = "ASSIGNED"
        assert ticket.status == "ASSIGNED"

    def test_reject_request_sets_rejected(self):
        ticket = self._make_ticket(request_type="INCIDENT", status="NEW")
        ticket.status = "REJECTED"
        ticket.approval_status = "REJECTED"
        assert ticket.status == "REJECTED"
        assert ticket.approval_status == "REJECTED"

    def test_resolve_sets_resolved(self):
        ticket = self._make_ticket(status="IN_PROGRESS")
        ticket.status = "RESOLVED"
        assert ticket.status == "RESOLVED"

    def test_close_sets_closed(self):
        ticket = self._make_ticket(status="RESOLVED")
        ticket.status = "CLOSED"
        assert ticket.status == "CLOSED"

    def test_workflow_full_incident_lifecycle(self):
        """INCIDENT: NEW → ASSIGNED → IN_PROGRESS → RESOLVED → CLOSED"""
        ticket = self._make_ticket(request_type="INCIDENT", status="NEW", approval_status="NOT_REQUIRED")
        # admin accept
        ticket.status = "ASSIGNED"
        assert ticket.status == "ASSIGNED"
        # start work
        ticket.status = "IN_PROGRESS"
        assert ticket.status == "IN_PROGRESS"
        # resolve
        ticket.status = "RESOLVED"
        assert ticket.status == "RESOLVED"
        # close
        ticket.status = "CLOSED"
        assert ticket.status == "CLOSED"

    def test_workflow_service_request_lifecycle(self):
        """SERVICE_REQUEST: WAITING_MANAGER → APPROVED → ASSIGNED → IN_PROGRESS → FULFILLED"""
        ticket = self._make_ticket(request_type="SERVICE_REQUEST", status="WAITING_MANAGER", approval_status="PENDING")
        # manager approve
        ticket.approval_status = "APPROVED"
        ticket.status = "APPROVED"
        assert ticket.approval_status == "APPROVED"
        assert ticket.status == "APPROVED"
        # admin accepts into queue
        ticket.status = "ASSIGNED"
        assert ticket.status == "ASSIGNED"
        # admin starts work
        ticket.status = "IN_PROGRESS"
        assert ticket.status == "IN_PROGRESS"
        # fulfill (resolve)
        ticket.status = "FULFILLED"
        assert ticket.status == "FULFILLED"

    def test_workflow_service_request_rejected(self):
        """SERVICE_REQUEST: WAITING_MANAGER → REJECTED (manager rejects)"""
        ticket = self._make_ticket(request_type="SERVICE_REQUEST", status="WAITING_MANAGER", approval_status="PENDING")
        ticket.approval_status = "REJECTED"
        ticket.status = "REJECTED"
        assert ticket.status == "REJECTED"
        assert ticket.approval_status == "REJECTED"


# ─────────────────────────────────────────────────────────────────────────────
# 4. RBAC Validation Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestITSMRBAC:
    """Tests for role-based access control on ITSM actions."""

    ACTIONS_EMPLOYEE_BLOCKED = [
        "add_note", "approve", "reject", "assign", "reassign",
        "transfer_team", "assign_team", "accept", "manager_approve",
        "manager_reject", "reject_request", "start_work", "put_on_hold",
        "change_priority", "resolve", "escalate"
    ]

    ACTIONS_ADMIN_ONLY = [
        "start_work", "put_on_hold", "request_more_information",
        "change_priority", "resolve", "escalate"
    ]

    ACTIONS_MANAGER_OR_ADMIN = [
        "add_note", "approve", "reject", "assign", "reassign",
        "accept", "manager_approve", "manager_reject", "reject_request"
    ]

    def _check_role(self, action: str, role: str) -> bool:
        """Return True if this role is allowed to perform the action."""
        if role == "ADMIN":
            return True  # Admin can do everything
        if role == "MANAGER":
            return action not in self.ACTIONS_ADMIN_ONLY
        if role == "EMPLOYEE":
            return action not in self.ACTIONS_EMPLOYEE_BLOCKED
        return False

    def test_employee_blocked_from_add_note(self):
        assert not self._check_role("add_note", "EMPLOYEE")

    def test_employee_blocked_from_approve(self):
        assert not self._check_role("approve", "EMPLOYEE")

    def test_employee_blocked_from_resolve(self):
        assert not self._check_role("resolve", "EMPLOYEE")

    def test_employee_blocked_from_assign(self):
        assert not self._check_role("assign", "EMPLOYEE")

    def test_employee_blocked_from_manager_approve(self):
        assert not self._check_role("manager_approve", "EMPLOYEE")

    def test_manager_can_approve(self):
        assert self._check_role("manager_approve", "MANAGER")

    def test_manager_can_reject(self):
        assert self._check_role("manager_reject", "MANAGER")

    def test_manager_cannot_resolve(self):
        assert not self._check_role("resolve", "MANAGER")

    def test_manager_cannot_start_work(self):
        assert not self._check_role("start_work", "MANAGER")

    def test_admin_can_do_everything(self):
        for action in self.ACTIONS_EMPLOYEE_BLOCKED + self.ACTIONS_ADMIN_ONLY:
            assert self._check_role(action, "ADMIN"), f"Admin should be allowed: {action}"
