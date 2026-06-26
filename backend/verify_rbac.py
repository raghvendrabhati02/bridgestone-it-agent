"""
verify_rbac.py
==============
Enterprise Readiness Sprint 1 — Phase 4

Tests:
  1. EMPLOYEE denied: lifecycle transition (close ticket)
  2. EMPLOYEE denied: approval of privileged action
  3. MANAGER allowed: lifecycle transition
  4. ADMIN allowed: all lifecycle actions

Run from backend/
    python verify_rbac.py
"""

import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

import logging
logging.disable(logging.CRITICAL)   # suppress noise during tests

# ── Helpers ───────────────────────────────────────────────────────────────────

PASS = "  [PASS]"
FAIL = "  [FAIL]"
results = []

def check(label: str, condition: bool, detail: str = ""):
    icon = PASS if condition else FAIL
    msg  = f"{icon}  {label}"
    if detail:
        msg += f"\n         -> {detail}"
    print(msg)
    results.append((label, condition))
    return condition


# ── Import services ───────────────────────────────────────────────────────────

from app.services.rbac_service import (
    has_permission,
    check_permission,
    get_role_summary,
    infer_lifecycle_action,
    build_access_denied_response,
    ROLE_PERMISSIONS,
)

# ─────────────────────────────────────────────────────────────────────────────
print("\n" + "=" * 62)
print("  VERIFY_RBAC.PY — RBAC Permission Matrix Tests")
print("=" * 62)

# ── Test 1: EMPLOYEE denied lifecycle transition ──────────────────────────────
print("\n[TEST 1] EMPLOYEE denied: lifecycle transitions")
check(
    "EMPLOYEE cannot update_ticket_lifecycle",
    not has_permission("EMPLOYEE", "update_ticket_lifecycle"),
)
check(
    "EMPLOYEE cannot resolve_ticket",
    not has_permission("EMPLOYEE", "resolve_ticket"),
)
check(
    "EMPLOYEE cannot close_ticket",
    not has_permission("EMPLOYEE", "close_ticket"),
)
check(
    "EMPLOYEE cannot override_lifecycle",
    not has_permission("EMPLOYEE", "override_lifecycle"),
)

# ── Test 2: EMPLOYEE denied approval actions ──────────────────────────────────
print("\n[TEST 2] EMPLOYEE denied: approval actions")
check(
    "EMPLOYEE cannot approve_privileged_action",
    not has_permission("EMPLOYEE", "approve_privileged_action"),
)
check(
    "EMPLOYEE cannot execute_privileged_action",
    not has_permission("EMPLOYEE", "execute_privileged_action"),
)
check(
    "EMPLOYEE cannot view_audit_logs",
    not has_permission("EMPLOYEE", "view_audit_logs"),
)

# ── Test 3: MANAGER allowed lifecycle transitions ─────────────────────────────
print("\n[TEST 3] MANAGER allowed: lifecycle transitions")
check(
    "MANAGER can update_ticket_lifecycle",
    has_permission("MANAGER", "update_ticket_lifecycle"),
)
check(
    "MANAGER can resolve_ticket",
    has_permission("MANAGER", "resolve_ticket"),
)
check(
    "MANAGER can close_ticket",
    has_permission("MANAGER", "close_ticket"),
)
check(
    "MANAGER can approve_privileged_action",
    has_permission("MANAGER", "approve_privileged_action"),
)
check(
    "MANAGER cannot view_audit_logs (ADMIN-only)",
    not has_permission("MANAGER", "view_audit_logs"),
)
check(
    "MANAGER cannot override_lifecycle (ADMIN-only)",
    not has_permission("MANAGER", "override_lifecycle"),
)

# ── Test 4: ADMIN allowed everything ─────────────────────────────────────────
print("\n[TEST 4] ADMIN allowed: all actions")
all_actions = list(ROLE_PERMISSIONS["ADMIN"])
for action in all_actions:
    check(
        f"ADMIN can {action}",
        has_permission("ADMIN", action),
    )

# ── Test 5: Utility helpers ───────────────────────────────────────────────────
print("\n[TEST 5] Utility function correctness")
check(
    "infer_lifecycle_action('CLOSED') == 'close_ticket'",
    infer_lifecycle_action("CLOSED") == "close_ticket",
)
check(
    "infer_lifecycle_action('RESOLVED') == 'resolve_ticket'",
    infer_lifecycle_action("RESOLVED") == "resolve_ticket",
)
check(
    "infer_lifecycle_action('IN_PROGRESS') == 'update_ticket_lifecycle'",
    infer_lifecycle_action("IN_PROGRESS") == "update_ticket_lifecycle",
)

# ── Test 6: check_permission raises PermissionError ──────────────────────────
print("\n[TEST 6] check_permission raises PermissionError for denied role")
try:
    check_permission("EMPLOYEE", "close_ticket")
    check("PermissionError raised for EMPLOYEE + close_ticket", False,
          "Expected PermissionError but none raised")
except PermissionError as e:
    check("PermissionError raised for EMPLOYEE + close_ticket", True, str(e))

# ── Test 7: ACCESS_DENIED response shape ─────────────────────────────────────
print("\n[TEST 7] build_access_denied_response shape")
denied = build_access_denied_response("EMPLOYEE", "close_ticket", "INC000001")
check(
    "decision == 'ACCESS_DENIED'",
    denied.get("decision") == "ACCESS_DENIED",
)
check(
    "decision_response contains 'ACCESS_DENIED'",
    "ACCESS_DENIED" in denied.get("decision_response", ""),
)

# ── Test 8: Unknown role defaults safely ─────────────────────────────────────
print("\n[TEST 8] Unknown role treated as EMPLOYEE (safe default)")
check(
    "Unknown role cannot close_ticket",
    not has_permission("SUPERHERO", "close_ticket"),
)
check(
    "Unknown role can create_ticket",
    has_permission("SUPERHERO", "create_ticket"),
)

# ── Test 9: get_role_summary returns all three roles ─────────────────────────
print("\n[TEST 9] get_role_summary returns expected roles")
summary = get_role_summary()
check("Summary contains EMPLOYEE", "EMPLOYEE" in summary)
check("Summary contains MANAGER",  "MANAGER"  in summary)
check("Summary contains ADMIN",    "ADMIN"    in summary)

# ── Results ───────────────────────────────────────────────────────────────────
print("\n" + "=" * 62)
passed = sum(1 for _, ok in results if ok)
failed = sum(1 for _, ok in results if not ok)
print(f"  Results: {passed} passed / {failed} failed / {len(results)} total")
print("=" * 62)

if failed:
    print("\n  FAILED TESTS:")
    for label, ok in results:
        if not ok:
            print(f"    ✗ {label}")
    sys.exit(1)
else:
    print("\n  ALL RBAC TESTS PASSED ✅")
    sys.exit(0)
