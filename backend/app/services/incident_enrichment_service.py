"""
incident_enrichment_service.py
──────────────────────────────────────────────────────────────────────────────
Enterprise ServiceNow Incident Enrichment Service.

Responsibilities
----------------
• Build a fully-populated IncidentMetadata from existing classification,
  troubleshooting state, and TicketSummary — entirely without LLM calls.
• Deterministically derive Impact, Urgency, Priority (ServiceNow matrix),
  Subcategory, Channel, Type, and Configuration Item from business rules.
• Delegate Category and Assignment Group resolution to FieldMappingService.
• Guarantee that no required ServiceNow field is ever sent blank.

Design contracts (MUST NOT be violated)
-----------------------------------------
  ✓  Never calls an LLM — 100% deterministic rule engine.
  ✓  Never hardcodes assignment groups — always resolves via FieldMappingService.
  ✓  Falls back to sensible defaults if enrichment partially fails.
  ✓  Never raises — returns an IncidentMetadata on all paths.
  ✓  Does not create tickets — that is TicketService's responsibility.
  ✓  All business mappings loaded from ConfigurationService (JSON-backed).

Integration placement
---------------------
  Conversation
        │
        ▼
  TicketSummaryService
        │
        ▼
  IncidentEnrichmentService   ← HERE
        │
        ▼
  TicketService
        │
        ▼
  ServiceNow
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from app.core.tracing import trace_span
from app.core.logging_context import correlation_id_ctx

logger = logging.getLogger("it-agent-backend")


# ── ServiceNow Priority Matrix ────────────────────────────────────────────────
# Standard ServiceNow priority matrix: Priority = f(Impact, Urgency)
# Impact:  1=High  2=Medium  3=Low
# Urgency: 1=High  2=Medium  3=Low
# Priority: 1=Critical 2=High 3=Moderate 4=Low
# NOTE: This is pure mathematical logic, not business configuration.
#       It is intentionally kept as code, not moved to JSON.
_PRIORITY_MATRIX: Dict[Tuple[int, int], Tuple[int, str]] = {
    (1, 1): (1, "1 - Critical"),
    (1, 2): (2, "2 - High"),
    (1, 3): (2, "2 - High"),
    (2, 1): (2, "2 - High"),
    (2, 2): (3, "3 - Moderate"),
    (2, 3): (3, "3 - Moderate"),
    (3, 1): (3, "3 - Moderate"),
    (3, 2): (4, "4 - Low"),
    (3, 3): (4, "4 - Low"),
}


# ── Module-level aliases (backward-compat for existing tests & callers) ───────
# These properties are lazy-populated from ConfigurationService on first access
# so that ``from incident_enrichment_service import _CI_MAP`` still works.

def _get_config():
    from app.services.configuration_service import ConfigurationService
    return ConfigurationService.get_instance()


def __getattr__(name: str):
    """
    Module-level __getattr__ — called when a name is not found in module globals.
    Provides backward-compatible access to the config-backed maps.
    """
    if name == "_CI_MAP":
        return _get_config().ci_map_snapshot()
    if name == "_CATEGORY_IMPACT":
        return _get_config().impact_map_snapshot()
    if name == "_CATEGORY_URGENCY":
        return _get_config().urgency_map_snapshot()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


# ── Data Contract ──────────────────────────────────────────────────────────────

@dataclass
class IncidentMetadata:
    """
    Fully-enriched metadata for a ServiceNow incident.
    All required fields are guaranteed to be populated — never blank.
    """
    category:            str
    assignment_group:    str
    impact:              int               # 1=High  2=Medium  3=Low
    urgency:             int               # 1=High  2=Medium  3=Low
    priority:            int               # 1=Critical 2=High 3=Moderate 4=Low
    priority_label:      str               # "2 - High"
    subcategory:         Optional[str]     = None
    channel:             str               = "Virtual Agent"
    incident_type:       str               = "Incident"
    configuration_item:  Optional[str]     = None
    business_service:    Optional[str]     = None
    location:            Optional[str]     = None

    def to_extra_fields(self) -> Dict[str, Any]:
        """
        Return a dict of fields suitable for IncidentCreateRequest.extra_fields.
        Omits None values to avoid sending blank to ServiceNow.
        """
        fields: Dict[str, Any] = {
            "contact_type":   self.channel,
            "u_type":         self.incident_type.lower(),
        }
        if self.subcategory:
            fields["subcategory"] = self.subcategory
        if self.configuration_item:
            fields["cmdb_ci"] = self.configuration_item
        if self.business_service:
            fields["business_service"] = self.business_service
        if self.location:
            fields["location"] = self.location
        return fields


# ── Core Rules Engine ──────────────────────────────────────────────────────────

class _Rules:
    """Pure-function deterministic rules engine. No LLM calls. No I/O."""

    @staticmethod
    def normalize_category(raw: str) -> str:
        """Return a lowercase, stripped category key for map lookups."""
        return raw.lower().strip() if raw else "general"

    @staticmethod
    def derive_subcategory(category_key: str, subcategory_hint: Optional[str] = None) -> Optional[str]:
        """
        Derive subcategory using ServiceNowChoiceResolver as sole source of truth.
        Validates parent-child category hierarchy (dependent_value).
        """
        from app.services.servicenow_choice_resolver import ServiceNowChoiceResolver
        from app.services.configuration_service import ConfigurationService

        config   = ConfigurationService.get_instance()
        resolver = ServiceNowChoiceResolver.get_instance()
        hint     = (subcategory_hint or category_key).lower().strip()

        parent_cat = (
            config.get_parent_category(hint)
            or config.get_parent_category(category_key)
            or category_key
        ).lower().strip()

        resolved = resolver.resolve_subcategory(parent_cat, hint)

        # 1. Strict hierarchy validation: verify subcategory belongs to parent_cat
        if resolved:
            is_valid_hierarchy = any(
                c.get("element") == "subcategory"
                and c.get("value", "").lower() == resolved.lower()
                and c.get("dependent_value", "").lower() == parent_cat
                for c in resolver.choices
            )
            if is_valid_hierarchy:
                return resolved

        # 2. Category-aware default lookup when exact hint did not validate
        cat_subcats = [
            c.get("value")
            for c in resolver.choices
            if c.get("element") == "subcategory"
            and c.get("dependent_value", "").lower() == parent_cat
        ]
        if cat_subcats:
            for preferred in ("Other", "General", "Software Crash / Error", "Laptop / PC", "Password Reset"):
                for sc_val in cat_subcats:
                    if sc_val and sc_val.lower() == preferred.lower():
                        return sc_val
            return cat_subcats[0]

        logger.warning(
            "[IncidentEnrichmentService._Rules.derive_subcategory]: "
            "No valid subcategory hierarchy found for category='%s', hint='%s'",
            parent_cat, hint
        )
        return None

    @staticmethod
    def derive_configuration_item(category_key: str) -> Optional[str]:
        from app.services.configuration_service import ConfigurationService
        return ConfigurationService.get_instance().get_ci(category_key)

    @staticmethod
    def derive_impact(
        category_key: str,
        troubleshooting_state: Optional[Any] = None,
    ) -> int:
        """
        Derive impact (1=High, 2=Medium, 3=Low) from category.
        Future: inspect TroubleshootingState for multi-user signals.
        """
        from app.services.configuration_service import ConfigurationService
        return ConfigurationService.get_instance().get_impact(category_key)

    @staticmethod
    def derive_urgency(
        category_key: str,
        troubleshooting_state: Optional[Any] = None,
    ) -> int:
        """
        Derive urgency (1=High, 2=Medium, 3=Low) from category.
        Escalates urgency if fully unresolved and user could not work at all.
        """
        from app.services.configuration_service import ConfigurationService
        base = ConfigurationService.get_instance().get_urgency(category_key)
        # Escalate urgency if fully unresolved and user couldn't work at all
        if troubleshooting_state:
            res = getattr(troubleshooting_state, "resolution_status", None)
            res_str = res.value if hasattr(res, "value") else str(res or "")
            if res_str.upper() in ("UNRESOLVED", "ESCALATED") and base > 1:
                base = min(base, 2)  # never worse than Medium for unresolved
        return base

    @staticmethod
    def derive_priority(impact: int, urgency: int) -> Tuple[int, str]:
        """Calculate ServiceNow priority from the standard Impact × Urgency matrix."""
        return _PRIORITY_MATRIX.get((impact, urgency), (3, "3 - Moderate"))


# ── Main Service Class ──────────────────────────────────────────────────────────

class IncidentEnrichmentService:
    """
    Enterprise ServiceNow Incident Enrichment Service.

    Usage:
        service = IncidentEnrichmentService()
        metadata = service.enrich(
            category="VPN",
            troubleshooting_state=state,
            classification=classification,
            ticket_summary=summary,
            assignment_group="IT Support",
            caller_id="john.doe",
        )

    The returned IncidentMetadata is ready to be consumed by TicketService.
    All business mappings are loaded from ConfigurationService (JSON-backed).
    """

    def __init__(
        self,
        field_mapping_service: Optional[Any] = None,
    ) -> None:
        self._field_mapper = field_mapping_service

    def _get_field_mapper(self) -> Optional[Any]:
        if self._field_mapper:
            return self._field_mapper
        try:
            from app.services.field_mapping_service import FieldMappingService
            return FieldMappingService(auto_load=True)
        except Exception as exc:
            logger.warning("[IncidentEnrichmentService]: Could not load FieldMappingService: %s", exc)
            return None

    def enrich(
        self,
        category: str,
        assignment_group: str                   = "IT Support",
        troubleshooting_state: Optional[Any]    = None,
        classification: Optional[Any]           = None,
        ticket_summary: Optional[Any]           = None,
        caller_id: Optional[str]                = None,
        location: Optional[str]                 = None,
    ) -> IncidentMetadata:
        """
        Produce a fully-populated IncidentMetadata from deterministic business rules.

        Never raises — on any partial failure falls back to sensible defaults so
        ticket creation is never blocked.
        """
        logger.info(
            ">>> ENTRY [IncidentEnrichmentService.enrich]: category=%s, assignment_group=%s",
            category, assignment_group,
        )

        with trace_span(
            name="enrichment",
            attributes={
                "provider": "none",
                "category": category,
                "correlation_id": correlation_id_ctx.get() or "",
            },
        ):
            try:
                metadata = self._enrich_internal(
                    category=category,
                    assignment_group=assignment_group,
                    troubleshooting_state=troubleshooting_state,
                    classification=classification,
                    ticket_summary=ticket_summary,
                    caller_id=caller_id,
                    location=location,
                )
            except Exception as exc:
                logger.error(
                    "[IncidentEnrichmentService.enrich]: Enrichment failed (%s: %s) — using safe defaults.",
                    type(exc).__name__, exc,
                )
                metadata = self._build_safe_defaults(category=category, assignment_group=assignment_group)

        logger.info(
            "<<< EXIT [IncidentEnrichmentService.enrich]: category=%s, subcategory=%s, impact=%d, "
            "urgency=%d, priority=%d (%s), assignment_group=%s, ci=%s",
            metadata.category,
            metadata.subcategory,
            metadata.impact,
            metadata.urgency,
            metadata.priority,
            metadata.priority_label,
            metadata.assignment_group,
            metadata.configuration_item,
        )
        return metadata

    def _enrich_internal(
        self,
        category: str,
        assignment_group: str,
        troubleshooting_state: Optional[Any],
        classification: Optional[Any],
        ticket_summary: Optional[Any],
        caller_id: Optional[str],
        location: Optional[str],
    ) -> IncidentMetadata:
        """Core enrichment — may raise, caught by enrich()."""
        from app.services.configuration_service import ConfigurationService
        config = ConfigurationService.get_instance()

        # Resolve best category string
        cat_str = self._resolve_category(category, classification)
        cat_key = _Rules.normalize_category(cat_str)

        # Subcategory — via ServiceNowChoiceResolver (single source of truth)
        subcategory = self._resolve_subcategory(cat_key, classification)

        # Assignment Group — via FieldMappingService (best-effort)
        resolved_group = self._resolve_assignment_group(
            assignment_group=assignment_group,
            cat_str=cat_str,
            cat_key=cat_key,
        )

        # Impact & Urgency — via ConfigurationService
        impact  = _Rules.derive_impact(cat_key, troubleshooting_state)
        urgency = _Rules.derive_urgency(cat_key, troubleshooting_state)

        # Priority — ServiceNow matrix
        priority_int, priority_label = _Rules.derive_priority(impact, urgency)

        # Configuration Item — via ConfigurationService
        ci = _Rules.derive_configuration_item(cat_key)

        # Channel / Type — via ConfigurationService
        channel = config.get_contact_type()
        if classification and getattr(classification, "u_type", None):
            incident_type = config.get_servicenow_type(classification.u_type)
        else:
            incident_type = config.get_incident_type()

        # Business Service (future-ready, None for now)
        business_service: Optional[str] = None

        return IncidentMetadata(
            category=cat_str,
            subcategory=subcategory,
            assignment_group=resolved_group,
            impact=impact,
            urgency=urgency,
            priority=priority_int,
            priority_label=priority_label,
            channel=channel,
            incident_type=incident_type,
            configuration_item=ci,
            business_service=business_service,
            location=location,
        )

    def _resolve_category(
        self,
        raw_category: str,
        classification: Optional[Any],
    ) -> str:
        """Pick best category string from available inputs and map via ConfigurationService."""
        from app.services.configuration_service import ConfigurationService
        config = ConfigurationService.get_instance()
        if classification and getattr(classification, "category", None):
            cat = str(classification.category).strip()
            return config.get_mapped_category(cat)
        raw = (raw_category or "General").strip()
        return config.get_mapped_category(raw)

    def _resolve_subcategory(
        self,
        cat_key: str,
        classification: Optional[Any],
    ) -> Optional[str]:
        """Derive subcategory; use classification.subcategory when available."""
        # Prefer explicitly set classification subcategory if present
        if classification and getattr(classification, "subcategory", None):
            sub = str(classification.subcategory).strip()
            if sub:
                from app.services.configuration_service import ConfigurationService
                return ConfigurationService.get_instance().get_mapped_subcategory(sub)

        # Check FieldMappingService for valid subcategories
        mapper = self._get_field_mapper()
        if mapper:
            try:
                subcat_map_key = _Rules.derive_subcategory(cat_key)
                subcats = mapper.get_subcategories(cat_key)
                if subcats:
                    sub_val = subcats[0]["value"]
                    from app.services.configuration_service import ConfigurationService
                    return ConfigurationService.get_instance().get_mapped_subcategory(sub_val)
                from app.services.configuration_service import ConfigurationService
                return ConfigurationService.get_instance().get_mapped_subcategory(subcat_map_key)
            except Exception:
                pass

        raw_sub = _Rules.derive_subcategory(cat_key)
        from app.services.configuration_service import ConfigurationService
        return ConfigurationService.get_instance().get_mapped_subcategory(raw_sub)

    def _resolve_assignment_group(
        self,
        assignment_group: str,
        cat_str: str,
        cat_key: str,
    ) -> str:
        """Resolve assignment group via ConfigurationService first, then FieldMappingService."""
        from app.services.configuration_service import ConfigurationService
        config = ConfigurationService.get_instance()
        config_group = config.get_assignment_group_for_category(cat_str) or config.get_assignment_group_for_category(cat_key)
        if config_group:
            return config_group

        mapper = self._get_field_mapper()
        if mapper:
            try:
                resolved = mapper.build_servicenow_fields(
                    contact_type="chat",
                    category=cat_str,
                    assignment_group=assignment_group,
                )
                grp = resolved.get("assignment_group", "")
                if grp:
                    return grp
            except Exception as exc:
                logger.warning(
                    "[IncidentEnrichmentService]: FieldMappingService could not resolve assignment_group: %s",
                    exc,
                )

        return assignment_group or "IT Support"

    @staticmethod
    def _build_safe_defaults(category: str, assignment_group: str) -> IncidentMetadata:
        """Fallback when enrichment itself fails — returns minimal safe values."""
        from app.services.configuration_service import ConfigurationService
        config  = ConfigurationService.get_instance()
        cat_key = _Rules.normalize_category(category)
        return IncidentMetadata(
            category=category or "General",
            subcategory=_Rules.derive_subcategory(cat_key),
            assignment_group=assignment_group or "IT Support",
            impact=3,
            urgency=3,
            priority=4,
            priority_label="4 - Low",
            channel=config.get_contact_type(),
            incident_type=config.get_incident_type(),
            configuration_item=_Rules.derive_configuration_item(cat_key),
        )


# ── Convenience factory ────────────────────────────────────────────────────────

def enrich_incident(
    category: str,
    assignment_group: str                   = "IT Support",
    troubleshooting_state: Optional[Any]    = None,
    classification: Optional[Any]           = None,
    ticket_summary: Optional[Any]           = None,
    caller_id: Optional[str]                = None,
    location: Optional[str]                 = None,
    field_mapping_service: Optional[Any]    = None,
) -> IncidentMetadata:
    """Module-level convenience entry point for IncidentEnrichmentService."""
    service = IncidentEnrichmentService(field_mapping_service=field_mapping_service)
    return service.enrich(
        category=category,
        assignment_group=assignment_group,
        troubleshooting_state=troubleshooting_state,
        classification=classification,
        ticket_summary=ticket_summary,
        caller_id=caller_id,
        location=location,
    )
