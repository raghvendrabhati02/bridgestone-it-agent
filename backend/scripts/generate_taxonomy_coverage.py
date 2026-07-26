#!/usr/bin/env python3
"""
scripts/generate_taxonomy_coverage.py
────────────────────────────────────────────────────────────────────────────
Phase 6 — Enterprise Taxonomy Coverage Report.

Generates a human-readable coverage report from incident_config.json and
intent_category_map.json. No HTTP calls, no database, no live services.

Reports
-------
  • Supported categories (from valid_categories)
  • Supported subcategories (from subcategory_map)
  • Supported intents (from intent_category_map)
  • CI map entries (from ci_map)
  • Impact/Urgency keyword coverage (from category_impact / category_urgency)
  • Assignment group mappings (from assignment_group_map)
  • Category → assignment group table
  • Intent → category table
  • Fallback rules domain count (derived from classification_service.py rules)

Usage
-----
    python scripts/generate_taxonomy_coverage.py [--json]

Exit codes
----------
    0 — Report generated successfully
    1 — Configuration load failure
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

# ── Resolve backend directory ─────────────────────────────────────────────────
_SCRIPT_DIR  = Path(__file__).resolve().parent   # backend/scripts/
_BACKEND_DIR = _SCRIPT_DIR.parent                # backend/

if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

# ── Colour helpers ────────────────────────────────────────────────────────────
GREEN  = "\033[92m"
CYAN   = "\033[96m"
YELLOW = "\033[93m"
WHITE  = "\033[97m"
RESET  = "\033[0m"
BOLD   = "\033[1m"

_DATA_DIR = _BACKEND_DIR / "app" / "data"
_INCIDENT_CONFIG  = _DATA_DIR / "incident_config.json"
_INTENT_MAP       = _DATA_DIR / "intent_category_map.json"

# ── Deterministic fallback domains in classification_service.py (Phase 6) ────
FALLBACK_DOMAINS = [
    "Security",
    "CyberArk PAM",
    "Network / VPN",
    "Wi-Fi",
    "DNS / LAN / Proxy",
    "Microsoft 365 — Outlook",
    "Microsoft 365 — Teams / Zoom",
    "Microsoft 365 — SharePoint",
    "Microsoft 365 — OneDrive",
    "Microsoft 365 — Office Apps",
    "Mobile Devices",
    "Hardware — Laptop / Desktop",
    "Hardware — Monitor",
    "Hardware — Keyboard / Mouse",
    "Hardware — Peripherals",
    "Printer",
    "Scanner",
    "Password Reset",
    "MFA",
    "Account Unlock",
    "New Account / BSID Domain",
    "Email — Spam",
    "Email — Shared Mailbox",
    "Software — SAP / ERP",
    "Software — Crash / Freeze",
    "Software — Install / License / Update",
]


def _load_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Configuration file not found: {path}")
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def _sep(char: str = "=", width: int = 68) -> str:
    return char * width


def _header(title: str, width: int = 68) -> str:
    pad = width - len(title) - 4
    left  = pad // 2
    right = pad - left
    return f"+{'-' * left} {title} {'-' * right}+"


def _row(label: str, value: Any, width: int = 68) -> str:
    label_part = f"  {label:<38}"
    val_str = str(value)
    return f"|{label_part}: {CYAN}{val_str:<22}{RESET}|"


def _divider(width: int = 68) -> str:
    return f"+{'-' * (width - 2)}+"


def generate_report(incident_data: Dict[str, Any], intent_data: Dict[str, Any]) -> Dict[str, Any]:
    """Compute coverage metrics from loaded configuration data."""
    valid_categories: List[str] = incident_data.get("valid_categories", [])
    subcategory_map:  Dict[str, str] = incident_data.get("subcategory_map", {})
    ci_map:           Dict[str, str] = incident_data.get("ci_map", {})
    category_impact:  Dict[str, Any] = incident_data.get("category_impact", {})
    category_urgency: Dict[str, Any] = incident_data.get("category_urgency", {})
    assignment_map:   Dict[str, str] = incident_data.get("assignment_group_map", {})
    category_map:     Dict[str, str] = incident_data.get("category_map", {})
    clarification_threshold: float   = float(incident_data.get("clarification_threshold", 0.70))

    # Intent map — skip comment keys
    raw_intents: Dict[str, str] = intent_data.get("intent_category_map", {})
    intents = {k: v for k, v in raw_intents.items() if not k.startswith("_") and isinstance(v, str)}

    # Unique assignment groups configured
    unique_groups: Set[str] = set(assignment_map.values())

    # Categories covered by intent map (normalised)
    intent_categories: Set[str] = set(v.lower() for v in intents.values())

    # Impact/urgency keyword overlap
    impact_keys:  Set[str] = set(k for k in category_impact.keys() if not k.startswith("_"))
    urgency_keys: Set[str] = set(k for k in category_urgency.keys() if not k.startswith("_"))

    return {
        "valid_categories": valid_categories,
        "subcategory_count": len(subcategory_map),
        "intent_count": len(intents),
        "ci_map_count": len(ci_map),
        "impact_keyword_count": len(impact_keys),
        "urgency_keyword_count": len(urgency_keys),
        "assignment_group_count": len(assignment_map),
        "unique_assignment_groups": sorted(unique_groups),
        "category_alias_count": len(category_map),
        "intent_categories": sorted(intent_categories),
        "intents": intents,
        "clarification_threshold": clarification_threshold,
        "fallback_domain_count": len(FALLBACK_DOMAINS),
        "fallback_domains": FALLBACK_DOMAINS,
        "assignment_map": assignment_map,
    }


def print_report(report: Dict[str, Any]) -> None:
    """Print a formatted console coverage report."""
    import sys
    # Ensure UTF-8 output on Windows if possible, otherwise fall back to ASCII
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    W = 68

    print(f"\n{BOLD}+{_sep('=', W - 2)}+{RESET}")
    print(f"{BOLD}|{'Bridgestone IT Agent -- Enterprise Taxonomy Coverage':^{W-2}}|{RESET}")
    print(f"{BOLD}+{_sep('=', W - 2)}+{RESET}")

    # -- Summary Metrics --
    cats = report["valid_categories"]
    print(_row("Supported Categories (valid_categories)", len(cats)))
    print(_row("Supported Subcategory Aliases", report["subcategory_count"]))
    print(_row("Supported Intent Keywords", report["intent_count"]))
    print(_row("CI Map Entries (cmdb_ci)", report["ci_map_count"]))
    print(_row("Impact Map Keywords", report["impact_keyword_count"]))
    print(_row("Urgency Map Keywords", report["urgency_keyword_count"]))
    print(_row("Assignment Group Mappings", report["assignment_group_count"]))
    print(_row("Unique Assignment Groups", len(report["unique_assignment_groups"])))
    print(_row("Category Alias Mappings", report["category_alias_count"]))
    print(_row("Fallback Rules Domains (classif. engine)", report["fallback_domain_count"]))
    print(_row("Clarification Threshold", f"{report['clarification_threshold']:.2f}"))

    # -- Valid Categories --
    print(f"+{'-' * (W - 2)}+")
    print(f"|  {YELLOW}Valid ServiceNow Categories{RESET}{' ' * (W - 30)}|")
    for i, cat in enumerate(sorted(cats), 1):
        line = f"    {i:2d}. {cat}"
        print(f"|{line:<{W-2}}|")

    # -- Assignment Group Map --
    print(f"+{'-' * (W - 2)}+")
    print(f"|  {YELLOW}Category -> Assignment Group{RESET}{' ' * (W - 31)}|")
    for cat_key, group in sorted(report["assignment_map"].items()):
        line = f"    {cat_key:<28} ->  {group}"
        print(f"|{line:<{W-2}}|")

    # -- Unique Assignment Groups --
    print(f"+{'-' * (W - 2)}+")
    print(f"|  {YELLOW}Unique Assignment Groups{RESET}{' ' * (W - 28)}|")
    for grp in report["unique_assignment_groups"]:
    print(f"║  {YELLOW}Intent Map → Category Coverage{RESET}{' ' * (W - 34)}║")
    for cat in report["intent_categories"]:
        intent_list = [k for k, v in report["intents"].items() if v.lower() == cat]
        line = f"    {cat:<20} ({len(intent_list)} intents)"
        print(f"║{line:<{W-2}}║")

    # ── Fallback Rules Domains ────────────────────────────────────────────────
    print(f"╠{'─' * (W - 2)}╣")
    print(f"║  {YELLOW}Fallback Rules Engine Domains{RESET}{' ' * (W - 33)}║")
    for i, domain in enumerate(report["fallback_domains"], 1):
        line = f"    {i:2d}. {domain}"
        print(f"║{line:<{W-2}}║")

    print(f"╚{_sep('═', W - 2)}╝\n")


def print_json_report(report: Dict[str, Any]) -> None:
    """Print machine-readable JSON report."""
    output = {
        "phase": "Phase 6 — Enterprise Incident Taxonomy",
        "summary": {
            "valid_categories": len(report["valid_categories"]),
            "subcategory_aliases": report["subcategory_count"],
            "intent_keywords": report["intent_count"],
            "ci_map_entries": report["ci_map_count"],
            "impact_keywords": report["impact_keyword_count"],
            "urgency_keywords": report["urgency_keyword_count"],
            "assignment_group_mappings": report["assignment_group_count"],
            "unique_assignment_groups": len(report["unique_assignment_groups"]),
            "category_aliases": report["category_alias_count"],
            "fallback_domains": report["fallback_domain_count"],
            "clarification_threshold": report["clarification_threshold"],
        },
        "valid_categories": sorted(report["valid_categories"]),
        "assignment_groups": report["unique_assignment_groups"],
        "fallback_domains": report["fallback_domains"],
    }
    print(json.dumps(output, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate Enterprise Taxonomy Coverage Report")
    parser.add_argument("--json", action="store_true", help="Output machine-readable JSON instead of console table")
    args = parser.parse_args()

    try:
        incident_data = _load_json(_INCIDENT_CONFIG)
        intent_data   = _load_json(_INTENT_MAP)
    except FileNotFoundError as exc:
        print(f"\n  ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError as exc:
        print(f"\n  ERROR: JSON parse failure — {exc}", file=sys.stderr)
        sys.exit(1)

    report = generate_report(incident_data, intent_data)

    if args.json:
        print_json_report(report)
    else:
        print_report(report)

    sys.exit(0)


if __name__ == "__main__":
    main()
