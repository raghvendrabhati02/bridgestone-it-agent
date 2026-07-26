"""
configuration_service.py
──────────────────────────────────────────────────────────────────────────────
Enterprise Configuration Service — single source of truth for all business
mapping configuration consumed by IncidentEnrichmentService and ClassificationService.

Design contracts (MUST NOT be violated)
-----------------------------------------
  ✓  Singleton — one instance per Python process.
  ✓  Thread-safe — protected by a module-level lock during initialisation.
  ✓  Cached — JSON files are loaded once; zero per-request I/O.
  ✓  Lazy-loaded — first call triggers load; import side-effects are zero.
  ✓  Never raises on missing keys — typed getters return safe defaults.
  ✓  No other service reads JSON directly — all consumers call this service.

JSON files loaded
-----------------
  app/data/incident_config.json
      ci_map, category_impact, category_urgency, defaults,
      valid_categories, assignment_group_map, clarification_threshold   [Phase 6]
  app/data/intent_category_map.json
      intent_category_map (intent → parent ServiceNow category)

Public API
----------
  ConfigurationService.get_instance() -> ConfigurationService
  .get_ci(category_key: str) -> Optional[str]
  .get_impact(category_key: str) -> int
  .get_urgency(category_key: str) -> int
  .get_contact_type() -> str
  .get_incident_type() -> str
  .get_default_location() -> Optional[str]
  .get_parent_category(intent: str) -> Optional[str]
  .get_default_impact() -> int
  .get_default_urgency() -> int
  .get_default_priority() -> int
  .get_mapped_category(category: Optional[str]) -> Optional[str]
  .get_mapped_subcategory(subcategory: Optional[str]) -> Optional[str]
  .get_servicenow_type(raw_type: Optional[str]) -> str
  .get_valid_categories() -> Set[str]                   [Phase 6]
  .get_clarification_threshold() -> float               [Phase 6]
  .get_assignment_group_for_category(category_key: str) -> Optional[str]  [Phase 6]
  .category_snapshot() -> List[str]                     [Phase 6]
"""

from __future__ import annotations

import json
import logging
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger("it-agent-backend")

# ── Internal data directory ───────────────────────────────────────────────────
_DATA_DIR = Path(__file__).resolve().parent.parent / "data"

_INCIDENT_CONFIG_FILE    = _DATA_DIR / "incident_config.json"
_INTENT_CATEGORY_FILE    = _DATA_DIR / "intent_category_map.json"

# ── Module-level singleton guard ──────────────────────────────────────────────
_instance: Optional["ConfigurationService"] = None
_lock: threading.Lock = threading.Lock()


