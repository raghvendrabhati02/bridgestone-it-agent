"""
servicenow_metadata_validator.py
─────────────────────────────────────────────────────────────────────────────
ServiceNow Metadata Validator. Validates configured ITSM values against the
ServiceNowMetadataCache and generates comprehensive validation reports.
"""

import logging
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional

from app.services.servicenow_metadata_cache import ServiceNowMetadataCache
from app.services.configuration_service import ConfigurationService

logger = logging.getLogger("it-agent-backend")


@dataclass
class ValidationResult:
    """Represents the validation result of a single metadata element."""

    field_name: str
    value: str
    is_valid: bool
    status: str  # "VALID" | "MISSING"
    parent_category: Optional[str] = None
    suggested_choices: List[str] = field(default_factory=list)
    details: str = ""


class ServiceNowMetadataValidator:
    """Validates ServiceNow incident metadata against cached instance metadata."""

    def __init__(self, cache: Optional[ServiceNowMetadataCache] = None) -> None:
        self.cache = cache or ServiceNowMetadataCache.get_instance()
        self.config = ConfigurationService.get_instance()

    def validate_category(self, category: str) -> ValidationResult:
        """Validate if category exists in ServiceNow metadata cache."""
        if not category or not category.strip():
            return ValidationResult("category", category or "", False, "MISSING", details="Category is empty")

        cat_norm = category.strip().lower()
        cached_cats = self.cache.get_categories()
        
        is_valid = any(
            c.get("value", "").lower() == cat_norm or c.get("label", "").lower() == cat_norm
            for c in cached_cats
        )

        if not is_valid:
            # Also check valid_categories in ConfigurationService
            valid_config_cats = [c.lower() for c in self.config.get_valid_categories()]
            if cat_norm in valid_config_cats:
                is_valid = True

        status = "VALID" if is_valid else "MISSING"
        return ValidationResult("category", category, is_valid, status)

    def validate_subcategory(self, subcategory: str, category: Optional[str] = None) -> ValidationResult:
        """Validate if subcategory exists under parent category in ServiceNow metadata cache."""
        if not subcategory or not subcategory.strip():
            return ValidationResult("subcategory", subcategory or "", False, "MISSING", parent_category=category, details="Subcategory is empty")

        sub_norm = subcategory.strip().lower()
        cat_subchoices = self.cache.get_subcategories(category)

        # Exact match check against value or label
        is_valid = any(
            s.get("value", "").lower() == sub_norm or s.get("label", "").lower() == sub_norm
            for s in cat_subchoices
        )

        suggested: List[str] = []
        if not is_valid:
            # Gather suggested valid choices under category for report visualization
            all_cat_choices = self.cache.get_subcategories(category)
            if not all_cat_choices:
                all_cat_choices = self.cache.get_subcategories(None)
            
            for choice in all_cat_choices:
                lbl = choice.get("label") or choice.get("value")
                if lbl and lbl not in suggested:
                    suggested.append(lbl)
            
            # Add known instance choice fallbacks if empty
            if not suggested and category and category.lower() in ["microsoft 365", "m365"]:
                suggested = ["Outlook Not Working", "MS Excel Not Opening/Working"]

        status = "VALID" if is_valid else "MISSING"
        return ValidationResult("subcategory", subcategory, is_valid, status, parent_category=category, suggested_choices=suggested)

    def validate_assignment_group(self, group_identifier: str) -> ValidationResult:
        """Validate if assignment group name or sys_id exists in ServiceNow metadata cache."""
        if not group_identifier or not group_identifier.strip():
            return ValidationResult("assignment_group", group_identifier or "", False, "MISSING", details="Group identifier is empty")

        grp_norm = group_identifier.strip().lower()
        cached_groups = self.cache.get_assignment_groups()

        is_valid = any(
            g.get("name", "").lower() == grp_norm or g.get("sys_id", "").lower() == grp_norm
            for g in cached_groups
        )

        status = "VALID" if is_valid else "MISSING"
        return ValidationResult("assignment_group", group_identifier, is_valid, status)

    def validate_cmdb_ci(self, ci_identifier: str) -> ValidationResult:
        """Validate if CMDB CI name or sys_id exists in ServiceNow metadata cache."""
        if not ci_identifier or not ci_identifier.strip():
            return ValidationResult("cmdb_ci", ci_identifier or "", False, "MISSING", details="CMDB CI is empty")

        ci_norm = ci_identifier.strip().lower()
        cached_cis = self.cache.get_cmdb_cis()

        is_valid = any(
            c.get("name", "").lower() == ci_norm or c.get("sys_id", "").lower() == ci_norm
            for c in cached_cis
        )

        status = "VALID" if is_valid else "MISSING"
        return ValidationResult("cmdb_ci", ci_identifier, is_valid, status)

    def generate_report_markdown(self) -> str:
        """Generate complete markdown report detailing valid & missing metadata."""
        stats = self.cache.get_stats()
        cats = self.config.get_valid_categories()
        subcat_map = getattr(self.config, "_subcategory_map", {})
        group_map = getattr(self.config, "_assignment_group_map", {})
        ci_map = getattr(self.config, "_ci_map", {})

        lines = [
            "# ServiceNow Metadata Validation & Integration Audit Report",
            "",
            "## Metadata Metadata & Version Header",
            "",
            f"- **Metadata Source**: {stats['source']}",
            f"- **Fetched Timestamp**: {stats['last_refresh']}",
            f"- **Cache Age**: {stats['cache_age_seconds']} seconds (TTL: {stats['ttl_seconds']}s)",
            f"- **Total Categories**: {stats['categories']}",
            f"- **Total Subcategories**: {stats['subcategories']}",
            f"- **Total Assignment Groups**: {stats['groups']}",
            f"- **Total CMDB Records**: {stats['cmdb_records']}",
            "",
            "---",
            "",
            "## Configured Metadata Validation Summary",
            "",
        ]

        # 1. Categories Section
        lines.append("### Categories Validation")
        lines.append("")
        for cat in cats:
            res = self.validate_category(cat)
            symbol = "✔" if res.is_valid else "✖"
            lines.append(f"- {symbol} **Category**: `{cat}` | **Status**: `{res.status}`")
        lines.append("")

        # 2. Subcategories Section
        lines.append("### Subcategories Validation")
        lines.append("")
        unique_subcats = set(subcat_map.values())
        for sub in sorted(unique_subcats):
            res = self.validate_subcategory(sub)
            symbol = "✔" if res.is_valid else "✖"
            lines.append(f"- {symbol} **Subcategory**: `{sub}` | **Status**: `{res.status}`")
            if not res.is_valid and res.suggested_choices:
                lines.append("  - **Suggested Choices in ServiceNow**:")
                for sug in res.suggested_choices[:5]:
                    lines.append(f"    - `{sug}`")
        lines.append("")

        # 3. Assignment Groups Section
        lines.append("### Assignment Groups Validation")
        lines.append("")
        unique_groups = set(group_map.values())
        for grp in sorted(unique_groups):
            res = self.validate_assignment_group(grp)
            symbol = "✔" if res.is_valid else "✖"
            lines.append(f"- {symbol} **Assignment Group**: `{grp}` | **Status**: `{res.status}`")
        lines.append("")

        # 4. CMDB Configuration Items Section
        lines.append("### CMDB Configuration Items Validation")
        lines.append("")
        unique_cis = set(ci_map.values())
        for ci in sorted(unique_cis):
            res = self.validate_cmdb_ci(ci)
            symbol = "✔" if res.is_valid else "✖"
            lines.append(f"- {symbol} **CMDB CI**: `{ci}` | **Status**: `{res.status}`")
        lines.append("")

        return "\n".join(lines)
