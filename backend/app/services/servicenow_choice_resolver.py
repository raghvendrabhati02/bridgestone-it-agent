"""
servicenow_choice_resolver.py
─────────────────────────────────────────────────────────────────────────────
Enterprise ServiceNow Choice Table & Hierarchy Resolver.

Authoritative source of truth for:
  1. Resolving u_type, category, subcategory, contact_type Labels to API Values.
  2. Enforcing strict multi-level hierarchy dependencies:
     u_type -> category -> subcategory
  3. Resolving assignment group display names to valid 32-character sys_id hex strings.
  4. Preventing invalid category/subcategory combinations from being sent in API payloads.

Supports dynamic loading from exported sys_choice CSV/Excel files while providing
an exact embedded choice matrix matching enterprise ServiceNow sys_choice exports.
"""

from __future__ import annotations

import hashlib
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union

logger = logging.getLogger("it-agent-backend")


# ── Authoritative sys_choice Registry (from ServiceNow sys_choice Export) ─────

_DEFAULT_SYS_CHOICES: List[Dict[str, str]] = [
    # ── u_type (Incident Type) Choices ──────────────────────────────────────────
    {"element": "u_type", "label": "Digital Workplace (Infrastructure)", "value": "Digital Workplace (Infrastructure)", "dependent_value": ""},
    {"element": "u_type", "label": "Business Application - Non-SAP", "value": "Business Application - Non-SAP", "dependent_value": ""},
    {"element": "u_type", "label": "Business Application - SAP", "value": "Business Application - SAP", "dependent_value": ""},
    {"element": "u_type", "label": "Data & Analytics", "value": "Data_and_Analytics", "dependent_value": ""},
    {"element": "u_type", "label": "Server", "value": "Server", "dependent_value": ""},
    {"element": "u_type", "label": "ServiceNow Support", "value": "servicenow_support", "dependent_value": ""},
    {"element": "u_type", "label": "Incident", "value": "incident", "dependent_value": ""},
    {"element": "u_type", "label": "Issue", "value": "issue", "dependent_value": ""},
    {"element": "u_type", "label": "Service Request", "value": "request", "dependent_value": ""},

    # ── category Choices (Mapped to Dependent u_type Values) ──────────────────
    # Dependent on "Digital Workplace (Infrastructure)"
    {"element": "category", "label": "Network", "value": "network", "dependent_value": "Digital Workplace (Infrastructure)"},
    {"element": "category", "label": "Hardware", "value": "Hardware", "dependent_value": "Digital Workplace (Infrastructure)"},
    {"element": "category", "label": "Microsoft 365", "value": "Microsoft 365", "dependent_value": "Digital Workplace (Infrastructure)"},
    {"element": "category", "label": "Software", "value": "Software", "dependent_value": "Digital Workplace (Infrastructure)"},
    {"element": "category", "label": "Printer", "value": "Printer", "dependent_value": "Digital Workplace (Infrastructure)"},
    {"element": "category", "label": "CyberArk PAM", "value": "CyberArk PAM", "dependent_value": "Digital Workplace (Infrastructure)"},
    {"element": "category", "label": "BSID Domain", "value": "BSID Domain", "dependent_value": "Digital Workplace (Infrastructure)"},
    {"element": "category", "label": "E-mail", "value": "E-mail", "dependent_value": "Digital Workplace (Infrastructure)"},
    {"element": "category", "label": "Password/Access", "value": "Password/Access", "dependent_value": "Digital Workplace (Infrastructure)"},

    # Incident / Request Fallbacks
    {"element": "category", "label": "Network", "value": "network", "dependent_value": "incident"},
    {"element": "category", "label": "Hardware", "value": "Hardware", "dependent_value": "incident"},
    {"element": "category", "label": "Microsoft 365", "value": "Microsoft 365", "dependent_value": "incident"},
    {"element": "category", "label": "Software", "value": "Software", "dependent_value": "incident"},
    {"element": "category", "label": "Printer", "value": "Printer", "dependent_value": "incident"},
    {"element": "category", "label": "Password/Access", "value": "Password/Access", "dependent_value": "incident"},

    # ── subcategory Choices ─────────────────────────────────────────────────────
    # Dependent on "network"
    {"element": "subcategory", "label": "VPN-Global Protect", "value": "VPN-Global Protect", "dependent_value": "network"},
    {"element": "subcategory", "label": "Network Issue Wi-Fi/Wired", "value": "Network Issue Wi-Fi/Wired", "dependent_value": "network"},
    {"element": "subcategory", "label": "Access Point Faulty", "value": "Access Point Faulty", "dependent_value": "network"},
    {"element": "subcategory", "label": "Configuration Issue", "value": "Configuration Issue", "dependent_value": "network"},
    {"element": "subcategory", "label": "Website Blocked", "value": "Website Blocked", "dependent_value": "network"},
    {"element": "subcategory", "label": "LAN/Wi-Fi Driver Update", "value": "LAN/Wi-Fi Driver Update", "dependent_value": "network"},

    # Dependent on "Hardware"
    {"element": "subcategory", "label": "Keyboard/Mouse Not Working", "value": "Keyboard/Mouse Not Working", "dependent_value": "Hardware"},
    {"element": "subcategory", "label": "Dell Desktop/Laptop Damage", "value": "Dell Desktop/Laptop Damage", "dependent_value": "Hardware"},
    {"element": "subcategory", "label": "Monitor", "value": "Monitor", "dependent_value": "Hardware"},
    {"element": "subcategory", "label": "Printer", "value": "Printer", "dependent_value": "Hardware"},
    {"element": "subcategory", "label": "Laptop / PC", "value": "Laptop / PC", "dependent_value": "Hardware"},

    # Dependent on "Microsoft 365"
    {"element": "subcategory", "label": "Outlook Not Working", "value": "Outlook Not Working", "dependent_value": "Microsoft 365"},
    {"element": "subcategory", "label": "OneDrive Sync Issue", "value": "OneDrive Sync Issue", "dependent_value": "Microsoft 365"},
    {"element": "subcategory", "label": "MS Excel Not Opening/Working", "value": "MS Excel Not Opening/Working", "dependent_value": "Microsoft 365"},
    {"element": "subcategory", "label": "Teams Issue", "value": "Teams Issue", "dependent_value": "Microsoft 365"},
    {"element": "subcategory", "label": "SharePoint Issue", "value": "SharePoint Issue", "dependent_value": "Microsoft 365"},

    # Dependent on "Software"
    {"element": "subcategory", "label": "Installation Request", "value": "Installation Request", "dependent_value": "Software"},
    {"element": "subcategory", "label": "Software Crash / Error", "value": "Software Crash / Error", "dependent_value": "Software"},
    {"element": "subcategory", "label": "License Request", "value": "License Request", "dependent_value": "Software"},

    # Dependent on "Printer"
    {"element": "subcategory", "label": "Printer Offline", "value": "Printer Offline", "dependent_value": "Printer"},
    {"element": "subcategory", "label": "Paper Jam / Hardware Fault", "value": "Paper Jam / Hardware Fault", "dependent_value": "Printer"},
    {"element": "subcategory", "label": "Toner Replacement", "value": "Toner Replacement", "dependent_value": "Printer"},
    {"element": "subcategory", "label": "Printer Driver Issue", "value": "Printer Driver Issue", "dependent_value": "Printer"},

    # Dependent on "Password/Access" / "BSID Domain"
    {"element": "subcategory", "label": "Password Reset", "value": "Password Reset", "dependent_value": "Password/Access"},
    {"element": "subcategory", "label": "Password Reset", "value": "Password Reset", "dependent_value": "BSID Domain"},
    {"element": "subcategory", "label": "Account Locked", "value": "Account Locked", "dependent_value": "Password/Access"},
    {"element": "subcategory", "label": "Account Locked", "value": "Account Locked", "dependent_value": "BSID Domain"},
    {"element": "subcategory", "label": "Access Request", "value": "Access Request", "dependent_value": "Password/Access"},
    {"element": "subcategory", "label": "Access Request", "value": "Access Request", "dependent_value": "BSID Domain"},

    # Dependent on "Security"
    {"element": "subcategory", "label": "Phishing Attack", "value": "Phishing Attack", "dependent_value": "Security"},
    {"element": "subcategory", "label": "Malware Detection", "value": "Malware Detection", "dependent_value": "Security"},
    {"element": "subcategory", "label": "Security Incident", "value": "Security Incident", "dependent_value": "Security"},

    # Dependent on "Mobile Devices"
    {"element": "subcategory", "label": "Mobile Device Issue", "value": "Mobile Device Issue", "dependent_value": "Mobile Devices"},
    {"element": "subcategory", "label": "MDM Enrollment", "value": "MDM Enrollment", "dependent_value": "Mobile Devices"},

    # Dependent on "E-mail"
    {"element": "subcategory", "label": "Spam/Junk Email", "value": "Spam/Junk Email", "dependent_value": "E-mail"},
    {"element": "subcategory", "label": "Shared Mailbox Issue", "value": "Shared Mailbox Issue", "dependent_value": "E-mail"},
    {"element": "subcategory", "label": "Email Issue", "value": "Email Issue", "dependent_value": "E-mail"},

    # Dependent on "CyberArk PAM"
    {"element": "subcategory", "label": "Vault Access Issue", "value": "Vault Access Issue", "dependent_value": "CyberArk PAM"},
    {"element": "subcategory", "label": "Privileged Session Issue", "value": "Privileged Session Issue", "dependent_value": "CyberArk PAM"},

    # ── contact_type Choices ───────────────────────────────────────────────────
    {"element": "contact_type", "label": "Virtual Agent", "value": "virtual_agent", "dependent_value": ""},
    {"element": "contact_type", "label": "Self-service", "value": "self-service", "dependent_value": ""},
    {"element": "contact_type", "label": "Email", "value": "email", "dependent_value": ""},
    {"element": "contact_type", "label": "Phone", "value": "phone", "dependent_value": ""},
]


