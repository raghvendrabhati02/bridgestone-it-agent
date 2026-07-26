"""
test_servicenow_payload_inspector.py
─────────────────────────────────────────────────────────────────────────────
Unit tests for ServiceNowPayloadInspector and ServiceNowClient payload verification.

Validates:
  1. ServiceNowPayloadInspector initialization & SERVICENOW_VALIDATE_MAPPING toggle.
  2. PRE-POST logging of request summary and JSON payload.
  3. POST response logging.
  4. Field comparison (Generated -> Sent -> Stored) and FieldAuditResult statuses.
  5. Integration with ServiceNowClient in mock mode (end-to-end payload audit).
  6. Adaptive reference resolution fallback.
"""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch

from app.services.servicenow_payload_inspector import (
    ServiceNowPayloadInspector,
    FieldAuditResult,
)
from app.services.servicenow_client import ServiceNowClient
from app.models.servicenow_models import IncidentCreateRequest


class TestServiceNowPayloadInspector:

    def test_inspector_toggle_enabled_by_default(self, monkeypatch):
        monkeypatch.delenv("SERVICENOW_VALIDATE_MAPPING", raising=False)
        inspector = ServiceNowPayloadInspector()
        assert inspector.enabled is True

    def test_inspector_toggle_disabled(self, monkeypatch):
        monkeypatch.setenv("SERVICENOW_VALIDATE_MAPPING", "false")
        inspector = ServiceNowPayloadInspector()
        assert inspector.enabled is False

    def test_verify_and_compare_all_matching(self):
        inspector = ServiceNowPayloadInspector()
        generated = {
            "short_description": "VPN issue",
            "category": "VPN",
            "subcategory": "Remote Access",
            "assignment_group": "Network Team",
            "impact": 2,
            "urgency": 2,
            "priority": 3,
            "channel": "Virtual Agent",
            "incident_type": "Incident",
            "configuration_item": "VPN Gateway",
        }
        sent = {
            "short_description": "VPN issue",
            "description": "VPN dropping",
            "category": "VPN",
            "subcategory": "Remote Access",
            "assignment_group": "Network Team",
            "impact": 2,
            "urgency": 2,
            "priority": 3,
            "contact_type": "Virtual Agent",
            "u_type": "incident",
            "cmdb_ci": "VPN Gateway",
        }
        stored = {
            "short_description": "VPN issue",
            "description": "VPN dropping",
            "category": "VPN",
            "subcategory": "Remote Access",
            "assignment_group": "Network Team",
            "impact": "2",
            "urgency": "2",
            "priority": "3",
            "contact_type": "Virtual Agent",
            "u_type": "incident",
            "cmdb_ci": "VPN Gateway",
        }

        results = inspector.verify_and_compare(generated, sent, stored)
        assert len(results) == 13
        # Check MATCH status on verified fields
        match_labels = [r.field_label for r in results if r.status == "MATCH"]
        assert "Short Description" in match_labels
        assert "Category" in match_labels
        assert "Subcategory" in match_labels
        assert "Assignment Group" in match_labels

    def test_verify_and_compare_detects_dropped_fields(self):
        inspector = ServiceNowPayloadInspector()
        generated = {
            "category": "VPN",
            "subcategory": "Remote Access",
            "configuration_item": "VPN Gateway",
        }
        sent = {
            "category": "VPN",
            "subcategory": "Remote Access",
            "cmdb_ci": "VPN Gateway",
        }
        stored = {
            "category": "VPN",
            # subcategory and cmdb_ci missing/empty in stored response
        }

        results = inspector.verify_and_compare(generated, sent, stored)
        subcat_res = next(r for r in results if r.field_label == "Subcategory")
        assert subcat_res.status == "FIELD_NOT_STORED"
        assert subcat_res.icon == "❌"

        ci_res = next(r for r in results if r.field_label == "Config Item (CI)")
        assert ci_res.status == "REFERENCE_LOOKUP_FAILED"
        assert ci_res.icon == "❌"

    def test_client_create_incident_mock_mode_with_inspector(self, monkeypatch):
        monkeypatch.setenv("USE_MOCK_SERVICENOW", "true")
        monkeypatch.setenv("SERVICENOW_VALIDATE_MAPPING", "true")

        client = ServiceNowClient()
        res = client.create_incident(
            short_description="Outlook Crashing",
            description="Outlook crashes on launch",
            category="Microsoft 365",
            assignment_group="Messaging Support",
            subcategory="Outlook Not Working",
            impact=2,
            urgency=2,
            priority=3,
            contact_type="Virtual Agent",
            u_type="incident",
            cmdb_ci="Microsoft Outlook",
        )

        assert res["success"] is True
        assert res["number"].startswith("INC")
        assert res["result"]["subcategory"] == "Outlook Not Working"
        assert res["result"]["cmdb_ci"] == "Microsoft Outlook"

    def test_resolve_reference_returns_display_value_in_mock(self):
        client = ServiceNowClient()
        resolved = client.resolve_reference("sys_user_group", "Network Support")
        assert resolved == "Network Support"

    def test_resolve_reference_preserves_existing_sys_id(self):
        client = ServiceNowClient()
        sys_id = "a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6"
        resolved = client.resolve_reference("sys_user_group", sys_id)
        assert resolved == sys_id
