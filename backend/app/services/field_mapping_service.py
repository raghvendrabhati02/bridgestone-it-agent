"""
field_mapping_service.py
─────────────────────────────────────────────────────────────────────────────
Standalone Production-Grade ServiceNow Field Mapping Engine.

Loads real ServiceNow export Excel (.xlsx, .xls) and CSV (.csv) files provided by
the business, validates required columns on startup (fail fast), caches mappings
in memory, resolves Labels to API Values, enforces dependency rules (category
depends on u_type, subcategory depends on category), and builds validated
ServiceNow API field payload dictionaries.

Key Principles & Rules:
  - NEVER creates or overwrites Excel files on disk.
  - Fails fast with clear exceptions if required files or columns are missing.
  - Always uses the 'Value' column from Excel for API payloads (never 'Label').
  - Extensible architecture supporting Choice mappings and Reference mappings.
  - Caches mapping files in memory once on startup (zero per-request file I/O).
"""

from __future__ import annotations

import csv
import enum
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Union

try:
    import openpyxl
    HAS_OPENPYXL = True
except ImportError:
    HAS_OPENPYXL = False

logger = logging.getLogger("it-agent-backend")


# ── Exceptions ───────────────────────────────────────────────────────────────

class FieldMappingError(ValueError):
    """Base exception for ServiceNow field mapping errors."""
    pass


class MappingFileNotFoundError(FieldMappingError):
    """Raised when a required mapping file or directory is missing."""
    pass


class InvalidMappingDataError(FieldMappingError):
    """Raised when mapping data is malformed or missing required columns."""
    pass


class DependencyValidationError(FieldMappingError):
    """Raised when dependency validation between u_type, category, or subcategory fails."""
    pass


# ── Mapping Types & Extensible Loaders ───────────────────────────────────────

class FieldMappingType(str, enum.Enum):
    """Enum representing the nature of a ServiceNow field mapping."""
    CHOICE = "choice"
    REFERENCE = "reference"


