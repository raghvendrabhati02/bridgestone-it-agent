"""
test_incident_enrichment_service.py
──────────────────────────────────────────────────────────────────────────────
Unit tests for IncidentEnrichmentService.

Coverage:
  • IncidentMetadata.to_extra_fields() contract
  • _Rules static methods (all derivations)
  • Priority matrix completeness
  • IncidentEnrichmentService.enrich() — all category branches
  • IncidentEnrichmentService.enrich() — urgency escalation for UNRESOLVED state
  • IncidentEnrichmentService.enrich() — FieldMappingService integration (mocked)
  • IncidentEnrichmentService.enrich() — graceful fallback on any exception
  • Safe-default fallback path
  • enrich_incident() convenience function
"""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch
from dataclasses import dataclass
from typing import Optional

from app.services.incident_enrichment_service import (
    IncidentEnrichmentService,
    IncidentMetadata,
    _Rules,
    _PRIORITY_MATRIX,
    _CI_MAP,
    _CATEGORY_IMPACT,
    _CATEGORY_URGENCY,
    enrich_incident,
)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers / Fixtures
# ─────────────────────────────────────────────────────────────────────────────

def make_service(field_mapper=None) -> IncidentEnrichmentService:
    return IncidentEnrichmentService(field_mapping_service=field_mapper)


@dataclass
class _FakeTSState:
    """Minimal fake TroubleshootingState for urgency escalation tests."""
    resolution_status: Optional[object] = None


class _ResEnum:
    def __init__(self, val: str):
        self.value = val


# ─────────────────────────────────────────────────────────────────────────────
# IncidentMetadata tests
# ─────────────────────────────────────────────────────────────────────────────

class TestIncidentMetadata:
    def _make(self, **overrides) -> IncidentMetadata:
        defaults = dict(
            category="VPN",
            subcategory="Remote Access",
            assignment_group="Network Support",
            impact=2,
            urgency=2,
            priority=3,
            priority_label="3 - Moderate",
        )
        defaults.update(overrides)
        return IncidentMetadata(**defaults)

    def test_to_extra_fields_baseline(self):
        meta = self._make()
        extra = meta.to_extra_fields()
        assert extra["subcategory"] == "Remote Access"
        assert extra["contact_type"] == "Virtual Agent"
        assert extra["u_type"] == "incident"
        # Optional fields absent when None
        assert "cmdb_ci" not in extra
        assert "business_service" not in extra
        assert "location" not in extra

    def test_to_extra_fields_with_ci(self):
        meta = self._make(configuration_item="VPN Gateway")
        extra = meta.to_extra_fields()
        assert extra["cmdb_ci"] == "VPN Gateway"

    def test_to_extra_fields_with_business_service(self):
        meta = self._make(business_service="IT Services")
        extra = meta.to_extra_fields()
        assert extra["business_service"] == "IT Services"

    def test_to_extra_fields_with_location(self):
        meta = self._make(location="London HQ")
        extra = meta.to_extra_fields()
        assert extra["location"] == "London HQ"

    def test_to_extra_fields_all_optional(self):
        meta = self._make(
            configuration_item="SAP ERP System",
            business_service="Finance",
            location="Tokyo",
        )
        extra = meta.to_extra_fields()
        assert extra["cmdb_ci"] == "SAP ERP System"
        assert extra["business_service"] == "Finance"
        assert extra["location"] == "Tokyo"

    def test_channel_and_type_defaults(self):
        meta = self._make()
        assert meta.channel == "Virtual Agent"
        assert meta.incident_type == "Incident"


# ─────────────────────────────────────────────────────────────────────────────
# _Rules static method tests
# ─────────────────────────────────────────────────────────────────────────────