class ConfigurationService:
    """
    Singleton configuration gateway.

    All business-rule mappings live in JSON files under ``app/data/``.
    This service loads them once, caches in memory, and exposes typed getters
    so no other service needs to touch JSON directly.

    Phase 6 additions
    -----------------
    - ``_valid_categories``: authoritative list of allowed ServiceNow categories,
      replacing all hardcoded Python sets in ClassificationService.
    - ``_assignment_group_map``: maps lowercase category key → default assignment
      group name (resolution lives in ConfigurationService, not the classifier).
    - ``clarification_threshold``: configurable confidence floor read by
      ClassificationService; default 0.70.
    """

    # ── Private constructor ───────────────────────────────────────────────────

    def __init__(self) -> None:
        self._ci_map:               Dict[str, str]  = {}
        self._category_impact:      Dict[str, int]  = {}
        self._category_urgency:     Dict[str, int]  = {}
        self._subcategory_map:      Dict[str, str]  = {}
        self._servicenow_type_map:  Dict[str, str]  = {}
        self._intent_category:      Dict[str, str]  = {}
        self._defaults:             Dict[str, Any]  = {}
        self._category_map:         Dict[str, str]  = {}
        # Phase 6 — new attributes
        self._valid_categories:     List[str]       = []
        self._assignment_group_map: Dict[str, str]  = {}
        self._loaded:               bool            = False
        self._load_lock:            threading.Lock  = threading.Lock()

    # ── Singleton factory ─────────────────────────────────────────────────────

    @classmethod
    def get_instance(cls) -> "ConfigurationService":
        """
        Return (or create) the process-wide singleton.
        Thread-safe via double-checked locking.
        """
        global _instance
        if _instance is None:
            with _lock:
                if _instance is None:
                    inst = cls()
                    inst._load_all()
                    _instance = inst
        return _instance

    @classmethod
    def reset_instance(cls) -> None:
        """
        Reset the singleton — **test-only**.
        Forces a fresh load on next ``get_instance()`` call.
        """
        global _instance
        with _lock:
            _instance = None

    # ── Loading ───────────────────────────────────────────────────────────────

    def _load_all(self) -> None:
        """Load all configuration JSON files. Called exactly once."""
        with self._load_lock:
            if self._loaded:
                return
            self._load_incident_config()
            self._load_intent_category_map()
            self._loaded = True
            logger.info(
                "[ConfigurationService] Loaded %d CI entries, %d impact entries, "
                "%d urgency entries, %d intent-category entries, "
                "%d valid categories, %d assignment group mappings.",
                len(self._ci_map),
                len(self._category_impact),
                len(self._category_urgency),
                len(self._intent_category),
                len(self._valid_categories),
                len(self._assignment_group_map),
            )

    def _load_incident_config(self) -> None:
        """Parse incident_config.json into in-memory dicts."""
        if not _INCIDENT_CONFIG_FILE.exists():
            logger.warning(
                "[ConfigurationService] incident_config.json not found at '%s'; "
                "falling back to empty maps (safe defaults will apply).",
                _INCIDENT_CONFIG_FILE,
            )
            return
        try:
            with open(_INCIDENT_CONFIG_FILE, "r", encoding="utf-8") as fh:
                data: Dict[str, Any] = json.load(fh)

            self._ci_map              = {k.lower(): v for k, v in data.get("ci_map", {}).items()}
            self._category_impact     = {k.lower(): int(v) for k, v in data.get("category_impact", {}).items()}
            self._category_urgency    = {k.lower(): int(v) for k, v in data.get("category_urgency", {}).items()}
            self._category_map        = {k.lower(): v for k, v in data.get("category_map", {}).items()}
            self._subcategory_map     = {k.lower(): v for k, v in data.get("subcategory_map", {}).items()}
            self._servicenow_type_map = {k.lower(): v for k, v in data.get("servicenow_type_map", {}).items()}
            self._defaults            = data.get("defaults", {})

            # Phase 6 — load valid_categories list
            raw_cats = data.get("valid_categories", [])
            self._valid_categories = [str(c) for c in raw_cats if c]

            # Phase 6 — load assignment_group_map (keys lowercased, values preserved)
            self._assignment_group_map = {
                k.lower(): str(v)
                for k, v in data.get("assignment_group_map", {}).items()
                if k and v
            }

        except Exception as exc:
            logger.error(
                "[ConfigurationService] Failed to parse incident_config.json: %s — "
                "continuing with empty maps.",
                exc,
            )

    def _load_intent_category_map(self) -> None:
        """Parse intent_category_map.json into in-memory dict.

        Keys starting with '_' are skipped — they are human-readable comment
        markers added in Phase 6 for maintainability.
        """
        if not _INTENT_CATEGORY_FILE.exists():
            logger.warning(
                "[ConfigurationService] intent_category_map.json not found at '%s'.",
                _INTENT_CATEGORY_FILE,
            )
            return
        try:
            with open(_INTENT_CATEGORY_FILE, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            raw: Dict[str, str] = data.get("intent_category_map", {})
            # Skip comment-marker keys (prefixed with '_') and non-string values
            self._intent_category = {
                k.lower(): v.lower()
                for k, v in raw.items()
                if not k.startswith("_") and isinstance(v, str)
            }
        except Exception as exc:
            logger.error(
                "[ConfigurationService] Failed to parse intent_category_map.json: %s",
                exc,
            )

    # ── Public getters ────────────────────────────────────────────────────────

    def get_ci(self, category_key: str) -> Optional[str]:
        """
        Return the Configuration Item name for ``category_key``.

        Returns ``None`` when the key is unknown (safe — caller omits cmdb_ci).
        """
        return self._ci_map.get((category_key or "").lower())

    def get_impact(self, category_key: str) -> int:
        """
        Return the ServiceNow impact integer (1=High, 2=Medium, 3=Low) for
        ``category_key``.  Falls back to the configured ``default_impact`` (3).
        """
        default = int(self._defaults.get("default_impact", 3))
        return self._category_impact.get((category_key or "").lower(), default)

    def get_urgency(self, category_key: str) -> int:
        """
        Return the ServiceNow urgency integer (1=High, 2=Medium, 3=Low) for
        ``category_key``.  Falls back to the configured ``default_urgency`` (3).
        """
        default = int(self._defaults.get("default_urgency", 3))
        return self._category_urgency.get((category_key or "").lower(), default)

    def get_contact_type(self) -> str:
        """Return the configured contact type (default: ``"Virtual Agent"``)."""
        return str(self._defaults.get("contact_type", "Virtual Agent"))

    def get_incident_type(self) -> str:
        """Return the configured incident type (default: ``"Incident"``)."""
        return str(self._defaults.get("incident_type", "Incident"))

    def get_mapped_category(self, category: Optional[str]) -> Optional[str]:
        """
        Map a vendor-neutral category to an instance-specific choice value via incident_config.json.
        Returns the original category if no override mapping exists.
        """
        if not category:
            return category
        mapped = self._category_map.get(category.strip().lower())
        return mapped if mapped else category

    def get_mapped_subcategory(self, subcategory: Optional[str]) -> Optional[str]:
        """
        Map a vendor-neutral subcategory to an instance-specific choice value via incident_config.json.
        Returns the original subcategory if no override mapping exists.
        """
        if not subcategory:
            return subcategory
        mapped = self._subcategory_map.get(subcategory.strip().lower())
        return mapped if mapped else subcategory

    def get_servicenow_type(self, raw_type: Optional[str]) -> str:
        """
        Map generic incident type to the target ServiceNow instance choice value via incident_config.json.
        Falls back to configured default.
        """
        target_key = (raw_type or "incident").strip().lower()
        mapped = self._servicenow_type_map.get(target_key)
        if mapped:
            return mapped
        return self.get_incident_type()

    def get_default_location(self) -> Optional[str]:
        """Return the configured default location, or ``None`` if not set."""
        val = self._defaults.get("default_location")
        return str(val) if val else None

    def get_default_impact(self) -> int:
        """Return the configured default impact (fallback: 3)."""
        return int(self._defaults.get("default_impact", 3))

    def get_default_urgency(self) -> int:
        """Return the configured default urgency (fallback: 3)."""
        return int(self._defaults.get("default_urgency", 3))

    def get_default_priority(self) -> int:
        """Return the configured default priority (fallback: 4)."""
        return int(self._defaults.get("default_priority", 4))

    def get_parent_category(self, intent: str) -> Optional[str]:
        """
        Map a raw intent keyword to a ServiceNow parent category value.

        Example:
            get_parent_category("vpn") -> "network"
            get_parent_category("outlook") -> "microsoft 365"

        Returns ``None`` when the intent is unknown.
        """
        return self._intent_category.get((intent or "").lower())

    # ── Phase 6 — New Public Getters ──────────────────────────────────────────

    def get_valid_categories(self) -> Set[str]:
        """
        Return the set of allowed ServiceNow categories loaded from
        ``incident_config.json["valid_categories"]``.

        This is the single authoritative source for hallucination rejection in
        ClassificationService — replaces all hardcoded Python sets.

        Returns an empty set if ``valid_categories`` was absent from the JSON
        (ClassificationService falls back to FieldMappingService in that case).
        """
        return set(self._valid_categories)

    def get_clarification_threshold(self) -> float:
        """
        Return the minimum LLM confidence score below which the classifier
        should ask the user for clarification.

        Loaded from ``incident_config.json["clarification_threshold"]``.
        Default: ``0.70`` (backward-compatible).
        """
        raw = self._defaults.get("clarification_threshold")
        if raw is None:
            # Also check top-level key for convenience
            return 0.70
        try:
            val = float(raw)
            return max(0.0, min(1.0, val))
        except (TypeError, ValueError):
            return 0.70

    def get_assignment_group_for_category(self, category_key: str) -> Optional[str]:
        """
        Return the default ServiceNow assignment group name for a given category key.

        Loaded from ``incident_config.json["assignment_group_map"]``.
        The lookup is case-insensitive.

        Returns ``None`` when the category key has no configured group —
        callers should apply their own fallback (e.g. ``"IT Support"``).

        Example:
            get_assignment_group_for_category("network") -> "Network Team"
            get_assignment_group_for_category("Security") -> "Security Team"
            get_assignment_group_for_category("unknown") -> None
        """
        return self._assignment_group_map.get((category_key or "").lower())

    # ── Snapshot helpers (testing / debugging) ────────────────────────────────

    def ci_map_snapshot(self) -> Dict[str, str]:
        """Return a copy of the CI map (for diagnostics / tests)."""
        return dict(self._ci_map)

    def impact_map_snapshot(self) -> Dict[str, int]:
        """Return a copy of the category_impact map (for diagnostics / tests)."""
        return dict(self._category_impact)

    def urgency_map_snapshot(self) -> Dict[str, int]:
        """Return a copy of the category_urgency map (for diagnostics / tests)."""
        return dict(self._category_urgency)

    def intent_category_snapshot(self) -> Dict[str, str]:
        """Return a copy of the intent_category map (for diagnostics / tests)."""
        return dict(self._intent_category)

    def category_snapshot(self) -> List[str]:
        """Return a copy of the valid_categories list (for diagnostics / tests)."""
        return list(self._valid_categories)
