"""
verify_ticket_ownership.py
===========================
Enterprise Readiness Sprint 1 — Phase 4

Tests:
  1. EMPLOYEE can_modify_ticket → own ticket → True
  2. EMPLOYEE can_modify_ticket → other employee's ticket → False
  3. MANAGER can modify any ticket → True
  4. ADMIN can modify any ticket → True
  5. Ticket not in DB → EMPLOYEE allowed (in-flight tolerance)
  6. build_ownership_denied_response shape

Run from backend/
    python verify_ticket_ownership.py
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


# ── Seed a ticket in the DB for ownership tests ───────────────────────────────

from app.database.session import get_db
from app.database.repositories.ticket_repository import TicketRepository

TEST_TICKET_ID   = "INC_OWN_TEST_001"
OWNER_USERNAME   = "alice"
OTHER_USERNAME   = "bob"

def seed_ticket(ticket_id: str, owner: str):
    try:
        with get_db() as db:
            repo = TicketRepository(db)
            repo.save_ticket(
                ticket_id=ticket_id,
                category="VPN",
                description="Ownership test ticket",
                issue_description="Ownership test ticket",
                assigned_team="Network Team",
                priority="P2",
                sla_hours=8,
                status="OPEN",
                created_by=owner,
            )
    except Exception as e:
        print(f"  [WARN] Seed failed: {e}")

def cleanup_ticket(ticket_id: str):
    try:
        with get_db() as db:
            from app.database.models.ticket import Ticket
            db.query(Ticket).filter(Ticket.ticket_id == ticket_id).delete()
            db.commit()
    except Exception:
        pass


# ─────────────────────────────────────────────────────────────────────────────
print("\n" + "=" * 62)
print("  VERIFY_TICKET_OWNERSHIP.PY — Ownership Validation Tests")
print("=" * 62)

from app.services.ticket_ownership_service import (
    can_modify_ticket,
    get_ticket_owner,
    build_ownership_denied_response,
)

# Seed test ticket owned by alice
cleanup_ticket(TEST_TICKET_ID)
seed_ticket(TEST_TICKET_ID, OWNER_USERNAME)

# ── Test 1: EMPLOYEE + own ticket ─────────────────────────────────────────────
print("\n[TEST 1] EMPLOYEE can modify their OWN ticket")
result = can_modify_ticket(username=OWNER_USERNAME, role="EMPLOYEE", ticket_id=TEST_TICKET_ID)
check(
    f"EMPLOYEE '{OWNER_USERNAME}' can_modify_ticket '{TEST_TICKET_ID}' (own ticket)",
    result,
    f"Returned: {result}",
)

# ── Test 2: EMPLOYEE + other employee's ticket ────────────────────────────────
print("\n[TEST 2] EMPLOYEE denied modifying ANOTHER employee's ticket")
result = can_modify_ticket(username=OTHER_USERNAME, role="EMPLOYEE", ticket_id=TEST_TICKET_ID)
check(
    f"EMPLOYEE '{OTHER_USERNAME}' cannot modify '{TEST_TICKET_ID}' (owned by '{OWNER_USERNAME}')",
    not result,
    f"Returned: {result}",
)

# ── Test 3: MANAGER can modify any ticket ─────────────────────────────────────
print("\n[TEST 3] MANAGER can modify any ticket")
result = can_modify_ticket(username=OTHER_USERNAME, role="MANAGER", ticket_id=TEST_TICKET_ID)
check(
    f"MANAGER '{OTHER_USERNAME}' can modify '{TEST_TICKET_ID}'",
    result,
    f"Returned: {result}",
)

# ── Test 4: ADMIN can modify any ticket ───────────────────────────────────────
print("\n[TEST 4] ADMIN can modify any ticket")
result = can_modify_ticket(username="admin_user", role="ADMIN", ticket_id=TEST_TICKET_ID)
check(
    f"ADMIN 'admin_user' can modify '{TEST_TICKET_ID}'",
    result,
    f"Returned: {result}",
)

# ── Test 5: Ticket not in DB — EMPLOYEE allowed (in-flight tolerance) ─────────
print("\n[TEST 5] Ticket not in DB — EMPLOYEE allowed (in-flight ticket creation)")
GHOST_TICKET = "INC_GHOST_999999"
cleanup_ticket(GHOST_TICKET)
result = can_modify_ticket(username=OWNER_USERNAME, role="EMPLOYEE", ticket_id=GHOST_TICKET)
check(
    f"EMPLOYEE '{OWNER_USERNAME}' allowed for unknown ticket '{GHOST_TICKET}'",
    result,
    f"Returned: {result} (expected True — in-flight tolerance)",
)

# ── Test 6: get_ticket_owner ──────────────────────────────────────────────────
print("\n[TEST 6] get_ticket_owner returns correct owner")
owner = get_ticket_owner(TEST_TICKET_ID)
check(
    f"get_ticket_owner('{TEST_TICKET_ID}') == '{OWNER_USERNAME}'",
    owner == OWNER_USERNAME,
    f"Returned: {owner!r}",
)

# ── Test 7: build_ownership_denied_response shape ─────────────────────────────
print("\n[TEST 7] build_ownership_denied_response returns ACCESS_DENIED structure")
denied = build_ownership_denied_response(OTHER_USERNAME, TEST_TICKET_ID)
check(
    "decision == 'ACCESS_DENIED'",
    denied.get("decision") == "ACCESS_DENIED",
)
check(
    "decision_response contains 'ACCESS_DENIED'",
    "ACCESS_DENIED" in denied.get("decision_response", ""),
)
check(
    f"decision_response mentions ticket '{TEST_TICKET_ID}'",
    TEST_TICKET_ID in denied.get("decision_response", ""),
)

# ── Test 8: Simulate Employee B trying to close Employee A's ticket ───────────
print("\n[TEST 8] Simulation: Employee B tries to close Employee A's ticket")
from app.services import rbac_service

rbac_ok   = rbac_service.has_permission("EMPLOYEE", "close_ticket")   # False
own_ok    = can_modify_ticket(OTHER_USERNAME, "EMPLOYEE", TEST_TICKET_ID)  # False

access_granted = rbac_ok and own_ok
check(
    "Employee B denied closing Employee A's ticket (both RBAC + ownership fail)",
    not access_granted,
    f"rbac_ok={rbac_ok}, ownership_ok={own_ok} → access_granted={access_granted}",
)

# Cleanup
cleanup_ticket(TEST_TICKET_ID)

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
    print("\n  ALL OWNERSHIP TESTS PASSED ✅")
    sys.exit(0)
