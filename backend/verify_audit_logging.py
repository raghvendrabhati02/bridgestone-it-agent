"""
verify_audit_logging.py
========================
Enterprise Readiness Sprint 1 — Phase 4

Tests:
  1. Ticket creation → rbac_audit_logs row exists (action='create_ticket')
  2. Lifecycle transition → row exists with old_state / new_state
  3. Approval event → row exists (action='approve_privileged_action')
  4. ACCESS_DENIED event → row exists (action='ACCESS_DENIED')
  5. get_rbac_audit_logs(ticket_id=...) filters correctly
  6. Volatile fallback when DB unavailable (service does not raise)

Run from backend/
    python verify_audit_logging.py
"""

import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

import logging
logging.disable(logging.CRITICAL)

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


# ── Imports ───────────────────────────────────────────────────────────────────

from app.services.rbac_audit_service import log_rbac_event, get_rbac_audit_logs
from app.database.session import get_db
from app.database.repositories.rbac_audit_repository import RbacAuditRepository

TEST_TICKET = "INC_AUDIT_TEST_001"

def count_events(ticket_id=None, action=None):
    """Helper: count rows matching optional filters."""
    logs = get_rbac_audit_logs(ticket_id=ticket_id)
    if action:
        logs = [l for l in logs if l.get("action") == action]
    return len(logs)

def cleanup():
    try:
        from app.database.models.rbac_audit_log import RbacAuditLog
        with get_db() as db:
            db.query(RbacAuditLog).filter(
                RbacAuditLog.ticket_id == TEST_TICKET
            ).delete()
            db.commit()
    except Exception as e:
        print(f"  [WARN] Cleanup failed: {e}")


# ─────────────────────────────────────────────────────────────────────────────
print("\n" + "=" * 62)
print("  VERIFY_AUDIT_LOGGING.PY — RBAC Audit Log Tests")
print("=" * 62)

cleanup()   # Start with a clean slate

# ── Test 1: Ticket creation audit row ────────────────────────────────────────
print("\n[TEST 1] Ticket creation emits audit row")

log_rbac_event(
    user="alice",
    role="EMPLOYEE",
    action="create_ticket",
    ticket_id=TEST_TICKET,
    old_state=None,
    new_state="OPEN",
    details={"category": "VPN"},
)

rows = get_rbac_audit_logs(ticket_id=TEST_TICKET)
creation_rows = [r for r in rows if r.get("action") == "create_ticket"]

check(
    "At least 1 'create_ticket' row exists for test ticket",
    len(creation_rows) >= 1,
    f"Found {len(creation_rows)} row(s)",
)
if creation_rows:
    row = creation_rows[0]
    check("Row user == 'alice'",      row.get("user") == "alice")
    check("Row role == 'EMPLOYEE'",   row.get("role") == "EMPLOYEE")
    check("Row new_state == 'OPEN'",  row.get("new_state") == "OPEN")
    check("Row old_state is None",    row.get("old_state") is None)
    check("Row details contains 'category'",
          isinstance(row.get("details"), dict) and "category" in row.get("details", {}))

# ── Test 2: Lifecycle transition audit row ────────────────────────────────────
print("\n[TEST 2] Lifecycle transition emits audit row with old_state/new_state")

log_rbac_event(
    user="manager",
    role="MANAGER",
    action="update_ticket_lifecycle",
    ticket_id=TEST_TICKET,
    old_state="OPEN",
    new_state="ASSIGNED",
    details={"note": "Auto-assigned"},
)

rows = get_rbac_audit_logs(ticket_id=TEST_TICKET)
transition_rows = [r for r in rows if r.get("action") == "update_ticket_lifecycle"]

check(
    "At least 1 'update_ticket_lifecycle' row exists",
    len(transition_rows) >= 1,
    f"Found {len(transition_rows)} row(s)",
)
if transition_rows:
    row = transition_rows[0]
    check("Row old_state == 'OPEN'",     row.get("old_state") == "OPEN")
    check("Row new_state == 'ASSIGNED'", row.get("new_state") == "ASSIGNED")
    check("Row role == 'MANAGER'",       row.get("role") == "MANAGER")

# ── Test 3: Approval event audit row ─────────────────────────────────────────
print("\n[TEST 3] Approval event emits audit row")

log_rbac_event(
    user="manager",
    role="MANAGER",
    action="approve_privileged_action",
    ticket_id=TEST_TICKET,
    old_state="PENDING",
    new_state="APPROVED",
    details={"recommended_action": "restart_service"},
)

