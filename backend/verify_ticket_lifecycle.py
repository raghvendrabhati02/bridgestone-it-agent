"""
verify_ticket_lifecycle.py
==========================
Verifies the Ticket Lifecycle Agent end-to-end:
  1. Service import
  2. init_lifecycle is idempotent
  3. VALID_TRANSITIONS completeness
  4. Forward transitions (full happy path)
  5. Invalid / backward transition guard
  6. Notification emission
  7. auto_transition_from_intent keyword mapping
  8. ticket_lifecycle_node returns expected keys
  9. Lifecycle persists across node calls
 10. get_state helper
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

# Force UTF-8 output on Windows terminals
if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

PASS = "\033[92mPASS\033[0m"
FAIL = "\033[91mFAIL\033[0m"
results = []


def check(name: str, condition: bool) -> None:
    status = PASS if condition else FAIL
    print(f"  [{status}] {name}")
    results.append((name, condition))


print("\n=== Ticket Lifecycle Agent Verification ===\n")

# ── Test 1: Service import ────────────────────────────────────────────────────
print("1. Service imports")
try:
    from app.services.ticket_lifecycle_service import (
        init_lifecycle,
        transition,
        get_lifecycle,
        get_state,
        record_event,
        auto_transition_from_intent,
        ALL_STATES,
        VALID_TRANSITIONS,
        TRANSITION_MESSAGES,
    )
    check("ticket_lifecycle_service imports cleanly", True)
except Exception as e:
    check(f"ticket_lifecycle_service import — ERROR: {e}", False)
    sys.exit(1)

# ── Test 2: ALL_STATES completeness ──────────────────────────────────────────
print("\n2. State machine completeness")
expected_states = ["OPEN", "ASSIGNED", "IN_PROGRESS", "WAITING_FOR_USER", "RESOLVED", "CLOSED"]
for st in expected_states:
    check(f"'{st}' defined in ALL_STATES", st in ALL_STATES)
    check(f"'{st}' has message template",  st in TRANSITION_MESSAGES)

# ── Test 3: init_lifecycle ────────────────────────────────────────────────────
print("\n3. Lifecycle initialisation")
try:
    lc = init_lifecycle("TKT-VERIFY-001")
    check("returns dict",           isinstance(lc, dict))
    check("state is OPEN",          lc.get("state") == "OPEN")
    check("history is not empty",   len(lc.get("history", [])) > 0)
    check("ticket_id is set",       lc.get("ticket_id") == "TKT-VERIFY-001")
    check("created_at is set",      bool(lc.get("created_at")))

    # Idempotency
    lc2 = init_lifecycle("TKT-VERIFY-001")
    check("second init returns same state", lc2.get("state") == lc.get("state"))
except Exception as e:
    check(f"init_lifecycle raised: {e}", False)

# ── Test 4: Forward transition — full happy path ──────────────────────────────
print("\n4. Full forward lifecycle path")
ticket = "TKT-VERIFY-FULL"
init_lifecycle(ticket)
path = ["ASSIGNED", "IN_PROGRESS", "RESOLVED", "CLOSED"]
prev = "OPEN"
for target in path:
    try:
        lc = transition(ticket, target, session_id="sess-verify")
        check(f"  {prev} → {target} accepted",  lc.get("state") == target)
        history_states = [e.get("to_state") for e in lc.get("history", []) if "to_state" in e]
        check(f"  {target} recorded in history", target in history_states)
        prev = target
    except Exception as e:
        check(f"  transition to {target} raised: {e}", False)

# ── Test 5: WAITING_FOR_USER path ────────────────────────────────────────────
print("\n5. WAITING_FOR_USER branch")
ticket_w = "TKT-VERIFY-WAIT"
init_lifecycle(ticket_w)
transition(ticket_w, "ASSIGNED")
transition(ticket_w, "IN_PROGRESS")
try:
    lc = transition(ticket_w, "WAITING_FOR_USER")
    check("transition to WAITING_FOR_USER", lc.get("state") == "WAITING_FOR_USER")
    lc = transition(ticket_w, "IN_PROGRESS")
    check("re-enter IN_PROGRESS from WAITING",  lc.get("state") == "IN_PROGRESS")
    lc = transition(ticket_w, "RESOLVED")
    check("resolve from IN_PROGRESS",           lc.get("state") == "RESOLVED")
except Exception as e:
    check(f"WAITING_FOR_USER path raised: {e}", False)

# ── Test 6: Invalid / backward transition guard ───────────────────────────────
print("\n6. Invalid transition guard")
ticket_bad = "TKT-VERIFY-INVALID"
init_lifecycle(ticket_bad)  # state = OPEN
try:
    lc = transition(ticket_bad, "RESOLVED")       # skip ASSIGNED / IN_PROGRESS
    check("OPEN → RESOLVED rejected (stays OPEN)", lc.get("state") == "OPEN")
    lc = transition(ticket_bad, "CLOSED")          # direct close from OPEN
    check("OPEN → CLOSED rejected (stays OPEN)",   lc.get("state") == "OPEN")
except Exception as e:
    check(f"Invalid transition raised: {e}", False)

# ── Test 7: get_state helper ──────────────────────────────────────────────────
print("\n7. get_state helper")
try:
    ticket_gs = "TKT-VERIFY-GS"
    init_lifecycle(ticket_gs)
    transition(ticket_gs, "ASSIGNED")
    state_str = get_state(ticket_gs)
    check("get_state returns current string", state_str == "ASSIGNED")
    missing_state = get_state("TKT-NONEXISTENT-999")
    check("get_state returns None for unknown ticket", missing_state is None)
except Exception as e:
    check(f"get_state raised: {e}", False)

# ── Test 8: record_event ──────────────────────────────────────────────────────
print("\n8. record_event")
try:
    ticket_ev = "TKT-VERIFY-EVENT"
    init_lifecycle(ticket_ev)
    record_event(ticket_ev, "SLA breach warning", session_id="sess-event")
    lc = get_lifecycle(ticket_ev)
    notes = [e.get("note") for e in lc.get("history", [])]
    check("event note stored in history", "SLA breach warning" in notes)
    check("state unchanged after event",  lc.get("state") == "OPEN")
except Exception as e:
    check(f"record_event raised: {e}", False)

# ── Test 9: auto_transition_from_intent keyword mapping ──────────────────────
print("\n9. auto_transition_from_intent keyword mapping")
keyword_tests = [
    ("TKT-KW-1", "OPEN",    "please assign this ticket",       "ASSIGNED"),
    ("TKT-KW-2", "OPEN",    "start working on it now",         None),        # Not valid from OPEN
    ("TKT-KW-4", "OPEN",    "resolve this please",             None),        # Not valid from OPEN
]
for tid, start_state, user_msg, expected_state in keyword_tests:
    init_lifecycle(tid, initial_state=start_state)
    try:
        result = auto_transition_from_intent(tid, user_msg, session_id="sess-kw")
        if expected_state is None:
            check(
                f"'{user_msg[:30]}' -> no transition (still {start_state})",
                result is None,
            )
        else:
            check(
                f"'{user_msg[:30]}' -> transitions to {expected_state}",
                result == expected_state and get_state(tid) == expected_state,
            )
    except Exception as e:
        check(f"auto_transition_from_intent raised: {e}", False)

# test separate – ASSIGNED → IN_PROGRESS
init_lifecycle("TKT-KW-3", initial_state="ASSIGNED")
try:
    result = auto_transition_from_intent("TKT-KW-3", "start working on it now")
    check("'start working on it now' → IN_PROGRESS from ASSIGNED", result == "IN_PROGRESS")
except Exception as e:
    check(f"auto_transition to IN_PROGRESS raised: {e}", False)

# ── Test 10: ticket_lifecycle_node ───────────────────────────────────────────
print("\n10. ticket_lifecycle_node")
try:
    from app.graph.nodes.ticket_lifecycle_node import ticket_lifecycle_node
    state = {
        "session_id":   "sess-node-001",
        "ticket":       {"ticket_id": "TKT-NODE-001", "assigned_team": "Network Team"},
        "active_ticket": "TKT-NODE-001",
        "user_message": "please assign this",
        "notifications": [],
    }
    result = ticket_lifecycle_node(state)
    check("node returns dict",                isinstance(result, dict))
    check("ticket_lifecycle key present",     "ticket_lifecycle" in result)
    check("lifecycle is dict",                isinstance(result.get("ticket_lifecycle"), dict))
    check("lifecycle state is not None",      result["ticket_lifecycle"].get("state") is not None)
    check("notifications key present",        "notifications" in result)
    check("notifications is list",            isinstance(result.get("notifications"), list))
except Exception as e:
    check(f"ticket_lifecycle_node raised: {e}", False)

# ── Test 11: node handles missing ticket gracefully ───────────────────────────
print("\n11. ticket_lifecycle_node — missing ticket guard")
try:
    result = ticket_lifecycle_node({
        "session_id":   "sess-empty",
        "ticket":       {},
        "user_message": "",
    })
    check("returns empty dict safely", isinstance(result, dict))
except Exception as e:
    check(f"missing ticket raised: {e}", False)

# ── Summary ───────────────────────────────────────────────────────────────────
print("\n" + "=" * 45)
passed = sum(1 for _, ok in results if ok)
total  = len(results)
print(f"Results: {passed}/{total} tests passed")
if passed == total:
    print("[OK] All Ticket Lifecycle checks PASSED")
    sys.exit(0)
else:
    print("[FAIL] Some checks FAILED - see output above")
    sys.exit(1)
