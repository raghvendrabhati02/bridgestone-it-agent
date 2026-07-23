"""
tests/test_ticket_field_mapping_integration.py
─────────────────────────────────────────────────────────────────────────────
Integration tests verifying FieldMappingService integration into the incident creation flow:
  1. VPN issue mapping (VPN -> vpn, GlobalProtect -> globalprotect, Network Team).
  2. Outlook issue mapping (Software -> software, Outlook Crashing -> outlook_crash).
  3. Hardware issue mapping (Hardware -> hardware, Laptop / PC -> laptop).
  4. Invalid mapping handling (fails safely with clear error message, no incident created).
"""

import openpyxl
import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path

from app.services.ticket_service import create_ticket
from app.services.field_mapping_service import FieldMappingService, FieldMappingError, DependencyValidationError
from app.models.servicenow_models import IncidentCreateResponse


@pytest.fixture(autouse=True)
def setup_test_mapping_files(tmp_path, monkeypatch):
    """Set up temporary test Excel mapping files for integration tests."""
    mapping_dir = tmp_path / "servicenow_mappings"
    mapping_dir.mkdir(parents=True, exist_ok=True)

    # 1. sys_choice_mappings.xlsx
    wb1 = openpyxl.Workbook()
    ws1 = wb1.active
    ws1.title = "sys_choice"
    ws1.append(["Element", "Label", "Value", "Dependent Value"])
    rows1 = [
        ["u_type", "Issue", "issue", ""],
        ["u_type", "Service Request", "request", ""],
        ["category", "Hardware", "hardware", "issue"],
        ["category", "Software", "software", "issue"],
        ["category", "VPN", "vpn", "issue"],
        ["subcategory", "GlobalProtect", "globalprotect", "vpn"],
        ["subcategory", "Outlook Crashing", "outlook_crash", "software"],
        ["subcategory", "Laptop / PC", "laptop", "hardware"],
        ["contact_type", "Chat", "chat", ""],
    ]
    for r in rows1:
        ws1.append(r)
    wb1.save(mapping_dir / "sys_choice_mappings.xlsx")

    # 2. assignment_groups.xlsx
    wb2 = openpyxl.Workbook()
    ws2 = wb2.active
    ws2.title = "assignment_groups"
    ws2.append(["Group Name", "Value", "Category"])
    rows2 = [
        ["Network Team", "Network Team", "VPN"],
        ["IT Support", "IT Support", "GENERAL"],
        ["Hardware Team", "Hardware Team", "HARDWARE"],
    ]
    for r in rows2:
        ws2.append(r)
    wb2.save(mapping_dir / "assignment_groups.xlsx")

    # Configure environment variables to point to test mapping dir
    monkeypatch.setenv("SERVICENOW_MAPPINGS_DIR", str(mapping_dir))
    monkeypatch.setenv("SERVICENOW_CHOICE_MAPPINGS_FILE", "sys_choice_mappings.xlsx")
    monkeypatch.setenv("SERVICENOW_GROUPS_MAPPINGS_FILE", "assignment_groups.xlsx")

    return mapping_dir


@patch("app.services.ticket_service.ServiceNowService")
def test_vpn_issue_field_mapping_integration(mock_sn_cls):
    """Test VPN issue field mapping and payload merging."""
    mock_sn_instance = MagicMock()
    mock_sn_instance.enabled = True
    mock_sn_instance.validate_configuration.return_value = (True, "Valid")
    mock_sn_instance.create_incident.return_value = IncidentCreateResponse(
        success=True,
        sys_id="sys_vpn_123",
        number="INC0099901",
        ticket_id="INC0099901",
        state="1",
        message="Created successfully"
    )
    mock_sn_cls.return_value = mock_sn_instance

    result = create_ticket(
        category="VPN",
        created_by="vpn_user",
        issue_description="VPN connection dropping on GlobalProtect",
        assigned_team="Network Team",
        subcategory="GlobalProtect",
        servicenow_service=mock_sn_instance,
    )

    assert result.get("success") is True
    assert result.get("servicenow_number") == "INC0099901"

    # Verify final IncidentCreateRequest payload sent to ServiceNowService
    mock_sn_instance.create_incident.assert_called_once()
    called_req = mock_sn_instance.create_incident.call_args[0][0]
    assert called_req.category == "vpn"
    assert called_req.assignment_group == "Network Team"
    assert called_req.extra_fields["u_type"] in ("issue", "request")
    assert called_req.extra_fields["subcategory"] == "globalprotect"
    assert called_req.extra_fields["contact_type"] == "chat"


