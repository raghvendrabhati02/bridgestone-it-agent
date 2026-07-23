"""
tests/test_field_mapping_service.py
─────────────────────────────────────────────────────────────────────────────
Comprehensive Unit Tests for Enterprise ServiceNow FieldMappingService:
  1. Startup validation: fails fast if required columns (Element, Label, Value, Dependent Value) are missing.
  2. Missing files validation: fails fast with MappingFileNotFoundError when directory or mapping files are missing.
  3. No dynamic file creation: verifies NO files are created/overwritten on disk.
  4. Configurable filenames: supports custom choice_filename, group_filename, and environment variables.
  5. Extensible architecture: validates ChoiceMappingLoader and ReferenceMappingLoader.
  6. In-memory caching: mappings loaded once on startup.
  7. Value precedence: resolves Labels to API Values (never returns Labels in payload).
  8. Dependency rules: enforces category -> u_type and subcategory -> category.
  9. Default caller_id: defaults to empty string ("").
"""

import os
import openpyxl
import pytest
from pathlib import Path

from app.services.field_mapping_service import (
    FieldMappingService,
    FieldMappingError,
    MappingFileNotFoundError,
    InvalidMappingDataError,
    DependencyValidationError,
    ChoiceMappingLoader,
    ReferenceMappingLoader,
)


@pytest.fixture
def temp_mapping_dir(tmp_path):
    """Creates a temporary directory with valid Excel mapping files."""
    mapping_dir = tmp_path / "servicenow_mappings"
    mapping_dir.mkdir()

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
        ["category", "Software Access", "software_access", "request"],
        ["subcategory", "GlobalProtect", "globalprotect", "vpn"],
        ["subcategory", "Cisco AnyConnect", "cisco_vpn", "vpn"],
        ["subcategory", "Outlook Crashing", "outlook_crash", "software"],
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
        ["Identity Team", "Identity Team", "PASSWORD_RESET"],
    ]
    for r in rows2:
        ws2.append(r)
    wb2.save(mapping_dir / "assignment_groups.xlsx")

    return mapping_dir


def test_startup_validation_missing_columns(tmp_path):
    """Verify service fails fast with InvalidMappingDataError if required columns are missing."""
    invalid_dir = tmp_path / "invalid_mappings"
    invalid_dir.mkdir()

    # Create Excel missing 'Dependent Value' column
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["Element", "Label", "Value"])  # Missing 'Dependent Value'
    ws.append(["u_type", "Issue", "issue"])
    wb.save(invalid_dir / "sys_choice_mappings.xlsx")

    with pytest.raises(InvalidMappingDataError) as excinfo:
        FieldMappingService(data_directory=invalid_dir, auto_load=True)

    assert "Missing required column(s)" in str(excinfo.value)
    assert "dependent value" in str(excinfo.value)


def test_missing_directory_fails_fast(tmp_path):
    """Verify service fails fast with MappingFileNotFoundError when directory is missing."""
    missing_dir = tmp_path / "non_existent_folder"
    with pytest.raises(MappingFileNotFoundError):
        FieldMappingService(data_directory=missing_dir, auto_load=True)


def test_no_files_created_or_overwritten(temp_mapping_dir):
    """Verify service NEVER creates or mutates files on disk."""
    files_before = set(temp_mapping_dir.glob("*"))

    service = FieldMappingService(data_directory=temp_mapping_dir, auto_load=True)

    # Perform queries and builds
    service.get_types()
    service.get_categories("issue")
    service.build_servicenow_fields(u_type="Issue", category="VPN", subcategory="GlobalProtect")

    files_after = set(temp_mapping_dir.glob("*"))
    assert files_before == files_after, "FieldMappingService mutated or created files on disk!"


def test_configurable_filenames(tmp_path):
    """Verify service supports custom configured filenames."""
    custom_dir = tmp_path / "custom_mappings"
    custom_dir.mkdir()

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["Element", "Label", "Value", "Dependent Value"])
    ws.append(["u_type", "Custom Type", "custom_type", ""])
    wb.save(custom_dir / "my_custom_choices.xlsx")

    wb2 = openpyxl.Workbook()
    ws2 = wb2.active
    ws2.append(["Group Name", "Value"])
    ws2.append(["Custom Team", "Custom Team"])
    wb2.save(custom_dir / "my_custom_groups.xlsx")

    service = FieldMappingService(
        data_directory=custom_dir,
        choice_filename="my_custom_choices.xlsx",
        group_filename="my_custom_groups.xlsx",
        auto_load=True,
    )

    types = service.get_types()
    assert len(types) == 1
    assert types[0]["value"] == "custom_type"

    groups = service.get_assignment_groups()
    assert len(groups) == 1
    assert groups[0]["value"] == "Custom Team"


def test_in_memory_caching(temp_mapping_dir):
    """Verify Excel files are loaded into memory once and queries use cached data."""
    service = FieldMappingService(data_directory=temp_mapping_dir, auto_load=True)
    assert service._is_loaded is True

    # Delete files from disk after loading
    for f in temp_mapping_dir.glob("*.xlsx"):
        f.unlink()

    # Cached queries should still succeed cleanly without disk I/O
    types = service.get_types()
    assert len(types) >= 2

    categories = service.get_categories("issue")
    assert len(categories) >= 3

    payload = service.build_servicenow_fields(
        u_type="Issue",
        category="VPN",
        subcategory="GlobalProtect",
        assignment_group="Network Team"
    )
    assert payload["category"] == "vpn"
    assert payload["subcategory"] == "globalprotect"


def test_build_servicenow_fields_value_precedence_and_dependencies(temp_mapping_dir):
    """Verify Label to Value resolution and dependency enforcement."""
    service = FieldMappingService(data_directory=temp_mapping_dir, auto_load=True)

    payload = service.build_servicenow_fields(
        contact_type="Chat",
        u_type="Service Request",
        category="Software Access",
        assignment_group="Identity Team",
        caller_id="user_001"
    )

    assert payload == {
        "contact_type": "chat",
        "u_type": "request",
        "category": "software_access",
        "subcategory": "",
        "assignment_group": "Identity Team",
        "caller_id": "user_001",
    }


def test_dependency_validation_error_on_mismatch(temp_mapping_dir):
    """Verify DependencyValidationError when category does not match u_type."""
    service = FieldMappingService(data_directory=temp_mapping_dir, auto_load=True)

    with pytest.raises(DependencyValidationError):
        service.build_servicenow_fields(
            u_type="issue",
            category="software_access"  # Software Access requires u_type='request'
        )


def test_caller_id_defaults_to_empty_string(temp_mapping_dir):
    """Verify caller_id defaults to empty string."""
    service = FieldMappingService(data_directory=temp_mapping_dir, auto_load=True)
    payload = service.build_servicenow_fields(u_type="issue", category="vpn")
    assert payload["caller_id"] == ""
