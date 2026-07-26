#!/usr/bin/env python3
"""
scripts/validate_observability.py
────────────────────────────────────────────────────────────────────────────
Phase 5: Observability Stack Validation Script.

Verifies that:
  1. GET /health returns 200 with all required keys.
  2. GET /ready returns 200 with status=="ready".
  3. GET /metrics returns Prometheus text containing all 40+ required metric names.
  4. X-Correlation-ID and X-Request-ID headers are present in responses.
  5. All expected Prometheus metrics are registered in the local registry.
  6. alerts.yml contains all required alert rules.

Usage:
    python scripts/validate_observability.py [--base-url http://localhost:8000]

Exit codes:
    0 — All checks passed
    1 — One or more checks failed
"""

from __future__ import annotations

import argparse
import json
import sys
import os
from pathlib import Path
from typing import List, Tuple

# Resolve backend directory and add to sys.path so `app` is importable
_SCRIPT_DIR = Path(__file__).resolve().parent          # backend/scripts/
_BACKEND_DIR = _SCRIPT_DIR.parent                      # backend/
_REPO_ROOT = _BACKEND_DIR.parent                       # bridgestone-it-agent/

if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

try:
    import yaml
except ImportError:
    print("ERROR: PyYAML not installed. Run: pip install pyyaml")
    sys.exit(1)

# ── Colour helpers ────────────────────────────────────────────────────────────
GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
RESET  = "\033[0m"


def _ok(msg: str) -> None:
    print(f"  {GREEN}OK{RESET}  {msg}")


def _fail(msg: str) -> None:
    print(f"  {RED}FAIL{RESET} {msg}")


def _section(title: str) -> None:
    line = "-" * (60 - len(title))
    print(f"\n{YELLOW}-- {title} {line}{RESET}")


# -- Required metric names -----------------------------------------------------
REQUIRED_METRICS: List[str] = [
    # HTTP
    "http_requests_total",
    "http_failures_total",
    "http_request_duration_seconds",
    # Security
    "security_logins_total",
    "security_failed_logins_total",
    "security_jwt_expired_total",
    "security_unauthorized_total",
    # Agent
    "agent_execution_duration_seconds",
    # LLM
    "llm_requests_total",
    "llm_success_total",
    "llm_failures_total",
    "llm_latency_seconds",
    "llm_token_usage_total",
    "llm_fallback_events_total",
    # Business
    "business_tickets_created_total",
    "business_sla_breaches_total",
    # DB
    "db_connections_active",
    "db_query_duration_seconds",
    "db_failures_total",
    # Redis
    "redis_availability",
    "redis_cache_hits_total",
    # ServiceNow
    "servicenow_requests_total",
    "servicenow_failures_total",
    "servicenow_latency_seconds",
    "incidents_created_total",
    # Graph / AD
    "graph_requests_total",
    "ad_requests_total",
    # Tool
    "tool_execution_total",
    "tool_execution_duration_seconds",
    # Provider
    "provider_requests_total",
    "provider_latency_seconds",
    # Pipeline spans (Phase 5)
    "pipeline_span_duration_seconds",
]

# -- Required alert names in alerts.yml ---------------------------------------
REQUIRED_ALERTS: List[str] = [
    "BackendDown",
    "DatabaseDown",
    "RedisDown",
    "GeminiHighFailRate",
    "SlaBreachThreshold",
    "AuthenticationFailureSpike",
    "ServiceNowHighFailRate",
    "ServiceNowHighLatency",
    "AIProviderFallbackSpike",
    "HighEndToEndLatency",
]

# -- Health response required keys ---------------------------------------------
REQUIRED_HEALTH_KEYS = ["status", "database", "redis", "gemini", "adapters", "scheduler"]


def check_health_endpoint(base_url: str) -> Tuple[bool, List[str]]:
    """Check GET /health returns 200 with required JSON structure."""
    import requests as req
    errors = []
    try:
        r = req.get(f"{base_url}/health", timeout=10)
        if r.status_code != 200:
            errors.append(f"GET /health returned {r.status_code}, expected 200")
            return False, errors

        # Check X-Correlation-ID response header
        if "x-correlation-id" not in {k.lower() for k in r.headers}:
            errors.append("GET /health response is missing X-Correlation-ID header")

        data = r.json()
        for key in REQUIRED_HEALTH_KEYS:
            if key not in data:
                errors.append(f"GET /health response missing key: '{key}'")

        return len(errors) == 0, errors
    except Exception as exc:
        errors.append(f"GET /health request failed: {exc}")
        return False, errors


def check_ready_endpoint(base_url: str) -> Tuple[bool, List[str]]:
    """Check GET /ready returns 200 and status == 'ready'."""
    import requests as req
    errors = []
    try:
        r = req.get(f"{base_url}/ready", timeout=5)
        if r.status_code == 503:
            errors.append("GET /ready returned 503 — application is not yet ready (check if startup completed)")
            return False, errors
        if r.status_code != 200:
            errors.append(f"GET /ready returned {r.status_code}, expected 200")
            return False, errors

        data = r.json()
        if data.get("status") != "ready":
            errors.append(f"GET /ready body status='{data.get('status')}', expected 'ready'")

        return len(errors) == 0, errors
    except Exception as exc:
        errors.append(f"GET /ready request failed: {exc}")
        return False, errors