@patch("app.services.ticket_service.ServiceNowService")
def test_outlook_issue_field_mapping_integration(mock_sn_cls):
    """Test Outlook software issue field mapping and payload merging."""
    mock_sn_instance = MagicMock()
    mock_sn_instance.enabled = True
    mock_sn_instance.validate_configuration.return_value = (True, "Valid")
    mock_sn_instance.create_incident.return_value = IncidentCreateResponse(
        success=True,
        sys_id="sys_soft_456",
        number="INC0099902",
        ticket_id="INC0099902",
        state="1",
        message="Created successfully"
    )
    mock_sn_cls.return_value = mock_sn_instance

    result = create_ticket(
        category="Software",
        created_by="outlook_user",
        issue_description="Outlook crashing on start",
        assigned_team="IT Support",
        subcategory="Outlook Crashing",
        servicenow_service=mock_sn_instance,
    )

    assert result.get("success") is True, f"Expected success=True, got: {result}"

    mock_sn_instance.create_incident.assert_called_once()
    called_req = mock_sn_instance.create_incident.call_args[0][0]
    assert called_req.category == "software"
    assert called_req.extra_fields["subcategory"] == "outlook_crash"


@patch("app.services.ticket_service.ServiceNowService")
def test_hardware_issue_field_mapping_integration(mock_sn_cls):
    """Test Hardware issue field mapping and payload merging."""
    mock_sn_instance = MagicMock()
    mock_sn_instance.enabled = True
    mock_sn_instance.validate_configuration.return_value = (True, "Valid")
    mock_sn_instance.create_incident.return_value = IncidentCreateResponse(
        success=True,
        sys_id="sys_hard_789",
        number="INC0099903",
        ticket_id="INC0099903",
        state="1",
        message="Created successfully"
    )
    mock_sn_cls.return_value = mock_sn_instance

    result = create_ticket(
        category="Hardware",
        created_by="hw_user",
        issue_description="Laptop monitor flickering",
        assigned_team="Hardware Team",
        subcategory="Laptop / PC",
        servicenow_service=mock_sn_instance,
    )

    assert result.get("success") is True, f"Expected success=True, got: {result}"

    mock_sn_instance.create_incident.assert_called_once()
    called_req = mock_sn_instance.create_incident.call_args[0][0]
    assert called_req.category == "hardware"
    assert called_req.assignment_group == "Hardware Team"
    assert called_req.extra_fields["subcategory"] == "laptop"


@patch("app.services.ticket_service.ServiceNowService")
def test_invalid_mapping_fails_safely_without_creating_incident(mock_sn_cls):
    """Verify that an invalid mapping fails safely and DOES NOT create a ServiceNow incident."""
    mock_sn_instance = MagicMock()
    mock_sn_instance.enabled = True
    mock_sn_instance.validate_configuration.return_value = (True, "Valid")
    mock_sn_instance.create_incident.return_value = IncidentCreateResponse(
        success=False,
        sys_id="",
        number="",
        ticket_id="",
        state="",
        message="Mapping failed"
    )
    mock_sn_cls.return_value = mock_sn_instance

    # Pass invalid category 'NonExistentCategory'
    result = create_ticket(
        category="NonExistentCategory",
        created_by="test_user",
        issue_description="Test invalid category",
        assigned_team="IT Support",
        servicenow_service=mock_sn_instance,
    )

    assert result.get("error") is True, f"Expected error=True, got: {result}"
    assert result.get("success") is False
    assert result.get("servicenow_error") is True
    assert "Field Mapping Failure" in result.get("message", "")

    # CRITICAL: Verify create_incident was NEVER called on ServiceNow API
    mock_sn_instance.create_incident.assert_not_called()
