"""
test_configuration_service.py
──────────────────────────────────────────────────────────────────────────────
Unit tests for ConfigurationService.

Coverage:
  • Singleton behaviour (same instance returned on repeated calls)
  • Thread-safety (concurrent get_instance() calls yield one instance)
  • JSON loading — incident_config.json present and parseable
  • JSON loading — graceful fallback when file is missing
  • All public getters return correct types and values
  • reset_instance() forces fresh load on next get_instance()
  • Snapshot helpers return dict copies
"""

from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any
from unittest.mock import patch, mock_open, MagicMock

import pytest

from app.services.configuration_service import ConfigurationService


# ── Helpers ───────────────────────────────────────────────────────────────────

def _reset() -> None:
    """Reset the singleton before each test."""
    ConfigurationService.reset_instance()


@pytest.fixture(autouse=True)
def reset_singleton():
    """Ensure a fresh singleton for every test."""
    _reset()
    yield
    _reset()


# ── Singleton & Thread-safety ─────────────────────────────────────────────────

class TestSingleton:
    def test_same_instance_returned(self):
        a = ConfigurationService.get_instance()
        b = ConfigurationService.get_instance()
        assert a is b

    def test_reset_gives_new_instance(self):
        a = ConfigurationService.get_instance()
        ConfigurationService.reset_instance()
        b = ConfigurationService.get_instance()
        assert a is not b

    def test_concurrent_get_instance_returns_same(self):
        results = []
        barrier = threading.Barrier(10)

        def worker():
            barrier.wait()
            results.append(ConfigurationService.get_instance())

        threads = [threading.Thread(target=worker) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(results) == 10
        # All threads must have received the exact same object
        first = results[0]
        assert all(r is first for r in results)


# ── JSON Loading ──────────────────────────────────────────────────────────────

class TestJsonLoading:
    def test_loads_ci_map_from_json(self):
        cfg = ConfigurationService.get_instance()
        # Verify a known entry from incident_config.json
        assert cfg.get_ci("vpn") == "VPN Gateway"
        assert cfg.get_ci("outlook") == "Microsoft Outlook"

    def test_loads_impact_from_json(self):
        cfg = ConfigurationService.get_instance()
        assert cfg.get_impact("sap") == 1
        assert cfg.get_impact("printer") == 3
        assert cfg.get_impact("network") == 1

    def test_loads_urgency_from_json(self):
        cfg = ConfigurationService.get_instance()
        assert cfg.get_urgency("password") == 1
        assert cfg.get_urgency("printer") == 3
        assert cfg.get_urgency("vpn") == 2

    def test_loads_defaults_from_json(self):
        cfg = ConfigurationService.get_instance()
        assert cfg.get_contact_type() == "Virtual Agent"
        assert cfg.get_incident_type() == "Incident"

    def test_loads_intent_category_map(self):
        cfg = ConfigurationService.get_instance()
        assert cfg.get_parent_category("vpn") == "network"
        assert cfg.get_parent_category("outlook") == "microsoft 365"
        assert cfg.get_parent_category("printer") == "printer"

    def test_missing_incident_config_graceful(self, tmp_path, monkeypatch):
        """When incident_config.json is absent, getters return safe defaults."""
        import app.services.configuration_service as mod
        monkeypatch.setattr(mod, "_INCIDENT_CONFIG_FILE", tmp_path / "nonexistent.json")
        monkeypatch.setattr(mod, "_INTENT_CATEGORY_FILE", tmp_path / "nonexistent2.json")

        cfg = ConfigurationService.get_instance()
        # Should return None / defaults, not raise
        assert cfg.get_ci("vpn") is None
        assert cfg.get_impact("vpn") == 3      # default
        assert cfg.get_urgency("vpn") == 3     # default
        assert cfg.get_contact_type() == "Virtual Agent"
        assert cfg.get_incident_type() == "Incident"

    def test_malformed_json_graceful(self, tmp_path, monkeypatch):
        """Malformed JSON must not crash — service degrades gracefully."""
        bad_file = tmp_path / "incident_config.json"
        bad_file.write_text("NOT JSON {{{", encoding="utf-8")

        import app.services.configuration_service as mod
        monkeypatch.setattr(mod, "_INCIDENT_CONFIG_FILE", bad_file)
        monkeypatch.setattr(mod, "_INTENT_CATEGORY_FILE", tmp_path / "missing.json")

        cfg = ConfigurationService.get_instance()
        assert cfg.get_ci("vpn") is None
        assert isinstance(cfg.get_impact("vpn"), int)


# ── Public Getters ────────────────────────────────────────────────────────────

class TestGetters:
    def test_get_ci_known(self):
        cfg = ConfigurationService.get_instance()
        assert cfg.get_ci("vpn")     == "VPN Gateway"
        assert cfg.get_ci("printer") == "Network Printer"
        assert cfg.get_ci("sap")     == "SAP ERP System"

    def test_get_ci_unknown_returns_none(self):
        cfg = ConfigurationService.get_instance()
        assert cfg.get_ci("unknown_xyz") is None

    def test_get_ci_case_insensitive(self):
        cfg = ConfigurationService.get_instance()
        assert cfg.get_ci("VPN")    == cfg.get_ci("vpn")
        assert cfg.get_ci("Printer") == cfg.get_ci("printer")

    def test_get_impact_ranges(self):
        cfg = ConfigurationService.get_instance()
        for key in ("vpn", "network", "sap", "printer", "unknown_xyz"):
            val = cfg.get_impact(key)
            assert val in (1, 2, 3), f"Impact out of range for key={key!r}: {val}"

    def test_get_urgency_ranges(self):
        cfg = ConfigurationService.get_instance()
        for key in ("vpn", "network", "password", "printer", "unknown_xyz"):
            val = cfg.get_urgency(key)
            assert val in (1, 2, 3), f"Urgency out of range for key={key!r}: {val}"

    def test_get_impact_unknown_returns_default(self):
        cfg = ConfigurationService.get_instance()
        assert cfg.get_impact("xyz_unknown") == cfg.get_default_impact()

    def test_get_urgency_unknown_returns_default(self):
        cfg = ConfigurationService.get_instance()
        assert cfg.get_urgency("xyz_unknown") == cfg.get_default_urgency()

    def test_get_contact_type_is_string(self):
        cfg = ConfigurationService.get_instance()
        assert isinstance(cfg.get_contact_type(), str)
        assert cfg.get_contact_type() != ""

    def test_get_incident_type_is_string(self):
        cfg = ConfigurationService.get_instance()
        assert isinstance(cfg.get_incident_type(), str)
        assert cfg.get_incident_type() != ""

    def test_get_default_location_none_or_str(self):
        cfg = ConfigurationService.get_instance()
        loc = cfg.get_default_location()
        assert loc is None or isinstance(loc, str)

    def test_get_default_impact_int(self):
        cfg = ConfigurationService.get_instance()
        assert isinstance(cfg.get_default_impact(), int)
        assert cfg.get_default_impact() in (1, 2, 3)

    def test_get_default_urgency_int(self):
        cfg = ConfigurationService.get_instance()
        assert isinstance(cfg.get_default_urgency(), int)
        assert cfg.get_default_urgency() in (1, 2, 3)

    def test_get_default_priority_int(self):
        cfg = ConfigurationService.get_instance()
        assert isinstance(cfg.get_default_priority(), int)
        assert cfg.get_default_priority() in (1, 2, 3, 4)

    def test_get_parent_category_known(self):
        cfg = ConfigurationService.get_instance()
        assert cfg.get_parent_category("vpn")     == "network"
        assert cfg.get_parent_category("outlook")  == "microsoft 365"
        assert cfg.get_parent_category("laptop")   == "hardware"

    def test_get_parent_category_unknown_returns_none(self):
        cfg = ConfigurationService.get_instance()
        assert cfg.get_parent_category("unknown_xyz") is None

    def test_get_parent_category_case_insensitive(self):
        cfg = ConfigurationService.get_instance()
        assert cfg.get_parent_category("VPN")  == cfg.get_parent_category("vpn")
        assert cfg.get_parent_category("Teams") == cfg.get_parent_category("teams")

    def test_get_parent_category_empty_string(self):
        cfg = ConfigurationService.get_instance()
        assert cfg.get_parent_category("") is None

    def test_get_ci_empty_string(self):
        cfg = ConfigurationService.get_instance()
        assert cfg.get_ci("") is None

    def test_get_impact_empty_string(self):
        cfg = ConfigurationService.get_instance()
        # Empty string should fall back to default
        assert cfg.get_impact("") == cfg.get_default_impact()


# ── Snapshot Helpers ──────────────────────────────────────────────────────────

class TestSnapshots:
    def test_ci_map_snapshot_is_dict(self):
        cfg = ConfigurationService.get_instance()
        snap = cfg.ci_map_snapshot()
        assert isinstance(snap, dict)
        assert len(snap) > 0

    def test_ci_map_snapshot_is_copy(self):
        cfg = ConfigurationService.get_instance()
        snap1 = cfg.ci_map_snapshot()
        snap1["injected"] = "SHOULD NOT APPEAR"
        snap2 = cfg.ci_map_snapshot()
        assert "injected" not in snap2

    def test_impact_map_snapshot_is_dict(self):
        cfg = ConfigurationService.get_instance()
        snap = cfg.impact_map_snapshot()
        assert isinstance(snap, dict)
        assert "vpn" in snap

    def test_urgency_map_snapshot_is_dict(self):
        cfg = ConfigurationService.get_instance()
        snap = cfg.urgency_map_snapshot()
        assert isinstance(snap, dict)
        assert "password" in snap

    def test_intent_category_snapshot_is_dict(self):
        cfg = ConfigurationService.get_instance()
        snap = cfg.intent_category_snapshot()
        assert isinstance(snap, dict)
        assert "vpn" in snap


# ── Module-level Aliases in incident_enrichment_service ──────────────────────

class TestModuleLevelAliases:
    """
    Ensure that the backward-compat __getattr__ in incident_enrichment_service
    still exposes _CI_MAP, _CATEGORY_IMPACT, _CATEGORY_URGENCY as dict-like objects.
    """

    def test_ci_map_importable(self):
        from app.services.incident_enrichment_service import _CI_MAP
        assert isinstance(_CI_MAP, dict)
        assert "vpn" in _CI_MAP

    def test_category_impact_importable(self):
        from app.services.incident_enrichment_service import _CATEGORY_IMPACT
        assert isinstance(_CATEGORY_IMPACT, dict)
        assert "vpn" in _CATEGORY_IMPACT

    def test_category_urgency_importable(self):
        from app.services.incident_enrichment_service import _CATEGORY_URGENCY
        assert isinstance(_CATEGORY_URGENCY, dict)
        assert "password" in _CATEGORY_URGENCY

    def test_priority_matrix_still_present(self):
        from app.services.incident_enrichment_service import _PRIORITY_MATRIX
        assert (1, 1) in _PRIORITY_MATRIX
        assert len(_PRIORITY_MATRIX) == 9


# ── Phase 6 — New ConfigurationService Getters ───────────────────────────────

class TestPhase6Getters:
    """
    Tests for the three new Phase 6 getters added to ConfigurationService:
      • get_valid_categories()         — loads from incident_config.json["valid_categories"]
      • get_clarification_threshold()  — loads from incident_config.json["clarification_threshold"]
      • get_assignment_group_for_category() — loads from incident_config.json["assignment_group_map"]
      • category_snapshot()            — returns a list copy of valid_categories
    """

    def test_get_valid_categories_returns_set(self):
        """get_valid_categories() always returns a set."""
        cfg = ConfigurationService.get_instance()
        cats = cfg.get_valid_categories()
        assert isinstance(cats, set)

    def test_get_valid_categories_non_empty(self):
        """valid_categories must not be empty (at least the legacy domains must be present)."""
        cfg = ConfigurationService.get_instance()
        cats = cfg.get_valid_categories()
        assert len(cats) >= 9, f"Expected >= 9 valid categories, got: {cats}"

    def test_get_valid_categories_core_domains(self):
        """Core domains from incident_config.json are present in valid_categories."""
        cfg = ConfigurationService.get_instance()
        cats = cfg.get_valid_categories()
        for expected in ("network", "Hardware", "Microsoft 365", "Software", "Printer", "BSID Domain", "E-mail"):
            assert expected in cats, f"Core category '{expected}' missing from valid_categories: {cats}"

    def test_get_valid_categories_phase6_domains(self):
        """Phase 6 new domains Security and Mobile Devices are present."""
        cfg = ConfigurationService.get_instance()
        cats = cfg.get_valid_categories()
        assert "Security" in cats, f"'Security' not in valid_categories: {cats}"
        assert "Mobile Devices" in cats, f"'Mobile Devices' not in valid_categories: {cats}"

    def test_get_valid_categories_returns_copy(self):
        """Mutating the returned set must not affect the internal state."""
        cfg = ConfigurationService.get_instance()
        cats1 = cfg.get_valid_categories()
        cats1.add("INJECTED_VALUE_XYZ")
        cats2 = cfg.get_valid_categories()
        assert "INJECTED_VALUE_XYZ" not in cats2

    def test_get_clarification_threshold_is_float(self):
        """get_clarification_threshold() returns a float."""
        cfg = ConfigurationService.get_instance()
        threshold = cfg.get_clarification_threshold()
        assert isinstance(threshold, float)

    def test_get_clarification_threshold_in_range(self):
        """Threshold must be between 0.0 and 1.0 inclusive."""
        cfg = ConfigurationService.get_instance()
        threshold = cfg.get_clarification_threshold()
        assert 0.0 <= threshold <= 1.0

    def test_get_clarification_threshold_default_value(self):
        """Default threshold must be 0.70."""
        cfg = ConfigurationService.get_instance()
        assert cfg.get_clarification_threshold() == pytest.approx(0.70, abs=0.01)

    def test_get_clarification_threshold_missing_config(self, tmp_path, monkeypatch):
        """When config file is absent, threshold falls back to 0.70."""
        import app.services.configuration_service as mod
        monkeypatch.setattr(mod, "_INCIDENT_CONFIG_FILE", tmp_path / "nonexistent.json")
        monkeypatch.setattr(mod, "_INTENT_CATEGORY_FILE", tmp_path / "nonexistent2.json")

        cfg = ConfigurationService.get_instance()
        assert cfg.get_clarification_threshold() == pytest.approx(0.70, abs=0.01)

    def test_get_assignment_group_network(self):
        """Network category maps to 'Network Team'."""
        cfg = ConfigurationService.get_instance()
        assert cfg.get_assignment_group_for_category("network") == "Network Team"

    def test_get_assignment_group_hardware(self):
        """Hardware category maps to 'Hardware Team'."""
        cfg = ConfigurationService.get_instance()
        assert cfg.get_assignment_group_for_category("hardware") == "Hardware Team"

    def test_get_assignment_group_security(self):
        """Security category maps to 'Security Team'."""
        cfg = ConfigurationService.get_instance()
        assert cfg.get_assignment_group_for_category("security") == "Security Team"

    def test_get_assignment_group_mobile(self):
        """Mobile Devices category maps to 'Mobile Team'."""
        cfg = ConfigurationService.get_instance()
        assert cfg.get_assignment_group_for_category("mobile devices") == "Mobile Team"

    def test_get_assignment_group_case_insensitive(self):
        """Assignment group lookup is case-insensitive."""
        cfg = ConfigurationService.get_instance()
        lower = cfg.get_assignment_group_for_category("network")
        upper = cfg.get_assignment_group_for_category("NETWORK")
        mixed = cfg.get_assignment_group_for_category("Network")
        assert lower == upper == mixed == "Network Team"

    def test_get_assignment_group_unknown_returns_none(self):
        """Unknown category key returns None (caller applies own fallback)."""
        cfg = ConfigurationService.get_instance()
        result = cfg.get_assignment_group_for_category("unknown_xyz_domain")
        assert result is None

    def test_get_assignment_group_empty_string_returns_none(self):
        """Empty string returns None."""
        cfg = ConfigurationService.get_instance()
        result = cfg.get_assignment_group_for_category("")
        assert result is None

    def test_category_snapshot_is_list(self):
        """category_snapshot() returns a list."""
        cfg = ConfigurationService.get_instance()
        snap = cfg.category_snapshot()
        assert isinstance(snap, list)

    def test_category_snapshot_non_empty(self):
        """category_snapshot() contains at least the core categories."""
        cfg = ConfigurationService.get_instance()
        snap = cfg.category_snapshot()
        assert len(snap) >= 9

    def test_category_snapshot_is_copy(self):
        """Mutating category_snapshot() must not affect internal state."""
        cfg = ConfigurationService.get_instance()
        snap1 = cfg.category_snapshot()
        snap1.append("INJECTED_CATEGORY")
        snap2 = cfg.category_snapshot()
        assert "INJECTED_CATEGORY" not in snap2

    def test_missing_config_valid_categories_empty(self, tmp_path, monkeypatch):
        """When config is absent, get_valid_categories() returns an empty set (safe)."""
        import app.services.configuration_service as mod
        monkeypatch.setattr(mod, "_INCIDENT_CONFIG_FILE", tmp_path / "nonexistent.json")
        monkeypatch.setattr(mod, "_INTENT_CATEGORY_FILE", tmp_path / "nonexistent2.json")

        cfg = ConfigurationService.get_instance()
        cats = cfg.get_valid_categories()
        assert isinstance(cats, set)
        # Empty set is acceptable — ClassificationService falls back to FieldMappingService

    def test_missing_config_assignment_group_returns_none(self, tmp_path, monkeypatch):
        """When config is absent, get_assignment_group_for_category() returns None."""
        import app.services.configuration_service as mod
        monkeypatch.setattr(mod, "_INCIDENT_CONFIG_FILE", tmp_path / "nonexistent.json")
        monkeypatch.setattr(mod, "_INTENT_CATEGORY_FILE", tmp_path / "nonexistent2.json")

        cfg = ConfigurationService.get_instance()
        assert cfg.get_assignment_group_for_category("network") is None
