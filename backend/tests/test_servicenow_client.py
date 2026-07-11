"""
test_servicenow_client.py
─────────────────────────────────────────────────────────────────────────────
Tests for ServiceNowClient and integration inside TicketOrchestrator.
"""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch
import pytest
import requests
from app.services.servicenow_client import (
    ServiceNowClient,
    ServiceNowException,
    ServiceNowConnectionError,
    ServiceNowTimeoutError,
    ServiceNowHTTPError,
    ServiceNowAuthError,
)
from app.services.ticket_orchestrator import TicketOrchestrator
from app.services.conversation_service import SessionState


@pytest.fixture
def mock_env():
    """Setup mock environment variables."""
    old_env = os.environ.copy()
    os.environ["SERVICENOW_INSTANCE"] = "testinstance"
    os.environ["SERVICENOW_USERNAME"] = "testuser"
    os.environ["SERVICENOW_PASSWORD"] = "testpass"
    os.environ["SERVICENOW_TABLE"] = "incident"
    os.environ["USE_MOCK_SERVICENOW"] = "false"
    yield
    os.environ.clear()
    os.environ.update(old_env)


def test_client_url_construction(mock_env):
    # Case 1: Simple instance name
    client1 = ServiceNowClient(instance="foo")
    assert client1.base_url == "https://foo.service-now.com"

    # Case 2: Full URL
    client2 = ServiceNowClient(instance="https://myinstance.custom.com")
    assert client2.base_url == "https://myinstance.custom.com"


def test_create_incident_success(mock_env):
    client = ServiceNowClient()
    mock_response = MagicMock()
    mock_response.status_code = 201
    mock_response.json.return_value = {
        "result": {
            "sys_id": "sys12345",
            "number": "INC0012345",
            "state": "1"
        }
    }

    with patch.object(client.session, "post", return_value=mock_response) as mock_post:
        res = client.create_incident("Short desc", "Description", "VPN", 3)
        assert res["success"] is True
        assert res["sys_id"] == "sys12345"
        assert res["ticket_id"] == "INC0012345"
        assert res["number"] == "INC0012345"
        assert res["state"] == "1"
        mock_post.assert_called_once()
        
        # Verify body sent contains expected fields
        args, kwargs = mock_post.call_args
        assert kwargs["json"]["short_description"] == "Short desc"
        assert kwargs["json"]["description"] == "Description"
        assert kwargs["json"]["category"] == "VPN"


def test_create_incident_http_error(mock_env):
    client = ServiceNowClient()

    with patch.object(client.session, "post", side_effect=requests.exceptions.HTTPError("Bad Request")):
        res = client.create_incident("Short desc", "Description", "VPN")
        assert res["success"] is False
        assert "Connection failed" in res["message"] or "API request failed" in res["message"]


def test_get_incident_success(mock_env):
    client = ServiceNowClient()
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "result": {
            "sys_id": "sys12345",
            "number": "INC0012345",
            "state": "2",
            "short_description": "Found",
        }
    }

    with patch.object(client.session, "get", return_value=mock_response) as mock_get:
        res = client.get_incident("sys12345")
        assert res["success"] is True
        assert res["sys_id"] == "sys12345"
        assert res["ticket_id"] == "INC0012345"
        assert res["state"] == "2"
        assert res["result"]["short_description"] == "Found"
        mock_get.assert_called_once()


def test_update_incident_success(mock_env):
    client = ServiceNowClient()
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "result": {
            "sys_id": "sys12345",
            "number": "INC0012345",
            "state": "2",
            "short_description": "Updated",
        }
    }

    with patch.object(client.session, "put", return_value=mock_response) as mock_put:
        res = client.update_incident("sys12345", {"short_description": "Updated"})
        assert res["success"] is True
        assert res["sys_id"] == "sys12345"
        assert res["result"]["short_description"] == "Updated"
        mock_put.assert_called_once()


def test_close_incident_success(mock_env):
    client = ServiceNowClient()
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "result": {
            "sys_id": "sys12345",
            "state": "7",
            "close_notes": "Solved",
        }
    }

    with patch.object(client.session, "put", return_value=mock_response) as mock_put:
        res = client.close_incident("sys12345", "Solved")
        assert res["success"] is True
        assert res["state"] == "7"
        assert res["result"]["close_notes"] == "Solved"
        mock_put.assert_called_once()


