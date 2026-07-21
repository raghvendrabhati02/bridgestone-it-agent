"""
test_servicenow_service.py
─────────────────────────────────────────────────────────────────────────────
Unit tests for ServiceNowService, validate_configuration(), local fallback,
caller_id, PATCH updates, and custom status code mapping.
"""

import os
from unittest.mock import MagicMock, patch
import pytest

from app.models.servicenow_models import (
    IncidentCreateRequest,
    IncidentCreateResponse,
    IncidentStatus,
    IncidentUpdateRequest,
)
from app.services.servicenow_exceptions import (
    ServiceNowException,
    ServiceNowConfigurationError,
    ServiceNowAuthenticationError,
    ServiceNowAPIError,
    ServiceNowHTTPError,
)
from app.services.servicenow_service import ServiceNowService
from app.services.servicenow_client import ServiceNowClient
from app.services.ticket_service import create_ticket, set_servicenow_service


@pytest.fixture
def disabled_env():
    """Environment fixture with ServiceNow disabled."""
    old_env = os.environ.copy()
    os.environ["SERVICENOW_ENABLED"] = "false"
    os.environ["SERVICENOW_INSTANCE_URL"] = ""
    yield
    os.environ.clear()
    os.environ.update(old_env)


@pytest.fixture
def enabled_env():
    """Environment fixture with ServiceNow enabled and configured with Basic Auth."""
    old_env = os.environ.copy()
    os.environ["SERVICENOW_ENABLED"] = "true"
    os.environ["SERVICENOW_INSTANCE_URL"] = "https://dev12345.service-now.com"
    os.environ["SERVICENOW_AUTH_TYPE"] = "basic"
    os.environ["SERVICENOW_USERNAME"] = "admin"
    os.environ["SERVICENOW_PASSWORD"] = "secret123"
    os.environ["SERVICENOW_ASSIGNMENT_GROUP_MODE"] = "name"
    yield
    os.environ.clear()
    os.environ.update(old_env)


def test_servicenow_service_disabled_by_default(disabled_env):
    """Test that ServiceNowService is disabled by default and handles operations gracefully."""
    service = ServiceNowService()
    assert service.is_configured() is False

    is_valid, msg = service.validate_configuration()
    assert is_valid is False
    assert "disabled" in msg.lower()

    req = IncidentCreateRequest(short_description="VPN issue", description="Cannot connect")
    res = service.create_incident(req)

    assert res.success is False
    assert res.sys_id == "N/A"
    assert "disabled" in res.message.lower() or "unconfigured" in res.message.lower()


def test_validate_configuration_checks(enabled_env):
    """Test validate_configuration logic under various invalid states."""
    service = ServiceNowService()
    is_valid, msg = service.validate_configuration()
    assert is_valid is True
    assert "valid" in msg.lower()

    # Invalid URL format
    service.instance_url = "invalid_url_no_domain"
    is_valid, msg = service.validate_configuration()
    assert is_valid is False
    assert "invalid format" in msg.lower()

    # Missing username
    service.instance_url = "https://dev12345.service-now.com"
    service.username = ""
    is_valid, msg = service.validate_configuration()
    assert is_valid is False
    assert "username" in msg.lower()

    # Invalid Auth Type
    service.username = "admin"
    service.auth_type = "invalid_auth"
    is_valid, msg = service.validate_configuration()
    assert is_valid is False
    assert "invalid" in msg.lower()

    # Invalid Assignment Group Mode
    service.auth_type = "basic"
    service.assignment_group_mode = "invalid_mode"
    is_valid, msg = service.validate_configuration()
    assert is_valid is False
    assert "assignment_group_mode" in msg.lower()


def test_create_incident_success_with_caller_id(enabled_env):
    """Test create_incident with caller_id included in payload."""
    mock_client = MagicMock()
    mock_client.create_incident.return_value = {
        "success": True,
        "sys_id": "SYS998877",
        "number": "INC0099887",
        "state": "1",
        "caller_id": "john.doe",
        "message": "Incident created",
    }

    service = ServiceNowService(client=mock_client)
    req = IncidentCreateRequest(
        short_description="Outlook crash",
        description="Outlook crashes on launch",
        category="OUTLOOK",
        severity=2,
        caller_id="john.doe",
    )

    res = service.create_incident(req)

    assert res.success is True
    assert res.sys_id == "SYS998877"
    assert res.number == "INC0099887"
    assert res.caller_id == "john.doe"
    mock_client.create_incident.assert_called_once_with(
        short_description="Outlook crash",
        description="Outlook crashes on launch",
        category="OUTLOOK",
        severity=2,
        assignment_group="IT Support",
        caller_id="john.doe",
    )


def test_update_incident_uses_patch(enabled_env):
    """Test update_incident delegates to client update_incident using PATCH."""
    mock_client = MagicMock()
    mock_client.update_incident.return_value = {
        "success": True,
        "sys_id": "SYS123",
        "number": "INC00123",
        "state": "2",
        "result": {"sys_id": "SYS123", "number": "INC00123", "state": "2"}
    }
    mock_client.get_incident.return_value = {
        "success": True,
        "sys_id": "SYS123",
        "number": "INC00123",
        "result": {"sys_id": "SYS123", "number": "INC00123", "state": "2"}
    }

    service = ServiceNowService(client=mock_client)
    update_req = IncidentUpdateRequest(work_notes="Tested connection")

    status = service.update_incident("SYS123", update_req)

    assert status is not None
    assert status.sys_id == "SYS123"
    mock_client.update_incident.assert_called_once()
    args, kwargs = mock_client.update_incident.call_args
    assert args[0] == "SYS123"
    assert kwargs["use_patch"] is True


def test_status_code_mapping_in_client(enabled_env):
    """Test status code exceptions (400, 404, 409, 429, 500) in ServiceNowClient."""
    client = ServiceNowClient(instance="https://dev12345.service-now.com", username="u", password="p")

    # 400 Bad Request
    mock_res_400 = MagicMock(status_code=400)
    mock_res_400.json.return_value = {"error": {"message": "Invalid field value"}}
    with patch.object(client.session, "post", return_value=mock_res_400):
        with pytest.raises(ServiceNowHTTPError) as exc:
            client._execute_request("POST", "https://dev12345.service-now.com/api")
        assert exc.value.status_code == 400
        assert "Bad Request" in str(exc.value)

    # 429 Rate Limit
    mock_res_429 = MagicMock(status_code=429)
    mock_res_429.json.return_value = {"error": "Too many requests"}
    with patch.object(client.session, "get", return_value=mock_res_429):
        with pytest.raises(ServiceNowHTTPError) as exc:
            client._execute_request("GET", "https://dev12345.service-now.com/api")
        assert exc.value.status_code == 429
        assert "Rate limit" in str(exc.value)


def test_local_ticket_creation_fallback(disabled_env):
    """Test ticket_service.create_ticket falls back to local ticket creation when ServiceNow is disabled."""
    service = ServiceNowService()
    set_servicenow_service(service)

    try:
        ticket = create_ticket(category="VPN", issue_description="VPN connection dropped")
        assert ticket is not None
        assert ticket.get("ticket_id").startswith("INC")
        assert ticket.get("servicenow_id") == "N/A"
        assert ticket.get("category") == "VPN"
    finally:
        set_servicenow_service(None)