class TestRules:
    def test_normalize_empty_returns_general(self):
        assert _Rules.normalize_category("") == "general"

    def test_normalize_strips_and_lowercases(self):
        assert _Rules.normalize_category("  VPN  ") == "vpn"

    def test_normalize_preserves_multi_word(self):
        assert _Rules.normalize_category("Microsoft 365") == "microsoft 365"

    def test_derive_subcategory_known_keys(self):
        assert _Rules.derive_subcategory("vpn")      == "VPN-Global Protect"
        assert _Rules.derive_subcategory("outlook")  == "Outlook Not Working"
        assert _Rules.derive_subcategory("printer")  == "Printer Offline"
        assert _Rules.derive_subcategory("password") == "Password Reset"

    def test_derive_subcategory_unknown_returns_default(self):
        assert _Rules.derive_subcategory("xyz_unknown") is None

    def test_derive_ci_known(self):
        assert _Rules.derive_configuration_item("vpn")     == "VPN Gateway"
        assert _Rules.derive_configuration_item("outlook") == "Microsoft Outlook"
        assert _Rules.derive_configuration_item("sap")     == "SAP ERP System"
        assert _Rules.derive_configuration_item("printer") == "Network Printer"

    def test_derive_ci_unknown_returns_none(self):
        assert _Rules.derive_configuration_item("unknown_category") is None

    def test_derive_impact_categories(self):
        assert _Rules.derive_impact("vpn")     == 2   # Medium
        assert _Rules.derive_impact("sap")     == 1   # High
        assert _Rules.derive_impact("printer") == 3   # Low
        assert _Rules.derive_impact("network") == 1   # High

    def test_derive_impact_unknown_defaults_to_low(self):
        assert _Rules.derive_impact("xyz") == 3

    def test_derive_urgency_categories(self):
        assert _Rules.derive_urgency("vpn")      == 2
        assert _Rules.derive_urgency("password") == 1
        assert _Rules.derive_urgency("printer")  == 3
        assert _Rules.derive_urgency("network")  == 1

    def test_derive_urgency_unknown_defaults_to_low(self):
        assert _Rules.derive_urgency("xyz") == 3

    def test_derive_urgency_escalates_for_unresolved_state(self):
        state = _FakeTSState(resolution_status=_ResEnum("UNRESOLVED"))
        # printer normally has urgency=3; unresolved should cap at 2
        result = _Rules.derive_urgency("printer", state)
        assert result == 2

    def test_derive_urgency_no_escalation_when_already_high(self):
        state = _FakeTSState(resolution_status=_ResEnum("UNRESOLVED"))
        # password already urgency=1; should remain 1
        result = _Rules.derive_urgency("password", state)
        assert result == 1

    def test_derive_priority_matrix_all_cells(self):
        """All 9 matrix cells must resolve and return (int, str)."""
        for impact in (1, 2, 3):
            for urgency in (1, 2, 3):
                p_int, p_label = _Rules.derive_priority(impact, urgency)
                assert isinstance(p_int, int)
                assert isinstance(p_label, str)
                assert 1 <= p_int <= 4
                assert "–" in p_label or "-" in p_label

    def test_derive_priority_critical(self):
        p_int, p_label = _Rules.derive_priority(1, 1)
        assert p_int == 1
        assert "Critical" in p_label

    def test_derive_priority_low(self):
        p_int, p_label = _Rules.derive_priority(3, 3)
        assert p_int == 4
        assert "Low" in p_label

    def test_derive_priority_bad_input_defaults_moderate(self):
        p_int, p_label = _Rules.derive_priority(9, 9)  # not in matrix
        assert p_int == 3
        assert "Moderate" in p_label


# ─────────────────────────────────────────────────────────────────────────────
# IncidentEnrichmentService.enrich() — category-specific behavior
# ─────────────────────────────────────────────────────────────────────────────

