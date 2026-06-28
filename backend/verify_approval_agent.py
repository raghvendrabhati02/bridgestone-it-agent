"""
verify_approval_agent.py
========================
Verifies the Approval Agent end-to-end:
  1. Privileged action detection
  2. Non-privileged bypass
  3. PENDING gate (new request)
  4. APPROVED pass-through
  5. REJECTED block
  6. audit_approval writes a trace record
  7. Graph node import check
"""
import sys
import os

# Make sure the backend package is on the path
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


print("\n=== Approval Agent Verification ===\n")

# ── Test 1: Import service ────────────────────────────────────────────────────
print("1. Service imports")
try:
    from app.services.approval_service import (
        detect_privileged,
        create_approval_entry,
        update_approval,
        audit_approval,
        get_approval,
        PRIVILEGED_KEYWORDS,
    )
    check("approval_service imports cleanly", True)
except Exception as e:
    check(f"approval_service imports cleanly — ERROR: {e}", False)

# ── Test 2: detect_privileged — positive cases ────────────────────────────────
print("\n2. Privileged action detection")
privileged_states = [
    {"recommended_action": "restart_server",       "decision": "EXECUTE_ACTION"},
    {"recommended_action": "reset_password",        "decision": "EXECUTE_ACTION"},
    {"recommended_action": "delete_ticket",         "decision": "EXECUTE_ACTION"},
    {"recommended_action": "change_configuration",  "decision": "EXECUTE_ACTION"},
    {"approval_required": True,                     "decision": "EXECUTE_ACTION"},
]
for s in privileged_states:
    try:
        result = detect_privileged(s)
        check(f"detect_privileged({s.get('recommended_action', 'explicit flag')!r}) -> True", result is True)
    except Exception as e:
        check(f"detect_privileged raised: {e}", False)

# ── Test 3: detect_privileged — negative case ────────────────────────────────
print("\n3. Non-privileged bypass")
safe_states = [
    {"recommended_action": "check_vpn_status",  "decision": "EXECUTE_ACTION"},
    {"recommended_action": "run_diagnostic",     "decision": "EXECUTE_ACTION"},
    {"recommended_action": "",                   "decision": "EXECUTE_ACTION"},
    {"recommended_action": "fetch_logs",         "decision": "EXECUTE_ACTION"},
]
for s in safe_states:
    try:
        result = detect_privileged(s)
        check(f"detect_privileged({s['recommended_action']!r}) -> False", result is False)
    except Exception as e:
        check(f"detect_privileged raised: {e}", False)

# ── Test 4: create_approval_entry ─────────────────────────────────────────────
print("\n4. Approval entry creation")
try:
    entry = create_approval_entry("session-test-001", "restart_server")
    check("entry has session_id",         entry.get("session_id") == "session-test-001")
    check("entry has recommended_action", entry.get("recommended_action") == "restart_server")
    check("entry status is PENDING",      entry.get("approval_status") == "PENDING")
    check("entry has timestamp",          bool(entry.get("timestamp")))
except Exception as e:
    check(f"create_approval_entry raised: {e}", False)

# ── Test 5: update_approval APPROVED ─────────────────────────────────────────
print("\n5. Approve")
try:
    approved = update_approval("session-test-001", "APPROVED")
    check("status updated to APPROVED", approved.get("approval_status") == "APPROVED")
    stored = get_approval("session-test-001")
    check("in-memory store updated",    stored.get("approval_status") == "APPROVED")
except Exception as e:
    check(f"update_approval(APPROVED) raised: {e}", False)

# ── Test 6: update_approval REJECTED ─────────────────────────────────────────
print("\n6. Reject")
try:
    create_approval_entry("session-test-002", "delete_ticket")
    rejected = update_approval("session-test-002", "REJECTED")
    check("status updated to REJECTED", rejected.get("approval_status") == "REJECTED")
