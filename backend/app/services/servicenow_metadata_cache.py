"""
servicenow_metadata_cache.py
─────────────────────────────────────────────────────────────────────────────
Production-grade, thread-safe in-memory metadata cache for ServiceNow choices,
assignment groups, and CMDB Configuration Items.

Features:
- Configurable TTL refresh interval (SERVICENOW_METADATA_CACHE_TTL_SECONDS).
- Non-blocking resilience: API fetch failures gracefully fall back to last cached
  data or local configuration (incident_config.json, FieldMappingService).
- Provides metadata statistics for observability (/metadata/health).
"""

import logging
import os
import time
from datetime import datetime, timezone
from threading import RLock
from typing import Dict, List, Any, Optional

from app.services.configuration_service import ConfigurationService
from app.services.servicenow_client import ServiceNowClient

logger = logging.getLogger("it-agent-backend")


class ServiceNowMetadataCache:
    """Thread-safe singleton cache for ServiceNow metadata with non-blocking resilience."""

    _instance: Optional["ServiceNowMetadataCache"] = None
    _lock: RLock = RLock()

    def __init__(self) -> None:
        self.ttl_seconds: int = int(os.getenv("SERVICENOW_METADATA_CACHE_TTL_SECONDS", "3600"))
        self.last_refresh_time: Optional[float] = None
        self.last_refresh_iso: Optional[str] = None
        self.status: str = "uninitialized"
        self.source: str = "local_config"

        # Cached structures
        self._categories: List[Dict[str, Any]] = []
        self._subcategories: List[Dict[str, Any]] = []
        self._assignment_groups: List[Dict[str, Any]] = []
        self._cmdb_cis: List[Dict[str, Any]] = []

    @classmethod
    def get_instance(cls) -> "ServiceNowMetadataCache":
        """Get or create singleton instance of ServiceNowMetadataCache."""
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    def is_expired(self) -> bool:
        """Check if cache has exceeded TTL."""
        if self.last_refresh_time is None:
            return True
        return (time.time() - self.last_refresh_time) >= self.ttl_seconds

    def sync(self, client: Optional[ServiceNowClient] = None, force: bool = False) -> bool:
        """
        Synchronize metadata from ServiceNow API or fallback to local configuration.
        Non-blocking: if network/API fails, uses last cached data or local config and emits warning.
        """
        with self._lock:
            if not force and not self.is_expired():
                logger.debug("[ServiceNowMetadataCache.sync]: Cache is fresh (age=%ds). Skipping sync.", self.get_age_seconds())
                return True

            logger.info(">>> ENTRY [ServiceNowMetadataCache.sync]: Synchronizing ServiceNow metadata...")
            sn_client = client or ServiceNowClient()
            api_success = False

            if sn_client.is_configured() and not sn_client.use_mock:
                try:
                    base_url = sn_client.instance.rstrip("/")

                    # 1. Fetch sys_choice
                    sys_choice_url = f"{base_url}/api/now/table/sys_choice"
                    choice_res = sn_client._execute_request(
                        method="GET",
                        url=sys_choice_url,
                        params={"sysparm_query": "name=incident^elementINcategory,subcategory", "sysparm_limit": "500"},
                    )
                    raw_choices = choice_res.json().get("result", [])

                    cats = []
                    subcats = []
                    for c in raw_choices:
                        elem = c.get("element")
                        lbl = c.get("label")
                        val = c.get("value")
                        dep = c.get("dependent_value")
                        if elem == "category" and val:
                            cats.append({"label": lbl or val, "value": val})
                        elif elem == "subcategory" and val:
                            subcats.append({"label": lbl or val, "value": val, "dependent_value": dep or ""})

                    # 2. Fetch sys_user_group
                    groups_url = f"{base_url}/api/now/table/sys_user_group"
                    group_res = sn_client._execute_request(
                        method="GET",
                        url=groups_url,
                        params={"sysparm_limit": "500", "sysparm_fields": "sys_id,name,email"},
                    )
                    raw_groups = group_res.json().get("result", [])
                    groups = [{"name": g.get("name"), "sys_id": g.get("sys_id")} for g in raw_groups if g.get("name")]

                    # 3. Fetch cmdb_ci
                    ci_url = f"{base_url}/api/now/table/cmdb_ci"
                    ci_res = sn_client._execute_request(
                        method="GET",
                        url=ci_url,
                        params={"sysparm_limit": "500", "sysparm_fields": "sys_id,name,sys_class_name"},
                    )
                    raw_cis = ci_res.json().get("result", [])
                    cis = [{"name": c.get("name"), "sys_id": c.get("sys_id"), "class": c.get("sys_class_name")} for c in raw_cis if c.get("name")]

                    if cats or groups:
                        self._categories = cats
                        self._subcategories = subcats
                        self._assignment_groups = groups
                        self._cmdb_cis = cis
                        self.source = "live_servicenow"
                        api_success = True
                        logger.info("✓ [ServiceNowMetadataCache.sync]: Synchronized from Live ServiceNow (%d cats, %d subcats, %d groups, %d CIs)", len(cats), len(subcats), len(groups), len(cis))
                except Exception as exc:
                    logger.warning("WARNING [ServiceNowMetadataCache.sync]: Live ServiceNow fetch failed (%s). Falling back to local configuration.", exc)

            # Fallback to local configuration if API fetch was skipped or failed
            if not api_success:
                self._populate_from_local_config()

            self.last_refresh_time = time.time()
            self.last_refresh_iso = datetime.now(timezone.utc).isoformat()
            self.status = "healthy"
            return True

    def _populate_from_local_config(self) -> None:
        """Populate metadata structures from FieldMappingService and ConfigurationService."""
        logger.info("[ServiceNowMetadataCache._populate_from_local_config]: Populating from local config & excel mappings...")
        cfg = ConfigurationService.get_instance()

        # Load valid categories
        valid_cat_list = cfg.get_valid_categories()
        self._categories = [{"label": cat, "value": cat} for cat in valid_cat_list]

        # Load subcategories from FieldMappingService if available
        try:
            from app.services.field_mapping_service import FieldMappingService
            fms = FieldMappingService(auto_load=True)
            self._subcategories = [
                {"label": s.get("label"), "value": s.get("value"), "dependent_value": s.get("dependent_value", "")}
                for s in fms._subcategories
            ]
            self._assignment_groups = [
                {"name": g.get("label") or g.get("name") or g.get("value"), "sys_id": g.get("value")}
                for g in fms._assignment_groups
            ]
        except Exception as exc:
            logger.warning("[ServiceNowMetadataCache]: FieldMappingService load notice: %s", exc)
            self._subcategories = []
            self._assignment_groups = []

        # Supplement assignment groups from ConfigurationService map
        group_map = getattr(cfg, "_assignment_group_map", {})
        known_group_names = {g["name"].lower() for g in self._assignment_groups if g.get("name")}
        for grp_name in group_map.values():
            if grp_name and grp_name.lower() not in known_group_names:
                self._assignment_groups.append({"name": grp_name, "sys_id": ""})
                known_group_names.add(grp_name.lower())

        # Sample CMDB CIs from ci_map
        ci_map = getattr(cfg, "_ci_map", {})
        known_cis = {c["name"].lower() for c in self._cmdb_cis if c.get("name")}
        for ci_name in ci_map.values():
            if ci_name and ci_name.lower() not in known_cis:
                self._cmdb_cis.append({"name": ci_name, "sys_id": ""})
                known_cis.add(ci_name.lower())

        self.source = "local_configuration"
        logger.info("✓ [ServiceNowMetadataCache]: Loaded local metadata (%d cats, %d subcats, %d groups, %d CIs)", len(self._categories), len(self._subcategories), len(self._assignment_groups), len(self._cmdb_cis))

    def get_age_seconds(self) -> int:
        """Return cache age in seconds."""
        if self.last_refresh_time is None:
            return -1
        return int(time.time() - self.last_refresh_time)

    def get_categories(self) -> List[Dict[str, Any]]:
        """Return list of cached category dicts."""
        with self._lock:
            return list(self._categories)

    def get_subcategories(self, category: Optional[str] = None) -> List[Dict[str, Any]]:
        """Return list of cached subcategory dicts, optionally filtered by category."""
        with self._lock:
            if not category:
                return list(self._subcategories)
            cat_norm = category.lower().strip()
            return [
                s for s in self._subcategories
                if (s.get("dependent_value") or "").lower().strip() == cat_norm
                or cat_norm in (s.get("dependent_value") or "").lower().strip()
            ]

    def get_assignment_groups(self) -> List[Dict[str, Any]]:
        """Return list of cached assignment group dicts."""
        with self._lock:
            return list(self._assignment_groups)

    def get_cmdb_cis(self) -> List[Dict[str, Any]]:
        """Return list of cached CMDB CI dicts."""
        with self._lock:
            return list(self._cmdb_cis)

    def get_stats(self) -> Dict[str, Any]:
        """Return dictionary of cache stats for observability endpoint."""
        with self._lock:
            return {
                "metadata_status": self.status,
                "source": self.source,
                "last_refresh": self.last_refresh_iso or "never",
                "cache_age_seconds": self.get_age_seconds(),
                "ttl_seconds": self.ttl_seconds,
                "categories": len(self._categories),
                "subcategories": len(self._subcategories),
                "groups": len(self._assignment_groups),
                "cmdb_records": len(self._cmdb_cis),
            }