class TestIncidentEnrichmentService:
    def test_vpn_enrichment(self):
        meta = make_service().enrich(category="VPN")
        assert meta.category == "VPN"
        assert meta.subcategory == "VPN-Global Protect"
        assert meta.impact == 2
        assert meta.urgency == 2
        assert meta.configuration_item == "VPN Gateway"
        assert meta.channel == "Virtual Agent"
        assert meta.incident_type == "Incident"

    def test_outlook_enrichment(self):
        meta = make_service().enrich(category="Outlook")
        assert meta.subcategory == "Outlook Not Working"
        assert meta.configuration_item == "Microsoft Office Suite"
        assert meta.impact == 2

    def test_sap_enrichment(self):
        meta = make_service().enrich(category="SAP")
        assert meta.subcategory == "Installation Request"
        assert meta.impact == 1    # High
        assert meta.urgency == 1   # High
        assert meta.priority == 1  # Critical
        assert "Critical" in meta.priority_label
        assert meta.configuration_item == "SAP ERP System"

    def test_printer_enrichment(self):
        meta = make_service().enrich(category="printer")
        assert meta.subcategory == "Printer Offline"
        assert meta.impact == 3   # Low
        assert meta.urgency == 3  # Low
        assert meta.priority == 4 # Low
        assert "Low" in meta.priority_label

    def test_network_enrichment(self):
        meta = make_service().enrich(category="Network")
        assert meta.impact == 1
        assert meta.urgency == 1
        assert meta.priority == 1

    def test_unknown_category_safe_defaults(self):
        meta = make_service().enrich(category="unknown_xyz_category")
        assert meta.category == "unknown_xyz_category"
        assert meta.subcategory is None
        assert meta.impact == 3
        assert meta.urgency == 3
        assert meta.priority == 4

    def test_empty_category_safe_defaults(self):
        meta = make_service().enrich(category="")
        assert meta.category in ("", "General")
        # Must not raise; fields must be set
        assert isinstance(meta.impact, int)
        assert isinstance(meta.urgency, int)

    def test_assignment_group_passed_through(self):
        meta = make_service().enrich(category="VPN", assignment_group="Network Team")
        assert meta.assignment_group == "Network Team"

    def test_location_propagated(self):
        meta = make_service().enrich(category="VPN", location="Berlin HQ")
        assert meta.location == "Berlin HQ"

    def test_priority_matrix_consistency(self):
        """SAP: impact=1, urgency=1 → priority=1 (Critical)."""
        meta = make_service().enrich(category="SAP")
        p_int, p_label = _Rules.derive_priority(meta.impact, meta.urgency)
        assert p_int == meta.priority
        assert p_label == meta.priority_label

    # ── TroubleshootingState integration ─────────────────────────────────────

    def test_urgency_escalates_for_unresolved(self):
        state = _FakeTSState(resolution_status=_ResEnum("UNRESOLVED"))
        # printer normally urgency=3; should be capped at 2 when unresolved
        meta = make_service().enrich(category="printer", troubleshooting_state=state)
        assert meta.urgency == 2

    def test_urgency_escalates_for_escalated(self):
        state = _FakeTSState(resolution_status=_ResEnum("ESCALATED"))
        meta = make_service().enrich(category="printer", troubleshooting_state=state)
        assert meta.urgency == 2

    def test_urgency_not_escalated_when_resolved(self):
        state = _FakeTSState(resolution_status=_ResEnum("RESOLVED"))
        meta = make_service().enrich(category="printer", troubleshooting_state=state)
        assert meta.urgency == 3  # unchanged

    # ── FieldMappingService integration ──────────────────────────────────────

    def test_field_mapper_resolves_assignment_group(self):
        mock_mapper = MagicMock()
        mock_mapper.build_servicenow_fields.return_value = {
            "assignment_group": "SN-Network-Support-Sys-ID",
            "category":         "vpn",
            "subcategory":      "",
            "contact_type":     "chat",
            "u_type":           "issue",
        }
        mock_mapper.get_subcategories.return_value = []

        meta = IncidentEnrichmentService(field_mapping_service=mock_mapper).enrich(
            category="VPN",
            assignment_group="Network Team",
        )
        assert meta.assignment_group == "SN-Network-Support-Sys-ID"
        mock_mapper.build_servicenow_fields.assert_called_once()

    def test_field_mapper_failure_falls_back_to_given_group(self):
        mock_mapper = MagicMock()
        mock_mapper.build_servicenow_fields.side_effect = Exception("FMS error")
        mock_mapper.get_subcategories.return_value = []

        meta = IncidentEnrichmentService(field_mapping_service=mock_mapper).enrich(
            category="VPN",
            assignment_group="Network Team",
        )
        assert meta.assignment_group == "Network Team"
        assert meta.category == "VPN"

    def test_classification_category_preferred(self):
        class FakeClassification:
            category = "Outlook"
            subcategory = "Email Client"
        meta = make_service().enrich(
            category="GENERAL",
            classification=FakeClassification(),
        )
        assert meta.category == "Microsoft 365"

    def test_classification_subcategory_preferred(self):
        class FakeClassification:
            category = "Outlook"
            subcategory = "Calendar"
        meta = make_service().enrich(
            category="GENERAL",
            classification=FakeClassification(),
        )
        assert meta.subcategory == "Calendar"

    # ── Graceful fallback on internal exception ───────────────────────────────

    def test_enrich_never_raises_on_internal_failure(self):
        """Even if _enrich_internal raises, enrich() must return an IncidentMetadata."""
        svc = make_service()
        with patch.object(svc, "_enrich_internal", side_effect=RuntimeError("forced")):
            meta = svc.enrich(category="VPN", assignment_group="IT Support")
        assert isinstance(meta, IncidentMetadata)
        assert meta.category == "VPN"
        assert meta.assignment_group == "IT Support"

    def test_safe_defaults_structure(self):
        meta = IncidentEnrichmentService._build_safe_defaults("VPN", "IT Support")
        assert meta.category == "VPN"
        assert meta.subcategory == "VPN-Global Protect"
        assert meta.assignment_group == "IT Support"
        assert meta.impact == 3
        assert meta.urgency == 3
        assert meta.priority == 4
        assert meta.priority_label == "4 - Low"
        assert meta.configuration_item == "VPN Gateway"


