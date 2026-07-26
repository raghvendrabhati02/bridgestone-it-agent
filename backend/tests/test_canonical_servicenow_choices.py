"""
test_canonical_servicenow_choices.py
─────────────────────────────────────────────────────────────────────────────
Unit tests for Canonical ServiceNow Category & Subcategory Resolution & Validation.

Verifies:
  1. VPN issue → category="network", subcategory="VPN-Global Protect"
  2. Outlook issue → category="Microsoft 365", subcategory="Outlook Not Working"
  3. Keyboard issue → category="Hardware", subcategory="Keyboard/Mouse Not Working"
  4. Printer offline → category="Printer", subcategory="Printer Offline"
  5. Website blocked → category="network", subcategory="Website Blocked"
  6. Enforces validation error when invalid subcategory is sent for category.
"""

import pytest
from app.services.servicenow_choice_resolver import ServiceNowChoiceResolver
from app.services.servicenow_exceptions import ServiceNowAPIError


@pytest.fixture
def resolver():
    return ServiceNowChoiceResolver.get_instance()


def test_vpn_issue_resolution(resolver):
    cat = resolver.resolve_category("Digital Workplace (Infrastructure)", "VPN")
    subcat = resolver.resolve_subcategory(cat, "My GlobalProtect VPN is not working")
    assert cat == "network"
    assert subcat == "VPN-Global Protect"


def test_outlook_issue_resolution(resolver):
    cat = resolver.resolve_category("Digital Workplace (Infrastructure)", "Outlook")
    subcat = resolver.resolve_subcategory(cat, "Outlook Not Working")
    assert cat == "Microsoft 365"
    assert subcat == "Outlook Not Working"


def test_keyboard_issue_resolution(resolver):
    cat = resolver.resolve_category("Digital Workplace (Infrastructure)", "Hardware")
    subcat = resolver.resolve_subcategory(cat, "Keyboard issue")
    assert cat == "Hardware"
    assert subcat == "Keyboard/Mouse Not Working"


def test_printer_offline_resolution(resolver):
    cat = resolver.resolve_category("Digital Workplace (Infrastructure)", "Printer")
    subcat = resolver.resolve_subcategory(cat, "Printer offline")
    assert cat == "Printer"
    assert subcat == "Printer Offline"


def test_website_blocked_resolution(resolver):
    cat = resolver.resolve_category("Digital Workplace (Infrastructure)", "network")
    subcat = resolver.resolve_subcategory(cat, "website blocked")
    assert cat == "network"
    assert subcat == "Website Blocked"


def test_hierarchy_validation_valid(resolver):
    is_valid, reason = resolver.validate_hierarchy(
        u_type_val="Digital Workplace (Infrastructure)",
        category_val="network",
        subcategory_val="VPN-Global Protect",
    )
    assert is_valid is True
    assert "valid" in reason.lower()


def test_hierarchy_validation_invalid_subcategory(resolver):
    is_valid, reason = resolver.validate_hierarchy(
        u_type_val="Digital Workplace (Infrastructure)",
        category_val="network",
        subcategory_val="Outlook Not Working",
    )
    assert is_valid is False
    assert "Hierarchy Validation Error" in reason
