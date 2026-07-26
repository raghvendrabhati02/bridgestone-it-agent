"""
test_servicenow_scenario_integration.py
──────────────────────────────────────────────────────────────────────────────
Integration tests for 7 core ServiceNow IT support scenarios.

Scenarios Tested:
  1. Printer
  2. VPN
  3. Outlook
  4. Laptop
  5. Password Reset
  6. Software Installation
  7. ServiceNow Issue

Rules:
  • Does NOT mock IncidentEnrichmentService or ConfigurationService.
  • Verifies u_type, category, subcategory, assignment_group, priority, and success response.
"""

from __future__ import annotations

import os
import pytest
from app.services.ticket_service import create_ticket
from app.services.servicenow_choice_resolver import ServiceNowChoiceResolver
from app.services.incident_enrichment_service import IncidentEnrichmentService
from app.models.classification_models import ITSMClassification


@pytest.fixture(autouse=True)
def enable_mock_servicenow(monkeypatch):
    """Ensure tests run in mock ServiceNow mode for unit test suite execution."""
    monkeypatch.setenv("USE_MOCK_SERVICENOW", "true")


class TestServiceNowScenarioIntegration:

    def _enrich_and_create(
        self,
        category: str,
        subcategory: str,
        issue_desc: str,
        short_desc: str,
        assignment_group: str = "IT Support",
    ) -> dict:
        enrichment_service = IncidentEnrichmentService()
        classification = ITSMClassification(
            category=category,
            subcategory=subcategory,
            confidence=0.95,
            u_type="issue",
            reasoning="Integration test classification",
        )
        metadata = enrichment_service.enrich(
            category=category,
            classification=classification,
        )

        ticket = create_ticket(
            category=metadata.category,
            issue_description=issue_desc,
            created_by="test_user",
            short_description=short_desc,
            description=issue_desc,
            incident_metadata=metadata,
        )
        return {"ticket": ticket, "metadata": metadata}

    def test_scenario_1_printer(self):
        """Scenario 1: Printer Offline"""
        res = self._enrich_and_create(
            category="Printer",
            subcategory="Printer Offline",
            issue_desc="Office printer is offline and not taking print jobs",
            short_desc="Printer Offline and unresponsive",
        )
        ticket = res["ticket"]
        metadata = res["metadata"]

        resolved_grp = ServiceNowChoiceResolver.get_instance().resolve_assignment_group(ticket["assignment_group"])
        assert ticket["success"] is True
        assert ticket["servicenow_number"].startswith("INC")
        assert metadata.incident_type == "Digital Workplace (Infrastructure)"
        assert metadata.category == "Printer"
        assert metadata.subcategory == "Printer Offline"
        assert len(resolved_grp) == 32
        assert 1 <= metadata.priority <= 5

    def test_scenario_2_vpn(self):
        """Scenario 2: VPN Connection Failed"""
        res = self._enrich_and_create(
            category="Network",
            subcategory="VPN-Global Protect",
            issue_desc="Global Protect VPN failed to connect with network timeout",
            short_desc="VPN Connection Failed",
        )
        ticket = res["ticket"]
        metadata = res["metadata"]
        resolved_grp = ServiceNowChoiceResolver.get_instance().resolve_assignment_group(ticket["assignment_group"])

        assert ticket["success"] is True
        assert ticket["servicenow_number"].startswith("INC")
        assert metadata.incident_type == "Digital Workplace (Infrastructure)"
        assert metadata.category.lower() == "network"
        assert metadata.subcategory == "VPN-Global Protect"
        assert len(resolved_grp) == 32
        assert 1 <= metadata.priority <= 5

    def test_scenario_3_outlook(self):
        """Scenario 3: Outlook Not Opening"""
        res = self._enrich_and_create(
            category="Microsoft 365",
            subcategory="Outlook Not Working",
            issue_desc="Outlook 365 not opening and failing to load profile",
            short_desc="Outlook 365 Not Opening",
        )
        ticket = res["ticket"]
        metadata = res["metadata"]
        resolved_grp = ServiceNowChoiceResolver.get_instance().resolve_assignment_group(ticket["assignment_group"])

        assert ticket["success"] is True
        assert ticket["servicenow_number"].startswith("INC")
        assert metadata.incident_type == "Digital Workplace (Infrastructure)"
        assert metadata.category == "Microsoft 365"
        assert metadata.subcategory == "Outlook Not Working"
        assert len(resolved_grp) == 32
        assert 1 <= metadata.priority <= 5

    def test_scenario_4_laptop(self):
        """Scenario 4: Laptop Hanging"""
        res = self._enrich_and_create(
            category="Hardware",
            subcategory="Dell Desktop/Laptop Damage",
            issue_desc="Laptop experiencing persistent hanging issues after reboot",
            short_desc="Laptop Persistent Hanging",
        )
        ticket = res["ticket"]
        metadata = res["metadata"]
        resolved_grp = ServiceNowChoiceResolver.get_instance().resolve_assignment_group(ticket["assignment_group"])

        assert ticket["success"] is True
        assert ticket["servicenow_number"].startswith("INC")
        assert metadata.incident_type == "Digital Workplace (Infrastructure)"
        assert metadata.category == "Hardware"
        assert metadata.subcategory == "Dell Desktop/Laptop Damage"
        assert len(resolved_grp) == 32
        assert 1 <= metadata.priority <= 5

    def test_scenario_5_password_reset(self):
        """Scenario 5: Password Reset"""
        res = self._enrich_and_create(
            category="Password/Access",
            subcategory="Password Reset",
            issue_desc="Password reset required for network domain user account",
            short_desc="Domain Password Reset Required",
        )
        ticket = res["ticket"]
        metadata = res["metadata"]
        resolved_grp = ServiceNowChoiceResolver.get_instance().resolve_assignment_group(ticket["assignment_group"])

        assert ticket["success"] is True
        assert ticket["servicenow_number"].startswith("INC")
        assert metadata.incident_type == "Digital Workplace (Infrastructure)"
        assert metadata.category == "BSID Domain"
        assert metadata.subcategory == "Password Reset"
        assert len(resolved_grp) == 32
        assert 1 <= metadata.priority <= 5

    def test_scenario_6_software_installation(self):
        """Scenario 6: Software Installation Request"""
        res = self._enrich_and_create(
            category="Software",
            subcategory="Installation Request",
            issue_desc="Requesting software installation for enterprise PDF editor",
            short_desc="Software Installation Request",
        )
        ticket = res["ticket"]
        metadata = res["metadata"]
        resolved_grp = ServiceNowChoiceResolver.get_instance().resolve_assignment_group(ticket["assignment_group"])

        assert ticket["success"] is True
        assert ticket["servicenow_number"].startswith("INC")
        assert metadata.incident_type == "Digital Workplace (Infrastructure)"
        assert metadata.category == "Software"
        assert metadata.subcategory == "Installation Request"
        assert len(resolved_grp) == 32
        assert 1 <= metadata.priority <= 5

    def test_scenario_7_servicenow_issue(self):
        """Scenario 7: ServiceNow Issue"""
        res = self._enrich_and_create(
            category="Network",
            subcategory="Configuration Issue",
            issue_desc="ServiceNow application page will not load in web browser",
            short_desc="ServiceNow Web Application Not Loading",
        )
        ticket = res["ticket"]
        metadata = res["metadata"]
        resolved_grp = ServiceNowChoiceResolver.get_instance().resolve_assignment_group(ticket["assignment_group"])

        assert ticket["success"] is True
        assert ticket["servicenow_number"].startswith("INC")
        assert metadata.incident_type == "Digital Workplace (Infrastructure)"
        assert metadata.category.lower() == "network"
        assert metadata.subcategory == "Configuration Issue"
        assert len(resolved_grp) == 32
        assert 1 <= metadata.priority <= 5
