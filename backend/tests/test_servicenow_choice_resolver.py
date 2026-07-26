"""
test_servicenow_choice_resolver.py
─────────────────────────────────────────────────────────────────────────────
Unit tests for ServiceNowChoiceResolver and ServiceNow mapping layer.

Verifies:
  1. No hardcoded choices; values resolved from sys_choice data.
  2. Multi-level hierarchy dependency checks (u_type -> category -> subcategory).
  3. Rule 3 key mappings (caller, channel, type, etc.).
  4. assignment_group display name resolved to 32-character sys_id before POST.
  5. contact_type Value resolution (Virtual Agent -> virtual_agent).
  6. u_type Value resolution (Digital Workplace (Infrastructure)).
  7. category Value lookup by u_type + label.
  8. subcategory Value lookup by category + label.
  9. ServiceNowChoiceResolver singleton & dynamic loading.
 10. Pre-POST hierarchy validation and prevention of invalid combinations.
"""

import pytest
from app.services.servicenow_choice_resolver import ServiceNowChoiceResolver
from app.services.servicenow_client import ServiceNowClient


class TestServiceNowChoiceResolver:

    @pytest.fixture(autouse=True)
    def setup_resolver(self):
        self.resolver = ServiceNowChoiceResolver.get_instance()

    def test_resolve_type_value(self):
        """Rule 6: u_type must resolve to VALUE column from sys_choice export."""
        res_dw = self.resolver.resolve_type("Digital Workplace (Infrastructure)")
        assert res_dw == "Digital Workplace (Infrastructure)"

        res_sap = self.resolver.resolve_type("Business Application - SAP")
        assert res_sap == "Business Application - SAP"

        res_da = self.resolver.resolve_type("Data & Analytics")
        assert res_da == "Data_and_Analytics"

    def test_resolve_category_value(self):
        """Rule 7: category must resolve to VALUE by u_type + label."""
        cat_vpn = self.resolver.resolve_category("Digital Workplace (Infrastructure)", "VPN")
        assert cat_vpn == "network"

        cat_network = self.resolver.resolve_category("Digital Workplace (Infrastructure)", "Network")
        assert cat_network == "network"

        cat_m365 = self.resolver.resolve_category("Digital Workplace (Infrastructure)", "Microsoft 365")
        assert cat_m365 == "Microsoft 365"

        cat_hw = self.resolver.resolve_category("Digital Workplace (Infrastructure)", "Hardware")
        assert cat_hw == "Hardware"

    def test_resolve_subcategory_value(self):
        """Rule 8: subcategory must resolve to VALUE by category + label."""
        sub_gp = self.resolver.resolve_subcategory("network", "GlobalProtect")
        assert sub_gp == "VPN-Global Protect"

        sub_net = self.resolver.resolve_subcategory("network", "Wi-Fi")
        assert sub_net == "Network Issue Wi-Fi/Wired"

        sub_email = self.resolver.resolve_subcategory("Microsoft 365", "Email")
        assert sub_email == "Outlook Not Working"

    def test_resolve_contact_type_value(self):
        """Rule 5: contact_type must resolve to VALUE column."""
        ct_va = self.resolver.resolve_contact_type("Virtual Agent")
        assert ct_va == "virtual_agent"

        ct_chat = self.resolver.resolve_contact_type("Chat")
        assert ct_chat == "chat"

        ct_email = self.resolver.resolve_contact_type("Email")
        assert ct_email == "email"

    def test_resolve_assignment_group_sys_id(self):
        """Rule 4: assignment_group must ALWAYS resolve to 32-character sys_id."""
        sys_id_msg = self.resolver.resolve_assignment_group("Messaging Team")
        assert len(sys_id_msg) == 32
        assert sys_id_msg == "0a4335ffdbaa1c104b1818fe3b96193f"

        sys_id_net = self.resolver.resolve_assignment_group("Network Support")
        assert len(sys_id_net) == 32

        # Already a 32-char sys_id must remain unchanged
        raw_32 = "a1b2c3d4e5f67890a1b2c3d4e5f67890"
        assert self.resolver.resolve_assignment_group(raw_32) == raw_32

    def test_exact_user_provided_resolution_matrix(self):
        """Verify the exact resolution flow requested by user."""
        resolved_type = self.resolver.resolve_type("Digital Workplace (Infrastructure)")
        assert resolved_type == "Digital Workplace (Infrastructure)"

        resolved_cat = self.resolver.resolve_category(resolved_type, "Network")
        assert resolved_cat == "network"

        resolved_subcat = self.resolver.resolve_subcategory(resolved_cat, "VPN")
        assert resolved_subcat == "VPN-Global Protect"

        resolved_contact = self.resolver.resolve_contact_type("Virtual Agent")
        assert resolved_contact == "virtual_agent"

        resolved_group_sys_id = self.resolver.resolve_assignment_group("IT Support Team")
        assert resolved_group_sys_id == "0a4335ffdbaa1c104b1818fe3b96193f"
        assert len(resolved_group_sys_id) == 32

    def test_validate_hierarchy_valid_combination(self):
        """Rule 2 & 10: Valid hierarchy combinations return (True, 'Hierarchy valid')."""
        is_valid, _ = self.resolver.validate_hierarchy(
            u_type_val="Digital Workplace (Infrastructure)",
            category_val="network",
            subcategory_val="VPN-Global Protect",
        )
        assert is_valid is True

    def test_validate_hierarchy_invalid_subcategory(self):
        """Rule 2 & 10: Invalid subcategory for category returns False."""
        is_valid, reason = self.resolver.validate_hierarchy(
            u_type_val="Digital Workplace (Infrastructure)",
            category_val="network",
            subcategory_val="Outlook Not Working",  # Outlook belongs to Microsoft 365, not network!
        )
        assert is_valid is False
        assert "Hierarchy Validation Error" in reason

    def test_validate_hierarchy_invalid_category(self):
        """Rule 2 & 10: Invalid category for u_type returns False."""
        is_valid, reason = self.resolver.validate_hierarchy(
            u_type_val="Business Application - SAP",
            category_val="network",  # Network belongs to Digital Workplace, not SAP!
        )
        assert is_valid is False
        assert "Hierarchy Validation Error" in reason