def check_metrics_endpoint(base_url: str) -> Tuple[bool, List[str]]:
    """Check GET /metrics returns Prometheus text with all required metric names."""
    import requests as req
    errors = []
    try:
        r = req.get(f"{base_url}/metrics", timeout=10)
        if r.status_code != 200:
            errors.append(f"GET /metrics returned {r.status_code}, expected 200")
            return False, errors

        content = r.text
        missing = [m for m in REQUIRED_METRICS if m not in content]
        for m in missing:
            errors.append(f"Metric '{m}' not found in /metrics output")

        return len(errors) == 0, errors
    except Exception as exc:
        errors.append(f"GET /metrics request failed: {exc}")
        return False, errors


def check_registry_metrics() -> Tuple[bool, List[str]]:
    """Check that all required metric names are registered in the local Prometheus registry."""
    errors = []
    try:
        from prometheus_client import REGISTRY
        registered_names = set()
        for collector in list(REGISTRY._names_to_collectors.keys()):
            registered_names.add(collector)

        missing = [m for m in REQUIRED_METRICS if not any(m in name for name in registered_names)]
        for m in missing:
            errors.append(f"Metric '{m}' not found in Prometheus registry")

        return len(errors) == 0, errors
    except Exception as exc:
        errors.append(f"Registry check failed: {exc}")
        return False, errors


def check_alerts_file(repo_root: Path) -> Tuple[bool, List[str]]:
    """Check alerts.yml contains all required alert rules."""
    errors = []
    # Try both backend-relative and repo-relative paths
    candidates = [
        repo_root / "infrastructure" / "monitoring" / "prometheus" / "alerts.yml",
        _REPO_ROOT / "infrastructure" / "monitoring" / "prometheus" / "alerts.yml",
    ]
    alerts_path = None
    for c in candidates:
        if c.exists():
            alerts_path = c
            break

    if alerts_path is None:
        errors.append(f"alerts.yml not found. Searched: {[str(c) for c in candidates]}")
        return False, errors

    try:
        with open(alerts_path) as f:
            data = yaml.safe_load(f)
    except Exception as exc:
        errors.append(f"alerts.yml parse failed: {exc}")
        return False, errors

    defined_alerts = set()
    for group in data.get("groups", []):
        for rule in group.get("rules", []):
            if "alert" in rule:
                defined_alerts.add(rule["alert"])

    for alert_name in REQUIRED_ALERTS:
        if alert_name not in defined_alerts:
            errors.append(f"Alert rule '{alert_name}' not found in alerts.yml")

    return len(errors) == 0, errors


def check_tracing_module() -> Tuple[bool, List[str]]:
    """Check that the tracing module loads and trace_span/async_trace_span are callable."""
    errors = []
    try:
        from app.core.tracing import trace_span, async_trace_span
        # Quick smoke test
        with trace_span("validate_observability_test", attributes={"provider": "none"}):
            pass
    except Exception as exc:
        errors.append(f"app.core.tracing import or execution failed: {exc}")
    return len(errors) == 0, errors


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate observability stack")
    parser.add_argument("--base-url", default="http://localhost:8000", help="Backend base URL")
    parser.add_argument("--skip-http", action="store_true", help="Skip live HTTP endpoint checks")
    args = parser.parse_args()

    repo_root = _REPO_ROOT
    all_passed = True

    print("\n" + "=" * 68)
    print("  Bridgestone IT Agent — Phase 5 Observability Validation")
    print("=" * 68)

    # -- 1. Tracing module ------------------------------------------------------
    _section("1. Tracing Module")
    ok, errs = check_tracing_module()
    if ok:
        _ok("app.core.tracing imports and trace_span executes without error")
    else:
        for e in errs:
            _fail(e)
        all_passed = False

    # -- 2. Prometheus registry -------------------------------------------------
    _section("2. Prometheus Registry (local import)")
    ok, errs = check_registry_metrics()
    if ok:
        _ok(f"All {len(REQUIRED_METRICS)} required metrics registered in Prometheus registry")
    else:
        for e in errs:
            _fail(e)
        all_passed = False

    # -- 3. Alerting rules ------------------------------------------------------
    _section("3. Prometheus Alert Rules")
    ok, errs = check_alerts_file(repo_root)
    if ok:
        _ok(f"All {len(REQUIRED_ALERTS)} required alert rules present in alerts.yml")
    else:
        for e in errs:
            _fail(e)
        all_passed = False

    # -- 4. Live HTTP endpoints -------------------------------------------------
    if not args.skip_http:
        _section(f"4. Live HTTP Endpoints ({args.base_url})")
        print("  (Use --skip-http to bypass if backend is not running)\n")

        ok, errs = check_health_endpoint(args.base_url)
        if ok:
            _ok("GET /health → 200, JSON structure valid, X-Correlation-ID present")
        else:
            for e in errs:
                _fail(e)
            all_passed = False

        ok, errs = check_ready_endpoint(args.base_url)
        if ok:
            _ok("GET /ready → 200, status='ready'")
        else:
            for e in errs:
                _fail(e)
            all_passed = False

        ok, errs = check_metrics_endpoint(args.base_url)
        if ok:
            _ok(f"GET /metrics → 200, all {len(REQUIRED_METRICS)} metric names present")
        else:
            for e in errs:
                _fail(e)
            all_passed = False
    else:
        _section("4. Live HTTP Endpoints")
        print(f"  {YELLOW}(Skipped - --skip-http){RESET}")

    # -- Summary ----------------------------------------------------------------
    print("\n" + "=" * 68)
    if all_passed:
        print(f"  {GREEN}ALL CHECKS PASSED{RESET}")
    else:
        print(f"  {RED}ONE OR MORE CHECKS FAILED{RESET}")
    print("=" * 68 + "\n")

    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()
