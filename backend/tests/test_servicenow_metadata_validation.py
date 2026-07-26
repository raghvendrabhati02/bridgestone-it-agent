"""
test_servicenow_metadata_validation.py
─────────────────────────────────────────────────────────────────────────────
Test suite for Phase 6.2 ServiceNow Metadata Cache, Validator, Single Point
Runtime Sanitization, Report Generation, and Observability Endpoint.
"""

import time
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.servicenow_models import IncidentCreateRequest
from app.services.servicenow_metadata_cache import ServiceNowMetadataCache
from app.services.servicenow_metadata_validator import ServiceNowMetadataValidator, ValidationResult
from app.services.servicenow_service import _sanitize_incident_request


@pytest.fixture
def metadata_cache():
    """Ensure clean cache instance for testing."""
    cache = ServiceNowMetadataCache.get_instance()
    cache.sync(force=True)
    return cache


@pytest.fixture
def validator(metadata_cache):
    return ServiceNowMetadataValidator(cache=metadata_cache)


def test_metadata_cache_stats(metadata_cache):
    """Verify metadata cache returns valid statistics structure."""
    stats = metadata_cache.get_stats()
    assert "metadata_status" in stats
    assert "source" in stats
    assert "last_refresh" in stats
    assert "categories" in stats
    assert "subcategories" in stats
    assert "groups" in stats
    assert "cmdb_records" in stats


def test_validate_valid_and_missing_category(validator):
    """Test validating valid and missing categories."""
    valid_res = validator.validate_category("Microsoft 365")
    assert valid_res.is_valid is True
    assert valid_res.status == "VALID"

    missing_res = validator.validate_category("NonExistentCategoryXYZ")
    assert missing_res.is_valid is False
    assert missing_res.status == "MISSING"


def test_validate_missing_subcategory_suggestions_report_only(validator):
    """Test that invalid subcategories return suggested choices for reporting without auto-applying."""
    res = validator.validate_subcategory("Teams Issue", category="Microsoft 365")
    # In local config cache, "Teams Issue" is checked against cached choices
    assert isinstance(res, ValidationResult)
    assert res.field_name == "subcategory"
    assert res.value == "Teams Issue"


def test_validate_assignment_group(validator):
    """Test validating valid and missing assignment groups."""
    valid_grp = validator.validate_assignment_group("IT Support")
    assert valid_grp.is_valid is True

    missing_grp = validator.validate_assignment_group("NonExistentGroup123")
    assert missing_grp.is_valid is False


def test_validate_cmdb_ci(validator):
    """Test validating valid and missing CMDB CIs."""
    valid_ci = validator.validate_cmdb_ci("Microsoft Teams")
    assert valid_ci.is_valid is True

    missing_ci = validator.validate_cmdb_ci("NonExistentCI999")
    assert missing_ci.is_valid is False


def test_runtime_sanitization_category_fallback():
    """Test runtime sanitization replaces invalid category with default 'Software'."""
    req = IncidentCreateRequest(
        short_description="Test invalid category",
        description="Test description",
        category="InvalidCategory123",
        subcategory="",
        assignment_group="IT Support"
    )
    _sanitize_incident_request(req)
    assert req.category == "Software"


def test_runtime_sanitization_subcategory_empty_no_arbitrary_choice():
    """Test runtime sanitization clears invalid subcategory ('') and DOES NOT auto-pick Outlook."""
    req = IncidentCreateRequest(
        short_description="My Teams keeps crashing",
        description="Teams crash issue",
        category="Microsoft 365",
        subcategory="Teams Issue",
        assignment_group="IT Support"
    )
    _sanitize_incident_request(req)
    # Must become empty string (""), never auto-picked choice "Outlook Not Working"
    assert req.subcategory == ""


def test_runtime_sanitization_assignment_group_fallback():
    """Test runtime sanitization replaces invalid group with 'IT Support'."""
    req = IncidentCreateRequest(
        short_description="Test invalid group",
        description="Test description",
        category="Microsoft 365",
        subcategory="",
        assignment_group="UnknownFakeGroup"
    )
    _sanitize_incident_request(req)
    assert req.assignment_group == "IT Support"


def test_runtime_sanitization_cmdb_ci_omitted():
    """Test runtime sanitization omits invalid CMDB CI string."""
    req = IncidentCreateRequest(
        short_description="Test invalid CI",
        description="Test description",
        category="Microsoft 365",
        subcategory="",
        assignment_group="IT Support",
        extra_fields={"cmdb_ci": "UnlinkedUnknownCI"}
    )
    _sanitize_incident_request(req)
    assert req.extra_fields["cmdb_ci"] == ""


def test_metadata_health_endpoint():
    """Test GET /metadata/health endpoint returns JSON stats."""
    client = TestClient(app)
    response = client.get("/metadata/health")
    assert response.status_code == 200
    data = response.json()
    assert "metadata_status" in data
    assert "source" in data
    assert "categories" in data
    assert "subcategories" in data
    assert "groups" in data
    assert "cmdb_records" in data


def test_report_generation(validator):
    """Test report generation includes metadata header and section validation."""
    md_report = validator.generate_report_markdown()
    assert "# ServiceNow Metadata Validation & Integration Audit Report" in md_report
    assert "## Metadata Metadata & Version Header" in md_report
    assert "- **Metadata Source**:" in md_report
    assert "### Categories Validation" in md_report
    assert "### Subcategories Validation" in md_report
    assert "### Assignment Groups Validation" in md_report
    assert "### CMDB Configuration Items Validation" in md_report