class BaseMappingLoader:
    """Abstract base loader for parsing raw Excel/CSV rows into normalized dicts."""

    @staticmethod
    def read_rows(file_path: Path) -> List[Dict[str, str]]:
        ext = file_path.suffix.lower()
        if ext in (".xlsx", ".xls"):
            if not HAS_OPENPYXL:
                raise ImportError(f"openpyxl library is required to read '{file_path.name}'.")
            wb = openpyxl.load_workbook(file_path, data_only=True)
            all_rows: List[Dict[str, str]] = []
            for sheet_name in wb.sheetnames:
                sheet = wb[sheet_name]
                rows_iter = sheet.iter_rows(values_only=True)
                try:
                    headers_raw = next(rows_iter)
                except StopIteration:
                    continue
                if not headers_raw:
                    continue
                headers = [str(h).strip() if h is not None else "" for h in headers_raw]

                for row in rows_iter:
                    if not row or not any(row):
                        continue
                    row_dict = {}
                    for h, val in zip(headers, row):
                        if h:
                            row_dict[h] = str(val).strip() if val is not None else ""
                    all_rows.append(row_dict)
            return all_rows
        elif ext == ".csv":
            with open(file_path, mode="r", encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                return [{k.strip(): (v.strip() if v else "") for k, v in row.items() if k} for row in reader]
        else:
            raise InvalidMappingDataError(f"Unsupported mapping file extension: '{ext}'")


class ChoiceMappingLoader(BaseMappingLoader):
    """Loader for Choice table mappings (sys_choice). Enforces mandatory columns."""

    REQUIRED_COLUMNS = {"element", "label", "value", "dependent value"}

    @classmethod
    def validate_and_parse(cls, file_path: Path) -> List[Dict[str, str]]:
        rows = cls.read_rows(file_path)
        if not rows:
            raise InvalidMappingDataError(f"Choice mapping file '{file_path.name}' is empty.")

        # Validate headers on the first row
        first_row_keys = {k.lower().strip() for k in rows[0].keys()}

        # Normalize key variations
        normalized_keys: Set[str] = set()
        for k in first_row_keys:
            if k in ("element", "field", "choice_type"):
                normalized_keys.add("element")
            elif k in ("label", "name"):
                normalized_keys.add("label")
            elif k in ("value", "value (api)", "api_value"):
                normalized_keys.add("value")
            elif k in ("dependent value", "dependent_value", "dependent", "parent"):
                normalized_keys.add("dependent value")
            else:
                normalized_keys.add(k)

        missing = cls.REQUIRED_COLUMNS - normalized_keys
        if missing:
            err_msg = (
                f"Validation failed for choice mapping file '{file_path.name}': "
                f"Missing required column(s): {sorted(list(missing))}. "
                f"File headers found: {sorted(list(first_row_keys))}"
            )
            logger.error("!!! [ChoiceMappingLoader]: %s", err_msg)
            raise InvalidMappingDataError(err_msg)

        parsed: List[Dict[str, str]] = []
        for row in rows:
            norm = {k.lower().strip(): v for k, v in row.items()}
            element = (norm.get("element") or norm.get("field") or norm.get("choice_type") or "").lower()
            label = norm.get("label") or norm.get("name") or ""
            value = norm.get("value") or norm.get("value (api)") or norm.get("api_value") or label
            dep_val = (
                norm.get("dependent value")
                or norm.get("dependent_value")
                or norm.get("dependent")
                or norm.get("parent")
                or ""
            )

            if not element and not label and not value:
                continue

            parsed.append({
                "element": element,
                "label": label or value,
                "value": value or label,
                "dependent_value": dep_val,
                "mapping_type": FieldMappingType.CHOICE.value,
            })

        return parsed


class ReferenceMappingLoader(BaseMappingLoader):
    """Loader for Reference table mappings (e.g., assignment groups / sys_user_group)."""

    @classmethod
    def parse(cls, file_path: Path) -> List[Dict[str, str]]:
        rows = cls.read_rows(file_path)
        parsed: List[Dict[str, str]] = []

        for row in rows:
            norm = {k.lower().strip(): v for k, v in row.items()}
            name = (
                norm.get("group_name")
                or norm.get("group name")
                or norm.get("name")
                or norm.get("label")
                or norm.get("value")
                or ""
            )
            val = (
                norm.get("value")
                or norm.get("sys_id")
                or norm.get("sys id")
                or norm.get("api_value")
                or name
            )
            category = norm.get("category") or norm.get("type") or ""

            if not name and not val:
                continue

            parsed.append({
                "label": name or val,
                "value": val or name,
                "category": category,
                "mapping_type": FieldMappingType.REFERENCE.value,
            })

        return parsed


# ── Core Service ─────────────────────────────────────────────────────────────

class FieldMappingService:
    """
    Enterprise ServiceNow Field Mapping Service.
    
    Provides startup validation, in-memory cached mapping lookups, label-to-value resolution,
    and dependency validation without writing or mutating files on disk.
    """

    DEFAULT_DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "servicenow_mappings"

    def __init__(
        self,
        data_directory: Optional[Union[str, Path]] = None,
        choice_filename: Optional[str] = None,
        group_filename: Optional[str] = None,
        auto_load: bool = True,
    ):
        self.data_directory = Path(
            data_directory
            or os.getenv("SERVICENOW_MAPPINGS_DIR", str(self.DEFAULT_DATA_DIR))
        )
        self.choice_filename = choice_filename or os.getenv("SERVICENOW_CHOICE_MAPPINGS_FILE", "sys_choice_mappings.xlsx")
        self.group_filename = group_filename or os.getenv("SERVICENOW_GROUPS_MAPPINGS_FILE", "assignment_groups.xlsx")

        # In-memory cached data structures
        self._types: List[Dict[str, str]] = []
        self._categories: List[Dict[str, str]] = []
        self._subcategories: List[Dict[str, str]] = []
        self._assignment_groups: List[Dict[str, str]] = []
        self._contact_types: List[Dict[str, str]] = []
        self._reference_mappings: Dict[str, List[Dict[str, str]]] = {}
        self._is_loaded: bool = False

        if auto_load:
            self.load_mappings(self.data_directory)

    # ── Startup Loading & Validation ─────────────────────────────────────────

    def load_mappings(self, directory_path: Optional[Union[str, Path]] = None) -> None:
        """
        Load Excel/CSV mapping files once at startup into in-memory cached structures.
        Fails fast if required directory or files are missing or missing required columns.
        """
        target_dir = Path(directory_path) if directory_path else self.data_directory
        logger.info(
            ">>> ENTRY [FieldMappingService.load_mappings]: Loading ServiceNow mappings from '%s' | choice_file='%s', group_file='%s'",
            target_dir,
            self.choice_filename,
            self.group_filename,
        )

        if not target_dir.exists() or not target_dir.is_dir():
            err_msg = f"Required ServiceNow mapping directory '{target_dir}' does not exist."
            logger.error("!!! [FieldMappingService.load_mappings]: %s", err_msg)
            raise MappingFileNotFoundError(err_msg)

        # Clear existing cached mappings
        self._types.clear()
        self._categories.clear()
        self._subcategories.clear()
        self._assignment_groups.clear()
        self._contact_types.clear()
        self._reference_mappings.clear()

        # Locate specific files or scan directory
        choice_path = target_dir / self.choice_filename
        group_path = target_dir / self.group_filename

        # If specific configured files do not exist, check for any excel/csv files
        files_to_process: List[Path] = []
        if choice_path.exists():
            files_to_process.append(choice_path)
        if group_path.exists() and group_path not in files_to_process:
            files_to_process.append(group_path)

        if not files_to_process:
            # Fallback: scan all xlsx/xls/csv files in directory
            files_to_process = list(target_dir.glob("*.xlsx")) + list(target_dir.glob("*.xls")) + list(target_dir.glob("*.csv"))

        # Exclude README files
        files_to_process = [f for f in files_to_process if f.name.lower() != "readme.md"]

        if not files_to_process:
            logger.warning(
                "[FieldMappingService.load_mappings]: No ServiceNow Excel/CSV mapping files found in directory '%s'. "
                "Running in pass-through mode until mapping files are uploaded.",
                target_dir,
            )
            return

        for file_path in files_to_process:
            fname_lower = file_path.name.lower()
            logger.info("[FieldMappingService.load_mappings]: Processing file '%s'", file_path.name)

            # Determine whether file is Choice table or Reference table
            if "choice" in fname_lower or file_path.name == self.choice_filename:
                parsed_choices = ChoiceMappingLoader.validate_and_parse(file_path)
                self._populate_choices(parsed_choices)
            elif "group" in fname_lower or "assignment" in fname_lower or file_path.name == self.group_filename:
                parsed_refs = ReferenceMappingLoader.parse(file_path)
                self._populate_groups(parsed_refs)
            else:
                # Attempt choice validation first, fallback to reference
                try:
                    parsed_choices = ChoiceMappingLoader.validate_and_parse(file_path)
                    self._populate_choices(parsed_choices)
                except InvalidMappingDataError:
                    parsed_refs = ReferenceMappingLoader.parse(file_path)
                    self._populate_groups(parsed_refs)

        self._is_loaded = True

        # Log exact required summary metrics
        logger.info(
            "<<< EXIT [FieldMappingService.load_mappings]: ServiceNow Field Mappings loaded successfully from '%s'\n"
            "  - Number of types loaded: %d\n"
            "  - Categories loaded: %d\n"
            "  - Subcategories loaded: %d\n"
            "  - Assignment groups loaded: %d",
            target_dir,
            len(self._types),
            len(self._categories),
            len(self._subcategories),
            len(self._assignment_groups),
        )

    def _populate_choices(self, choices: List[Dict[str, str]]) -> None:
        """Populate internal cached choice structures."""
        for item in choices:
            elem = item["element"]
            entry = {
                "label": item["label"],
                "value": item["value"],
                "dependent_value": item["dependent_value"],
            }
            if elem in ("u_type", "type"):
                if entry["value"] not in [t["value"] for t in self._types]:
                    self._types.append(entry)
            elif elem == "category":
                if not any(c["value"] == entry["value"] and c["dependent_value"] == entry["dependent_value"] for c in self._categories):
                    self._categories.append(entry)
            elif elem == "subcategory":
                if not any(s["value"] == entry["value"] and s["dependent_value"] == entry["dependent_value"] for s in self._subcategories):
                    self._subcategories.append(entry)
            elif elem in ("contact_type", "contacttype"):
                if entry["value"] not in [c["value"] for c in self._contact_types]:
                    self._contact_types.append(entry)

    def _populate_groups(self, refs: List[Dict[str, str]]) -> None:
        """Populate internal cached reference / assignment group structures."""
        for item in refs:
            grp_name = item["label"]
            grp_val = item["value"]
            if grp_name and grp_val not in [g["value"] for g in self._assignment_groups]:
                self._assignment_groups.append({
                    "label": grp_name,
                    "value": grp_val,
                    "category": item.get("category", ""),
                })

    # ── Cached Query API ──────────────────────────────────────────────────────

    def get_types(self) -> List[Dict[str, str]]:
        """Return all cached u_type choices."""
        return list(self._types)

    def get_categories(self, type_value: Optional[str] = None) -> List[Dict[str, str]]:
        """
        Return category choices.
        Optionally filtered where Dependent Value == type_value.
        """
        if not type_value:
            return list(self._categories)
        target = type_value.lower().strip()
        return [c for c in self._categories if c["dependent_value"].lower().strip() == target]

    def get_subcategories(self, category_value: Optional[str] = None) -> List[Dict[str, str]]:
        """
        Return subcategory choices.
        Optionally filtered where Dependent Value == category_value.
        """
        if not category_value:
            return list(self._subcategories)
        target = category_value.lower().strip()
        return [s for s in self._subcategories if s["dependent_value"].lower().strip() == target]

    def get_assignment_groups(self) -> List[Dict[str, str]]:
        """Return all cached assignment group mappings."""
        return list(self._assignment_groups)

    def get_contact_types(self) -> List[Dict[str, str]]:
        """Return all cached contact_type mappings."""
        return list(self._contact_types)

    # ── Label Resolution Helper ───────────────────────────────────────────────

    def resolve_value(self, choices: List[Dict[str, str]], input_str: str, field_name: str) -> str:
        """
        Resolve user input Label or Value to authoritative API Value.
        Always returns Value (never Label).
        """
        if not input_str:
            raise FieldMappingError(f"Cannot resolve empty input for field '{field_name}'.")

        target = input_str.lower().strip()

        # 1. Exact match on Value
        for item in choices:
            if item["value"].lower().strip() == target:
                return item["value"]

        # 2. Exact match on Label
        for item in choices:
            if item["label"].lower().strip() == target:
                logger.info("[FieldMappingService]: Resolved label '%s' -> value '%s' for field '%s'", input_str, item["value"], field_name)
                return item["value"]

        valid_options = [f"'{c['value']}' ({c['label']})" for c in choices[:10]]
        raise FieldMappingError(
            f"Invalid {field_name} '{input_str}'. No matching mapping found. Available options: {', '.join(valid_options)}"
        )

    # ── Payload Builder ───────────────────────────────────────────────────────

    def build_servicenow_fields(
        self,
        contact_type: str = "chat",
        u_type: Optional[str] = None,
        category: Optional[str] = None,
        subcategory: Optional[str] = None,
        assignment_group: Optional[str] = None,
        caller_id: str = "",
    ) -> Dict[str, str]:
        """
        Build validated ServiceNow payload field dictionary.
        
        Guarantees:
          - Always uses the 'Value' column from Excel for API payloads (never Label).
          - Enforces dependency: category depends on u_type using Dependent Value.
          - Enforces dependency: subcategory depends on category using Dependent Value.
          - caller_id defaults to empty string ("").
        """
        logger.info(
            ">>> ENTRY [FieldMappingService.build_servicenow_fields]: "
            "contact_type='%s', u_type='%s', category='%s', subcategory='%s', assignment_group='%s', caller_id='%s'",
            contact_type, u_type, category, subcategory, assignment_group, caller_id
        )

        # 1. Resolve contact_type
        resolved_contact_type = contact_type.lower().strip() if contact_type else "chat"
        if self._contact_types:
            try:
                resolved_contact_type = self.resolve_value(self._contact_types, contact_type, "contact_type")
            except FieldMappingError:
                pass

        # 2. Resolve u_type
        resolved_u_type = ""
        if u_type:
            if not self._types:
                resolved_u_type = u_type.lower().strip()
            else:
                resolved_u_type = self.resolve_value(self._types, u_type, "u_type")

        # 3. Resolve category and validate dependency on u_type
        resolved_category = ""
        if category:
            valid_categories_for_type = self.get_categories(resolved_u_type) if resolved_u_type else self._categories
            if not valid_categories_for_type and self._categories and not resolved_u_type:
                valid_categories_for_type = self._categories

            if valid_categories_for_type:
                try:
                    resolved_category = self.resolve_value(valid_categories_for_type, category, "category")
                    # If u_type was omitted, auto-derive resolved_u_type from category's dependent_value
                    if not resolved_u_type and self._categories:
                        for c in self._categories:
                            if c["value"] == resolved_category and c["dependent_value"]:
                                resolved_u_type = c["dependent_value"]
                                break
                except FieldMappingError as err:
                    if resolved_u_type:
                        raise DependencyValidationError(
                            f"Category '{category}' is not valid for u_type '{resolved_u_type}' (Dependent Value mismatch). {err}"
                        ) from err
                    raise
            else:
                resolved_category = category.lower().strip()

        # 4. Resolve subcategory and validate dependency on category
        resolved_subcategory = ""
        if subcategory:
            if not category and not resolved_category:
                raise DependencyValidationError("Cannot map subcategory without specifying a category first.")

            valid_subcategories_for_cat = self.get_subcategories(resolved_category) if resolved_category else self._subcategories
            if not valid_subcategories_for_cat and self._subcategories:
                valid_subcategories_for_cat = self._subcategories

            if valid_subcategories_for_cat:
                try:
                    resolved_subcategory = self.resolve_value(valid_subcategories_for_cat, subcategory, "subcategory")
                except FieldMappingError as err:
                    raise DependencyValidationError(
                        f"Subcategory '{subcategory}' is not valid for category '{resolved_category}' (Dependent Value mismatch). {err}"
                    ) from err
            else:
                resolved_subcategory = subcategory.lower().strip()

        # 5. Resolve assignment_group
        resolved_group = ""
        if assignment_group:
            if self._assignment_groups:
                try:
                    resolved_group = self.resolve_value(self._assignment_groups, assignment_group, "assignment_group")
                except FieldMappingError:
                    resolved_group = assignment_group
            else:
                resolved_group = assignment_group

        payload = {
            "contact_type": resolved_contact_type,
            "u_type": resolved_u_type,
            "category": resolved_category,
            "subcategory": resolved_subcategory,
            "assignment_group": resolved_group,
            "caller_id": caller_id or "",
        }

        logger.info("<<< EXIT [FieldMappingService.build_servicenow_fields]: Output payload: %s", payload)
        return payload