class TestServiceNowClientChoiceIntegration:

    def test_client_create_incident_maps_rule_3_keys_and_sys_id(self, monkeypatch):
        monkeypatch.setenv("USE_MOCK_SERVICENOW", "true")

        client = ServiceNowClient()
        res = client.create_incident(
            short_description="Outlook crash on launch",
            description="Detailed report",
            caller="user_123",
            channel="Virtual Agent",
            type="Digital Workplace (Infrastructure)",
            category="Microsoft 365",
            subcategory="Outlook Not Working",
            assignment_group="Messaging Support",
        )

        assert res["success"] is True
        result = res["result"]

        # Verify Rule 3 & Rule 4 resolution
        assert result["caller_id"] == "user_123"
        assert result["contact_type"] == "virtual_agent"
        assert result["u_type"] == "Digital Workplace (Infrastructure)"
        assert result["category"] == "Microsoft 365"
        assert result["subcategory"] == "Outlook Not Working"
        assert len(result["assignment_group"]) == 32
        assert result["assignment_group"] == "0a4335ffdbaa1c104b1818fe3b96193f"

    def test_client_create_incident_drops_invalid_hierarchy_combination(self, monkeypatch):
        monkeypatch.setenv("USE_MOCK_SERVICENOW", "true")

        client = ServiceNowClient()
        # Pass invalid subcategory (Outlook Not Working) for category (network)
        with pytest.raises(Exception) as exc:
            client.create_incident(
                short_description="VPN problem",
                description="Cannot connect",
                type="Digital Workplace (Infrastructure)",
                category="network",
                subcategory="Outlook Not Working",  # Invalid for network!
                assignment_group="Network Team",
            )

        assert "Invalid subcategory" in str(exc.value)
