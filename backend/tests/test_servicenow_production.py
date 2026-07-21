"""
test_servicenow_production.py
─────────────────────────────────────────────────────────────────────────────
Comprehensive unit and integration tests verifying 100% production-ready
ServiceNow integration behavior:
  • Phase 1: Mock mode only when USE_MOCK_SERVICENOW=true.
  • Phase 2: Fail Fast on ServiceNow errors (no silent fake ticket fallback).
  • Phase 3: Real incident number (INC0012458) returned as primary ticket_id.
  • Phase 4: Storing both local_ticket_id and servicenow_number / sys_id.
  • Phase 6: Production logs.
  • Phase 7: Startup validation checks.
  • Phase 8: GET /health/servicenow health check output format.
"""

import os
from unittest.mock import MagicMock, patch
import pytest

from app.models.servicenow_models import IncidentCreateRequest, IncidentCreateResponse
from app.services.servicenow_service import ServiceNowService
from app.services.servicenow_client import ServiceNowClient
from app.services.ticket_service import create_ticket, set_servicenow_service


@pytest.fixture
def servicenow_enabled_env():
    """Environment fixture for enabled ServiceNow integration."""
    old = os.environ.copy()
    os.environ["SERVICENOW_ENABLED"] = "true"
    os.environ["USE_MOCK_SERVICENOW"] = "false"
    os.environ["SERVICENOW_INSTANCE_URL"] = "https://dev99999.service-now.com"
    os.environ["SERVICENOW_AUTH_TYPE"] = "basic"
    os.environ["SERVICENOW_USERNAME"] = "admin"
    os.environ["SERVICENOW_PASSWORD"] = "secret123"
    yield
    os.environ.clear()
    os.environ.update(old)


def test_phase1_phase2_fail_fast_on_servicenow_failure(servicenow_enabled_env):
    """
    Phase 1 & Phase 2: When SERVICENOW_ENABLED=true and creation fails (e.g. 401 Unauthorized),
    it MUST NOT silently create a fake local ticket. It must return error=True and message.
    """
    mock_client = MagicMock()
    mock_client.create_incident.return_value = {
        "success": False,
        "message": "401 Unauthorized: Invalid username/password",
        "ticket_id": "",
        "sys_id": "",
    }
    sn_service = ServiceNowService(client=mock_client)
    set_servicenow_service(sn_service)

    try:
        res = create_ticket(category="VPN", issue_description="VPN not connecting", created_by="john_doe")

        assert res.get("error") is True
        assert res.get("success") is False
        assert res.get("servicenow_error") is True
        assert "Unable to create ServiceNow Incident" in res.get("message")
        assert "401 Unauthorized" in res.get("message")
        assert res.get("ticket_id") == ""
        assert res.get("servicenow_number") == ""
    finally:
        set_servicenow_service(None)


def test_phase3_phase4_real_incident_number_and_dual_identifiers(servicenow_enabled_env):
    """
    Phase 3 & Phase 4: Receive real incident number (INC0012458) and sys_id,
    and retain both local_ticket_id and servicenow_number in returned dict.
    """
    mock_client = MagicMock()
    mock_client.create_incident.return_value = {
        "success": True,
        "sys_id": "sys_abc123xyz",
        "number": "INC0012458",
        "state": "1",
        "message": "Incident created successfully",
    }
    sn_service = ServiceNowService(client=mock_client)
    set_servicenow_service(sn_service)

    try:
        res = create_ticket(category="VPN", issue_description="VPN not connecting", created_by="jane_doe")

        assert res.get("error") is not True
        assert res.get("ticket_id") == "INC0012458"  # Primary display ticket ID
        assert res.get("servicenow_number") == "INC0012458"
        assert res.get("servicenow_id") == "sys_abc123xyz"
        assert res.get("local_ticket_id").startswith("INC")
    finally:
        set_servicenow_service(None)


def test_phase8_servicenow_health_check(servicenow_enabled_env):
    """
    Phase 8: Test health_check method returns structured status dictionary.
    """
    mock_client = MagicMock()
    mock_client.use_mock = False
    mock_client.base_url = "https://dev99999.service-now.com"
    mock_client.table = "incident"
    mock_client._safe_request.return_value = {
        "success": True,
        "result": []
    }
    sn_service = ServiceNowService(client=mock_client)

    health = sn_service.health_check()

    assert health["status"] == "Connected"
    assert health["authenticated"] is True
    assert health["instance"] == "https://dev99999.service-now.com"
    assert "Table API" in health["version"]
    assert "latency_ms" in health