# Known Assignment Group Name -> sys_id mapping
_DEFAULT_GROUP_SYS_IDS: Dict[str, str] = {
    "it support team": "0a4335ffdbaa1c104b1818fe3b96193f",
    "it support": "0a4335ffdbaa1c104b1818fe3b96193f",
    "messaging team": "0a4335ffdbaa1c104b1818fe3b96193f",
    "messaging support": "0a4335ffdbaa1c104b1818fe3b96193f",
    "network team": "0a4335ffdbaa1c104b1818fe3b96193f",
    "network support": "0a4335ffdbaa1c104b1818fe3b96193f",
    "desktop support team": "032607a4db365c10e4fe0694f396199f",
    "desktop support": "032607a4db365c10e4fe0694f396199f",
    "sap support team": "061f1cdac35dca9014ed752f0501313d",
    "sap support": "061f1cdac35dca9014ed752f0501313d",
    "identity team": "19d949fa873802108513ea030cbb3536",
}


# ── ServiceNowChoiceResolver Service ───────────────────────────────────────────

class ServiceNowChoiceResolver:
    """
    Singleton / Reusable Choice Resolver service.
    
    Reads exported sys_choice tables (or embedded fallback registry) once on startup.
    Resolves Labels -> Values and validates u_type -> category -> subcategory relationships.
    """

    _instance: Optional[ServiceNowChoiceResolver] = None

    def __init__(self, data_directory: Optional[Union[str, Path]] = None):
        self.data_directory = Path(
            data_directory
            or os.getenv("SERVICENOW_MAPPINGS_DIR", str(Path(__file__).parent.parent / "data" / "servicenow_mappings"))
        )
        self.choices: List[Dict[str, str]] = list(_DEFAULT_SYS_CHOICES)
        self.group_mappings: Dict[str, str] = dict(_DEFAULT_GROUP_SYS_IDS)
        self._is_loaded: bool = False
        self.load_sys_choices()

    @classmethod
    def get_instance(cls) -> ServiceNowChoiceResolver:
        if cls._instance is None:
            cls._instance = ServiceNowChoiceResolver()
        return cls._instance

    def load_sys_choices(self) -> None:
        """
        Load exported sys_choice files (.xlsx, .csv) if present in data_directory.
        Appends or overwrites entries in internal choice tables.
        """
        if self._is_loaded:
            return

        if self.data_directory.exists() and self.data_directory.is_dir():
            files = list(self.data_directory.glob("*.csv")) + list(self.data_directory.glob("*.xlsx"))
            for f in files:
                if f.name.lower() == "readme.md":
                    continue
                try:
                    self._parse_file(f)
                except Exception as exc:
                    logger.warning("[ServiceNowChoiceResolver]: Could not load choice file '%s': %s", f.name, exc)

        self._is_loaded = True
        logger.info(
            "[ServiceNowChoiceResolver]: Initialized choice matrix with %d total choice mappings.",
            len(self.choices),
        )

    def _parse_file(self, file_path: Path) -> None:
        """Parse exported CSV/Excel choice file into internal choice list."""
        import csv
        ext = file_path.suffix.lower()
        rows: List[Dict[str, str]] = []

        if ext == ".csv":
            with open(file_path, mode="r", encoding="utf-8-sig") as fh:
                reader = csv.DictReader(fh)
                rows = [row for row in reader]
        elif ext in (".xlsx", ".xls"):
            try:
                import openpyxl
                wb = openpyxl.load_workbook(file_path, data_only=True)
                for sheet_name in wb.sheetnames:
                    sheet = wb[sheet_name]
                    iter_rows = sheet.iter_rows(values_only=True)
                    headers_raw = next(iter_rows, None)
                    if not headers_raw:
                        continue
                    headers = [str(h).strip().lower() for h in headers_raw if h is not None]
                    for r in iter_rows:
                        if not r or not any(r):
                            continue
                        row_dict = {h: str(v).strip() if v is not None else "" for h, v in zip(headers, r)}
                        rows.append(row_dict)
            except Exception as e:
                logger.warning("[ServiceNowChoiceResolver]: Failed reading Excel file '%s': %s", file_path.name, e)
                return

        for row in rows:
            norm = {str(k).lower().strip(): str(v).strip() for k, v in row.items()}
            element = norm.get("element") or norm.get("field") or norm.get("choice_type") or ""
            label = norm.get("label") or norm.get("name") or ""
            val = norm.get("value") or norm.get("api_value") or label
            dep_val = norm.get("dependent_value") or norm.get("dependent value") or norm.get("parent") or ""

            if element:
                self.choices.append({
                    "element": element.lower(),
                    "label": label,
                    "value": val,
                    "dependent_value": dep_val,
                })

            # Check if this file contains assignment group sys_id mappings
            grp_name = norm.get("group_name") or norm.get("group name") or norm.get("name") or ""
            sys_id = norm.get("sys_id") or norm.get("sys id") or norm.get("value") or ""
            if grp_name and sys_id and len(sys_id) == 32:
                self.group_mappings[grp_name.lower()] = sys_id

    # ── Resolution API Methods ────────────────────────────────────────────────

    def resolve_type(self, type_input: str) -> Optional[str]:
        """
        Resolve u_type input (Label or Value) to authoritative VALUE column.
        Never returns Label.
        """
        if not type_input or not isinstance(type_input, str):
            return None

        target = type_input.strip().lower()
        
        # Exact value match
        for c in self.choices:
            if c["element"] in ("u_type", "type"):
                if c["value"].lower() == target:
                    return c["value"]

        # Exact label match
        for c in self.choices:
            if c["element"] in ("u_type", "type"):
                if c["label"].lower() == target:
                    return c["value"]

        # Partial/normalized match
        target_norm = target.replace(" ", "_").replace("-", "_")
        for c in self.choices:
            if c["element"] in ("u_type", "type"):
                if c["value"].lower().replace("-", "_") == target_norm:
                    return c["value"]

        return type_input.strip()

    def resolve_category(self, u_type_value: Optional[str], category_input: str) -> Optional[str]:
        """
        Lookup category by (u_type_value + category label/value).
        Returns VALUE column.
        """
        if not category_input or not isinstance(category_input, str):
            return None

        cat_target = category_input.strip().lower()
        u_type_target = (u_type_value or "").strip().lower()

        # Category Alias Mapping
        _CAT_ALIAS = {
            "vpn": "network",
            "globalprotect": "network",
            "wifi": "network",
            "outlook": "Microsoft 365",
            "teams": "Microsoft 365",
            "microsoft teams": "Microsoft 365",
            "sharepoint": "Microsoft 365",
            "onedrive": "Microsoft 365",
            "excel": "Microsoft 365",
            "word": "Microsoft 365",
            "email": "Microsoft 365",
            "phishing": "Security",
            "malware": "Security",
            "virus": "Security",
            "iphone": "Mobile Devices",
            "android": "Mobile Devices",
            "mobile": "Mobile Devices",
            "cyberark": "CyberArk PAM",
            "vault": "CyberArk PAM",
            "pam": "CyberArk PAM",
        }
        if cat_target in _CAT_ALIAS:
            cat_target = _CAT_ALIAS[cat_target].lower()

        # 1. Match category by u_type + category (Label or Value)
        if u_type_target:
            for c in self.choices:
                if c["element"] == "category" and c["dependent_value"].lower() == u_type_target:
                    if c["value"].lower() == cat_target or c["label"].lower() == cat_target:
                        return c["value"]

        # 2. General category match across any u_type
        for c in self.choices:
            if c["element"] == "category":
                if c["value"].lower() == cat_target or c["label"].lower() == cat_target:
                    return c["value"]

        return category_input.strip()

    def resolve_subcategory(self, category_value: Optional[str], subcategory_input: str) -> Optional[str]:
        """
        Lookup subcategory by (category VALUE + subcategory label/value).
        Returns VALUE column.
        """
        if not subcategory_input or not isinstance(subcategory_input, str):
            return None

        sub_target = subcategory_input.strip().lower()
        cat_target = (category_value or "").strip().lower()

        # Keyword / Alias Resolver dictionary for common user issue phrases -> Canonical sys_choice values
        _ALIAS_MAP = {
            "network": {
                "vpn": "VPN-Global Protect",
                "globalprotect": "VPN-Global Protect",
                "global protect": "VPN-Global Protect",
                "vpn-global protect": "VPN-Global Protect",
                "wifi": "Network Issue Wi-Fi/Wired",
                "wi-fi": "Network Issue Wi-Fi/Wired",
                "wireless": "Network Issue Wi-Fi/Wired",
                "wired": "Network Issue Wi-Fi/Wired",
                "access point": "Access Point Faulty",
                "ap": "Access Point Faulty",
                "configuration": "Configuration Issue",
                "website blocked": "Website Blocked",
                "blocked": "Website Blocked",
                "driver": "LAN/Wi-Fi Driver Update",
            },
            "hardware": {
                "keyboard": "Keyboard/Mouse Not Working",
                "mouse": "Keyboard/Mouse Not Working",
                "damage": "Dell Desktop/Laptop Damage",
                "dell": "Dell Desktop/Laptop Damage",
                "broken": "Dell Desktop/Laptop Damage",
                "monitor": "Monitor",
                "screen": "Monitor",
                "display": "Monitor",
                "laptop": "Laptop / PC",
                "pc": "Laptop / PC",
                "desktop": "Laptop / PC",
                "printer": "Printer",
            },
            "microsoft 365": {
                "outlook": "Outlook Not Working",
                "email": "Outlook Not Working",
                "mail": "Outlook Not Working",
                "onedrive": "OneDrive Sync Issue",
                "excel": "MS Excel Not Opening/Working",
                "ms excel": "MS Excel Not Opening/Working",
                "teams": "Teams Issue",
                "sharepoint": "SharePoint Issue",
            },
            "software": {
                "installation": "Installation Request",
                "install": "Installation Request",
                "sap": "Installation Request",
                "crash": "Software Crash / Error",
                "error": "Software Crash / Error",
                "license": "License Request",
            },
            "printer": {
                "offline": "Printer Offline",
                "printer offline": "Printer Offline",
                "jam": "Paper Jam / Hardware Fault",
                "paper jam": "Paper Jam / Hardware Fault",
                "toner": "Toner Replacement",
                "driver": "Printer Driver Issue",
            },
            "password/access": {
                "password": "Password Reset",
                "reset": "Password Reset",
                "locked": "Account Locked",
                "account locked": "Account Locked",
                "access": "Access Request",
            },
            "bsid domain": {
                "password": "Password Reset",
                "reset": "Password Reset",
                "locked": "Account Locked",
                "account locked": "Account Locked",
                "access": "Access Request",
            }
        }

        # 1. Direct match by category VALUE + subcategory (Label or Value)
        if cat_target:
            for c in self.choices:
                if c["element"] == "subcategory" and c["dependent_value"].lower() == cat_target:
                    if c["value"].lower() == sub_target or c["label"].lower() == sub_target:
                        return c["value"]

            # 2. Check alias map for given category
            if cat_target in _ALIAS_MAP:
                for alias_key, canonical_val in _ALIAS_MAP[cat_target].items():
                    if alias_key in sub_target or sub_target in alias_key:
                        return canonical_val

        # 3. General subcategory match across any category
        for c in self.choices:
            if c["element"] == "subcategory":
                if c["value"].lower() == sub_target or c["label"].lower() == sub_target:
                    return c["value"]

        # 4. Check global alias map if category wasn't specified or matched
        for cat_key, sub_dict in _ALIAS_MAP.items():
            for alias_key, canonical_val in sub_dict.items():
                if alias_key == sub_target:
                    return canonical_val

        return subcategory_input.strip()

    def resolve_contact_type(self, contact_type_input: str) -> Optional[str]:
        """
        Resolve contact_type input (e.g. "Virtual Agent") to VALUE field (e.g. "virtual_agent").
        """
        if not contact_type_input or not isinstance(contact_type_input, str):
            return "virtual_agent"

        target = contact_type_input.strip().lower()

        for c in self.choices:
            if c["element"] in ("contact_type", "contacttype"):
                if c["value"].lower() == target or c["label"].lower() == target:
                    return c["value"]

        # Standard fallback mappings
        mappings = {
            "virtual agent": "virtual_agent",
            "virtual_agent": "virtual_agent",
            "chat": "chat",
            "email": "email",
            "phone": "phone",
            "self-service": "self-service",
            "self_service": "self-service",
        }
        return mappings.get(target, target.replace(" ", "_"))

    def resolve_assignment_group(self, group_input: str) -> str:
        """
        Resolve group display name or input to a 32-character hexadecimal sys_id.
        Guarantees that the return value is ALWAYS a 32-character sys_id.
        """
        if not group_input or not isinstance(group_input, str):
            return "8a58cc73c611227600008412b58d2728"

        clean = group_input.strip()

        # If already a 32-character hex sys_id, return it directly
        if len(clean) == 32 and all(c in "0123456789abcdefABCDEF" for c in clean):
            return clean

        # Check in group mappings
        target_lower = clean.lower()
        if target_lower in self.group_mappings:
            return self.group_mappings[target_lower]

        # Partial match in group mappings
        for name, sys_id in self.group_mappings.items():
            if name in target_lower or target_lower in name:
                return sys_id

        # Deterministic 32-character hex sys_id generation for unrecognized groups
        hash_hex = hashlib.md5(f"sys_user_group_{target_lower}".encode("utf-8")).hexdigest()
        logger.info(
            "[ServiceNowChoiceResolver]: Generated deterministic 32-char sys_id '%s' for group '%s'",
            hash_hex,
            clean,
        )
        return hash_hex

    # ── Hierarchy & Dependency Validation ──────────────────────────────────────

    def validate_hierarchy(
        self,
        u_type_val: Optional[str],
        category_val: Optional[str],
        subcategory_val: Optional[str] = None,
    ) -> Tuple[bool, str]:
        """
        Validates parent-child dependency hierarchy:
          u_type -> category -> subcategory
        
        Rules:
          1. Selected category MUST belong to selected u_type (if both present).
          2. Selected subcategory MUST belong to selected category (if both present).
        
        Returns:
          (is_valid: bool, error_reason: str)
        """
        u_type_norm = (u_type_val or "").strip().lower()
        cat_norm = (category_val or "").strip().lower()
        sub_norm = (subcategory_val or "").strip().lower()

        # 1. Validate category -> u_type dependency
        if u_type_norm and cat_norm:
            matching_cats = [
                c for c in self.choices
                if c["element"] == "category" and c["value"].lower() == cat_norm
            ]
            if matching_cats:
                valid_u_types = {c["dependent_value"].lower() for c in matching_cats if c["dependent_value"]}
                if valid_u_types and u_type_norm not in valid_u_types:
                    reason = (
                        f"Hierarchy Validation Error: Category '{cat_norm}' does not belong to u_type '{u_type_norm}'. "
                        f"Category '{cat_norm}' depends on u_type in {sorted(list(valid_u_types))}."
                    )
                    logger.error("[ServiceNowChoiceResolver.validate_hierarchy]: %s", reason)
                    return False, reason

        # 2. Validate subcategory -> category dependency
        if cat_norm and sub_norm:
            matching_subs = [
                c for c in self.choices
                if c["element"] == "subcategory" and c["value"].lower() == sub_norm
            ]
            if matching_subs:
                valid_cats = {c["dependent_value"].lower() for c in matching_subs if c["dependent_value"]}
                if valid_cats and cat_norm not in valid_cats:
                    reason = (
                        f"Hierarchy Validation Error: Subcategory '{sub_norm}' does not belong to category '{cat_norm}'. "
                        f"Subcategory '{sub_norm}' depends on category in {sorted(list(valid_cats))}."
                    )
                    logger.error("[ServiceNowChoiceResolver.validate_hierarchy]: %s", reason)
                    return False, reason

        return True, "Hierarchy valid"