except Exception as e:
    check(f"update_approval(REJECTED) raised: {e}", False)

# ── Test 7: approval_node — PENDING gate ──────────────────────────────────────
print("\n7. approval_node — PENDING gate")
try:
    from app.graph.nodes.approval_node import approval_node
    state = {
        "session_id":          "session-node-001",
        "recommended_action":  "restart_server",
        "decision":            "EXECUTE_ACTION",
        "approval_required":   False,
        "approval_status":     "PENDING",
        "user_role":           "ADMIN",
        "username":            "admin",
    }
    result = approval_node(state)
    check("node returns dict",                         isinstance(result, dict))
    check("approval_required is True",                 result.get("approval_required") is True)
    check("approval_status is PENDING",                result.get("approval_status") == "PENDING")
    check("decision is REQUEST_APPROVAL",              result.get("decision") == "REQUEST_APPROVAL")
    check("decision_response contains APPROVE prompt", "APPROVE" in (result.get("decision_response") or ""))
except Exception as e:
    check(f"approval_node PENDING raised: {e}", False)

# ── Test 8: approval_node — APPROVED pass-through ────────────────────────────
print("\n8. approval_node — APPROVED pass-through")
try:
    state = {
        "session_id":         "session-node-002",
        "recommended_action": "restart_server",
        "decision":           "EXECUTE_ACTION",
        "approval_required":  True,
        "approval_status":    "APPROVED",
        "user_role":           "ADMIN",
        "username":            "admin",
    }
    result = approval_node(state)
    check("decision is EXECUTE_ACTION", result.get("decision") == "EXECUTE_ACTION")
    check("approval_status stays APPROVED", result.get("approval_status") == "APPROVED")
except Exception as e:
    check(f"approval_node APPROVED raised: {e}", False)

# ── Test 9: approval_node — REJECTED block ────────────────────────────────────
print("\n9. approval_node — REJECTED block")
try:
    state = {
        "session_id":         "session-node-003",
        "recommended_action": "restart_server",
        "decision":           "EXECUTE_ACTION",
        "approval_required":  True,
        "approval_status":    "REJECTED",
        "user_role":           "ADMIN",
        "username":            "admin",
    }
    result = approval_node(state)
    check("decision is REJECTED",           result.get("decision") == "REJECTED")
    check("approval_status stays REJECTED", result.get("approval_status") == "REJECTED")
except Exception as e:
    check(f"approval_node REJECTED raised: {e}", False)

# ── Test 10: Non-privileged — auto-approved bypass ────────────────────────────
print("\n10. approval_node — non-privileged auto-bypass")
try:
    state = {
        "session_id":         "session-node-004",
        "recommended_action": "check_vpn_status",
        "decision":           "EXECUTE_ACTION",
        "approval_required":  False,
        "approval_status":    "PENDING",
        "user_role":           "ADMIN",
        "username":            "admin",
    }
    result = approval_node(state)
    check("approval_required is False",   result.get("approval_required") is False)
    check("approval_status is APPROVED",  result.get("approval_status") == "APPROVED")
    check("no blocking decision set",     result.get("decision") != "REQUEST_APPROVAL")
except Exception as e:
    check(f"approval_node bypass raised: {e}", False)

# ── Test 11: audit_approval does not crash ────────────────────────────────────
print("\n11. audit_approval trace")
try:
    audit_approval("session-audit-001", "restart_server", "PENDING")
    check("audit_approval runs without exception", True)
except Exception as e:
    check(f"audit_approval raised: {e}", False)

# ── Summary ───────────────────────────────────────────────────────────────────
print("\n" + "=" * 45)
passed = sum(1 for _, ok in results if ok)
total  = len(results)
print(f"Results: {passed}/{total} tests passed")
if passed == total:
    print("[OK] All Approval Agent checks PASSED")
    sys.exit(0)
else:
    print("[FAIL] Some checks FAILED - see output above")
    sys.exit(1)
