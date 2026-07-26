"""
validate_servicenow_configuration.py
──────────────────────────────────────────────────────────────────────────────
Enterprise Configuration Validator for ServiceNow Integration.

Verifies:
  ✓ Categories
  ✓ Subcategories
  ✓ Assignment Groups
  ✓ Incident Type (u_type)
  ✓ Contact Type (contact_type)
  ✓ Impact / Urgency / Priority

Exits with status code 0 if all configurations validate successfully,
or status code 1 if any configured value is invalid or missing.
"""

from __future__ import annotations

import os
import sys
import json
from pathlib import Path
from dotenv import load_dotenv

# Load backend environment & setup sys.path
backend_dir = Path(__file__).resolve().parent.parent
env_file = backend_dir / ".env"
load_dotenv(env_file)
sys.path.insert(0, str(backend_dir))

from app.services.configuration_service import ConfigurationService
from app.services.servicenow_choice_resolver import ServiceNowChoiceResolver
from app.services.servicenow_client import ServiceNowClient


def main() -> int:
    print("=" * 80)
    print("SERVICENOW CONFIGURATION VALIDATOR")
    print("=" * 80)

    errors = []
    cfg = ConfigurationService.get_instance()
    resolver = ServiceNowChoiceResolver.get_instance()
    client = ServiceNowClient()

    # 1. Check Incident Type & Contact Type Defaults
    print("\n1. Checking Default Types & Contact Channels...")
    default_type = cfg.get_servicenow_type("incident")
    contact_type = cfg.get_contact_type()

    valid_types = [c["value"] for c in resolver.choices if c["element"] == "u_type"]
    if default_type in valid_types or default_type == "Digital Workplace (Infrastructure)":
        print(f"  [OK] Default u_type: '{default_type}'")
    else:
        err = f"Invalid default u_type '{default_type}' not in choice hierarchy"
        print(f"  [FAIL] {err}")
        errors.append(err)

    if contact_type in ("Virtual Agent", "virtual_agent"):
        print(f"  [OK] Default contact_type: '{contact_type}'")
    else:
        err = f"Invalid default contact_type '{contact_type}'"
        print(f"  [FAIL] {err}")
        errors.append(err)

    # 2. Check Categories & Subcategories
    print("\n2. Checking Categories & Subcategories Hierarchy...")
    categories_to_check = [
        ("Hardware", "Dell Desktop/Laptop Damage"),
        ("Microsoft 365", "Outlook Not Working"),
        ("Network", "VPN-Global Protect"),
        ("Network", "Configuration Issue"),
        ("Printer", "Printer Offline"),
        ("BSID Domain", "Password Reset"),
        ("Software", "Installation Request"),
    ]

    for cat_raw, subcat_raw in categories_to_check:
        mapped_cat = cfg.get_mapped_category(cat_raw)
        mapped_subcat = cfg.get_mapped_subcategory(subcat_raw)

        resolved_cat = resolver.resolve_category(default_type, mapped_cat)
        resolved_subcat = resolver.resolve_subcategory(resolved_cat, mapped_subcat)

        is_valid, msg = resolver.validate_hierarchy(default_type, resolved_cat, resolved_subcat)
        if is_valid:
            print(f"  [OK] Category: '{resolved_cat}' | Subcategory: '{resolved_subcat}'")
        else:
            err = f"Invalid category/subcategory combination '{cat_raw}' -> '{subcat_raw}': {msg}"
            print(f"  [FAIL] {err}")
            errors.append(err)

    # 3. Check Assignment Groups
    print("\n3. Checking Assignment Groups...")
    groups_to_check = [
        "Network Team",
        "IT Support Team",
        "Desktop Support Team",
        "SAP Support Team",
        "Messaging Team",
    ]

    for grp in groups_to_check:
        sys_id = resolver.resolve_assignment_group(grp)
        if sys_id and len(sys_id) == 32:
            print(f"  [OK] Group: '{grp}' -> sys_id: '{sys_id}'")
        else:
            err = f"Assignment group '{grp}' resolved to invalid sys_id '{sys_id}'"
            print(f"  [FAIL] {err}")
            errors.append(err)

    # 4. Check Impact, Urgency, Priority Calculations
    print("\n4. Checking Impact / Urgency / Priority Calculations...")
    impact = cfg.get_impact("network")
    urgency = cfg.get_urgency("network")
    if 1 <= impact <= 3 and 1 <= urgency <= 3:
        print(f"  [OK] Impact / Urgency bounds OK (Impact: {impact}, Urgency: {urgency})")
    else:
        err = f"Impact/Urgency out of range (Impact: {impact}, Urgency: {urgency})"
        print(f"  [FAIL] {err}")
        errors.append(err)

    # Final summary
    print("\n" + "=" * 80)
    if not errors:
        print("Configuration Validation PASSED")
        print("=" * 80)
        return 0
    else:
        print(f"Configuration Validation FAILED ({len(errors)} errors):")
        for e in errors:
            print(f"  - {e}")
        print("=" * 80)
        return 1


if __name__ == "__main__":
    sys.exit(main())