def test_add_work_note_success(mock_env):
    client = ServiceNowClient()
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "result": {
            "sys_id": "sys12345",
            "work_notes": "This is a work note",
        }
    }

    with patch.object(client.session, "put", return_value=mock_response) as mock_put:
        res = client.add_work_note("sys12345", "This is a work note")
        assert res["success"] is True
        assert res["sys_id"] == "sys12345"
        assert res["result"]["work_notes"] == "This is a work note"
        mock_put.assert_called_once()


def test_ticket_orchestrator_integration_success(mock_env):
    mock_client = MagicMock()
    mock_client.create_incident.return_value = {
        "success": True,
        "sys_id": "sys123",
        "ticket_id": "INC007",
        "number": "INC007",
        "state": "1",
        "message": "Success"
    }
    
    state = SessionState(session_id="session123", category="VPN")
    orchestrator = TicketOrchestrator(client=mock_client)
    
    with patch("app.services.conversation_memory.get_history", return_value=[{"text": "My vpn does not work"}]):
        res = orchestrator.create(state, username="alice")
        
    assert res["ticket_id"] == "INC007"
    assert res["servicenow_id"] == "sys123"
    assert res["assigned_team"] == "IT Support"
    mock_client.create_incident.assert_called_once_with(
        short_description="VPN Issue",
        description="My vpn does not work",
        category="VPN",
        severity=3,
    )


def test_ticket_orchestrator_integration_failure(mock_env):
    mock_client = MagicMock()
    mock_client.create_incident.return_value = {
        "success": False,
        "sys_id": "",
        "ticket_id": "",
        "state": "",
        "message": "Connection timed out"
    }
    
    state = SessionState(session_id="session123", category="VPN")
    orchestrator = TicketOrchestrator(client=mock_client)
    
    with patch("app.services.conversation_memory.get_history", return_value=[{"text": "My vpn does not work"}]):
        res = orchestrator.create(state, username="alice")
        
    assert res.get("error") is True
    assert "currently unavailable" in res.get("message", "")


# ─────────────────────────────────────────────────────────────────────────────
# Custom Exceptions Hierarchy Tests
# ─────────────────────────────────────────────────────────────────────────────

def test_client_custom_exceptions_auth_error(mock_env):
    client = ServiceNowClient()
    mock_response = MagicMock()
    mock_response.status_code = 401
    mock_response.json.return_value = {
        "error": {"message": "Invalid username or password"}
    }

    with patch.object(client.session, "get", return_value=mock_response):
        with pytest.raises(ServiceNowAuthError) as exc:
            client._execute_request("GET", "https://foo.service-now.com/api")
        assert exc.value.status_code == 401
        assert "Invalid username or password" in exc.value.message


def test_client_custom_exceptions_http_error(mock_env):
    client = ServiceNowClient()
    mock_response = MagicMock()
    mock_response.status_code = 500
    mock_response.json.return_value = {
        "error": {"message": "Internal error occurred"}
    }

    with patch.object(client.session, "get", return_value=mock_response):
        with pytest.raises(ServiceNowHTTPError) as exc:
            client._execute_request("GET", "https://foo.service-now.com/api")
        assert exc.value.status_code == 500
        assert "Internal error occurred" in exc.value.message


def test_client_custom_exceptions_timeout(mock_env):
    client = ServiceNowClient()
    with patch.object(client.session, "get", side_effect=requests.exceptions.Timeout("Timeout info")):
        with pytest.raises(ServiceNowTimeoutError) as exc:
            client._execute_request("GET", "https://foo.service-now.com/api")
        assert "Request timed out" in str(exc.value)


def test_client_custom_exceptions_connection_error(mock_env):
    client = ServiceNowClient()
    with patch.object(client.session, "get", side_effect=requests.exceptions.ConnectionError("Connection info")):
        with pytest.raises(ServiceNowConnectionError) as exc:
            client._execute_request("GET", "https://foo.service-now.com/api")
        assert "Connection failed" in str(exc.value)


def test_client_safe_request_maps_to_dict_on_error(mock_env):
    client = ServiceNowClient()
    mock_response = MagicMock()
    mock_response.status_code = 403
    mock_response.json.return_value = {
        "error": {"message": "User lacks role permission"}
    }

    with patch.object(client.session, "get", return_value=mock_response):
        res = client.get_incident("sys123")
        assert res["success"] is False
        assert "Authentication failed" in res["message"] or "API request failed" in res["message"]
        assert "User lacks role permission" in res["message"]