rows = get_rbac_audit_logs(ticket_id=TEST_TICKET)
approval_rows = [r for r in rows if r.get("action") == "approve_privileged_action"]

check(
    "At least 1 'approve_privileged_action' row exists",
    len(approval_rows) >= 1,
    f"Found {len(approval_rows)} row(s)",
)
if approval_rows:
    row = approval_rows[0]
    check("Approval row new_state == 'APPROVED'", row.get("new_state") == "APPROVED")
    check("Approval row old_state == 'PENDING'",  row.get("old_state") == "PENDING")

# ── Test 4: ACCESS_DENIED audit row ──────────────────────────────────────────
print("\n[TEST 4] ACCESS_DENIED event emits audit row")

log_rbac_event(
    user="bob",
    role="EMPLOYEE",
    action="ACCESS_DENIED",
    ticket_id=TEST_TICKET,
    old_state="OPEN",
    new_state=None,
    details={"reason": "RBAC_DENIED", "required_action": "close_ticket"},
)

rows = get_rbac_audit_logs(ticket_id=TEST_TICKET)
denied_rows = [r for r in rows if r.get("action") == "ACCESS_DENIED"]

check(
    "At least 1 'ACCESS_DENIED' row exists",
    len(denied_rows) >= 1,
    f"Found {len(denied_rows)} row(s)",
)
if denied_rows:
    row = denied_rows[0]
    check("Denied row user == 'bob'",     row.get("user") == "bob")
    check("Denied row role == 'EMPLOYEE'", row.get("role") == "EMPLOYEE")
    check("Denied row details.reason == 'RBAC_DENIED'",
          isinstance(row.get("details"), dict) and
          row["details"].get("reason") == "RBAC_DENIED")

# ── Test 5: get_rbac_audit_logs(ticket_id) filters correctly ─────────────────
print("\n[TEST 5] Ticket-scoped filter returns only rows for that ticket")

OTHER_TICKET = "INC_AUDIT_OTHER_002"
log_rbac_event(
    user="charlie",
    role="MANAGER",
    action="close_ticket",
    ticket_id=OTHER_TICKET,
    old_state="RESOLVED",
    new_state="CLOSED",
)

filtered = get_rbac_audit_logs(ticket_id=TEST_TICKET)
wrong_ticket_rows = [r for r in filtered if r.get("ticket_id") == OTHER_TICKET]
check(
    f"Filtered results do not include rows for '{OTHER_TICKET}'",
    len(wrong_ticket_rows) == 0,
    f"Found {len(wrong_ticket_rows)} cross-contamination row(s)",
)
check(
    f"Filtered results include all rows for '{TEST_TICKET}'",
    all(r.get("ticket_id") == TEST_TICKET for r in filtered),
    f"Ticket IDs: {list(set(r.get('ticket_id') for r in filtered))}",
)

# Clean up other-ticket row
try:
    from app.database.models.rbac_audit_log import RbacAuditLog
    with get_db() as db:
        db.query(RbacAuditLog).filter(
            RbacAuditLog.ticket_id == OTHER_TICKET
        ).delete()
        db.commit()
except Exception:
    pass

# ── Test 6: Total row count matches expected emissions ────────────────────────
print("\n[TEST 6] Total rows for test ticket match expected emission count")

final_rows = get_rbac_audit_logs(ticket_id=TEST_TICKET)
check(
    "Total rows == 4 (create + transition + approval + access_denied)",
    len(final_rows) == 4,
    f"Found {len(final_rows)} row(s)",
)

# ── Test 7: Service is non-fatal on missing table (simulated error) ───────────
print("\n[TEST 7] log_rbac_event is non-fatal on error (returns fallback dict)")

import unittest.mock as mock

with mock.patch(
    "app.database.session.get_db",
    side_effect=RuntimeError("simulated DB failure"),
):
    result = log_rbac_event(
        user="test",
        role="EMPLOYEE",
        action="create_ticket",
        ticket_id="INC_VOLATILE",
    )

check(
    "log_rbac_event returned a dict (not raised) on DB failure",
    isinstance(result, dict),
    f"Returned: {result}",
)
check(
    "Volatile fallback dict has 'action' key",
    result.get("action") == "create_ticket",
)

# Cleanup
cleanup()

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
    print("\n  ALL AUDIT LOGGING TESTS PASSED ✅")
    sys.exit(0)