# ─────────────────────────────────────────────────────────────────────────────
# to_extra_fields() integration with IncidentCreateRequest mock
# ─────────────────────────────────────────────────────────────────────────────

class TestExtraFieldsPayloadIntegration:
    """Verify that to_extra_fields() produces a dict TicketService can merge."""

    def test_extra_fields_can_be_merged_into_dict(self):
        meta = IncidentEnrichmentService().enrich(category="SAP", assignment_group="SAP Support")
        base = {"contact_type": "chat", "u_type": "issue", "subcategory": ""}
        base.update(meta.to_extra_fields())
        # After merge, IES values should win
        assert base["subcategory"] == "Installation Request"
        assert base["contact_type"] == "Virtual Agent"

    def test_extra_fields_no_none_values(self):
        """None values must not appear in extra_fields (to avoid sending null to SN)."""
        meta = IncidentEnrichmentService().enrich(category="General")
        extra = meta.to_extra_fields()
        for key, val in extra.items():
            assert val is not None, f"Field '{key}' must not be None in extra_fields"


# ─────────────────────────────────────────────────────────────────────────────
# enrich_incident() module-level convenience function
# ─────────────────────────────────────────────────────────────────────────────

class TestEnrichIncidentConvenience:
    def test_returns_incident_metadata(self):
        meta = enrich_incident(category="VPN")
        assert isinstance(meta, IncidentMetadata)

    def test_passes_kwargs_through(self):
        meta = enrich_incident(
            category="SAP",
            assignment_group="SAP Team",
            location="Frankfurt",
        )
        assert meta.category == "SAP"
        assert meta.location == "Frankfurt"

    def test_accepts_field_mapping_service(self):
        mock_mapper = MagicMock()
        mock_mapper.build_servicenow_fields.return_value = {
            "assignment_group": "RESOLVED-SYS-ID",
            "category": "sap",
            "subcategory": "",
            "contact_type": "chat",
            "u_type": "issue",
        }
        mock_mapper.get_subcategories.return_value = []

        meta = enrich_incident(
            category="SAP",
            field_mapping_service=mock_mapper,
        )
        assert meta.assignment_group == "RESOLVED-SYS-ID"


# ─────────────────────────────────────────────────────────────────────────────
# Priority matrix completeness
# ─────────────────────────────────────────────────────────────────────────────

class TestPriorityMatrix:
    def test_all_nine_cells_present(self):
        for i in (1, 2, 3):
            for u in (1, 2, 3):
                assert (i, u) in _PRIORITY_MATRIX, f"Matrix missing ({i},{u})"

    def test_priority_decreases_with_increasing_impact_urgency(self):
        """Lower numbers = higher severity."""
        assert _PRIORITY_MATRIX[(1, 1)][0] < _PRIORITY_MATRIX[(2, 2)][0]
        assert _PRIORITY_MATRIX[(2, 2)][0] <= _PRIORITY_MATRIX[(3, 3)][0]

    def test_priority_label_format(self):
        for (i, u), (p_int, p_label) in _PRIORITY_MATRIX.items():
            assert str(p_int) in p_label, f"Priority label mismatch for ({i},{u})"
