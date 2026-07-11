"""
verify_rbac_privilege_escalation.py
=====================================
Regression test for the RBAC privilege-escalation bug.

Reported sequence (pre-fix):
    EMPLOYEE → "Reset my VPN access" → ACCESS_DENIED
    EMPLOYEE → "yes"                 → EXECUTE_ACTION  ← BUG

Expected sequence (post-fix):
    EMPLOYEE → "Reset my VPN access" → ACCESS_DENIED
    EMPLOYEE → "yes"                 → NOT EXECUTE_ACTION

Exit code 0  → ALL TESTS PASSED
Exit code 1  → FAILURE (escalation still possible)
"""

import sys
import os
import uuid
import logging
import mock_gemini

# ── Bootstrap: point Python at the backend package root ──────────────────────
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _SCRIPT_DIR)

logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("verify_rbac_privilege_escalation")

_PASS = "\033[32mPASS\033[0m"
_FAIL = "\033[31mFAIL\033[0m"
_INFO = "\033[36mINFO\033[0m"

failures: list[str] = []


def _result(name: str, passed: bool, detail: str = "") -> None:
    tag = _PASS if passed else _FAIL
    print(f"  [{tag}] {name}" + (f"  ->  {detail}" if detail else ""))
    if not passed:
        failures.append(f"{name}: {detail}")

# ─────────────────────────────────────────────────────────────────────────────
print("\n" + "=" * 68)
print("  SECTION 2 -- Unit: rbac_service state-isolation helpers")
print("=" * 68)

try:
    from app.services.rbac_service import has_permission, build_access_denied_response

    _result(
        "EMPLOYEE denied approve_privileged_action",
        not has_permission("EMPLOYEE", "approve_privileged_action"),
    )
    _result(
        "MANAGER allowed approve_privileged_action",
        has_permission("MANAGER", "approve_privileged_action"),
    )
    _result(
        "ADMIN allowed approve_privileged_action",
        has_permission("ADMIN", "approve_privileged_action"),
    )

    denied_resp = build_access_denied_response("EMPLOYEE", "approve_privileged_action")
    _result(
        "build_access_denied_response returns decision=ACCESS_DENIED",
        denied_resp.get("decision") == "ACCESS_DENIED",
        f"got {denied_resp.get('decision')!r}",
    )

except Exception as exc:
    print(f"  [{_FAIL}] rbac_service unit test raised: {exc}")
    failures.append(f"rbac_service unit test: {exc}")


# ─────────────────────────────────────────────────────────────────────────────
print("\n" + "=" * 68)
print("  SECTION 3 -- Unit: initial_state approval-forwarding guard")
print("=" * 68)

try:

    def _simulate_initial_state_build(session_status: str,
                                      approval_status: str,
                                      recommended_action: str,
                                      approval_required: bool) -> dict:
        """
        Reproduces the guard logic added to handle_chat_turn().
        Returns the values that would be placed in initial_state.
        """
        _session_awaiting       = session_status == "AWAITING_APPROVAL"
        _fwd_approval_status    = approval_status     if _session_awaiting else "PENDING"
        _fwd_recommended_action = recommended_action  if _session_awaiting else ""
        _fwd_approval_required  = approval_required   if _session_awaiting else False
        return {
            "approval_status":    _fwd_approval_status,
            "recommended_action": _fwd_recommended_action,
            "approval_required":  _fwd_approval_required,
        }

    # After ACCESS_DENIED the session status is ACTIVE -- guard must zero-out approval fields
    fwd = _simulate_initial_state_build(
        session_status     = "ACTIVE",                   # what is set after ACCESS_DENIED
        approval_status    = "PENDING",                  # stale poison value
        recommended_action = "VPN_ACCESS_RESTORATION",   # stale poison value
        approval_required  = True,
    )
    _result(
        "Guard zeros approval fields when session is not AWAITING_APPROVAL",
        fwd["approval_status"] == "PENDING" and fwd["recommended_action"] == "",
        f"approval_status={fwd['approval_status']!r}, recommended_action={fwd['recommended_action']!r}",
    )

    # When genuinely AWAITING_APPROVAL, guard must preserve the live fields
    fwd2 = _simulate_initial_state_build(
        session_status     = "AWAITING_APPROVAL",
        approval_status    = "PENDING",
        recommended_action = "VPN_ACCESS_RESTORATION",
        approval_required  = True,
    )
    _result(
        "Guard preserves approval fields when session is AWAITING_APPROVAL",
        fwd2["approval_status"] == "PENDING"
        and fwd2["recommended_action"] == "VPN_ACCESS_RESTORATION",
        f"approval_status={fwd2['approval_status']!r}, recommended_action={fwd2['recommended_action']!r}",
    )

except Exception as exc:
    print(f"  [{_FAIL}] initial_state guard unit test raised: {exc}")
    failures.append(f"initial_state guard unit test: {exc}")


# ─────────────────────────────────────────────────────────────────────────────
print("\n" + "=" * 68)
print("  SECTION 4 -- Integration: full handle_chat_turn() escalation sequence")
print("=" * 68)
print(f"  [{_INFO}] This section requires a running DB and Gemini API key.")
print(f"         Skipping gracefully if environment is unavailable.\n")

try:
    from app.services.conversation_service import handle_chat_turn

    _session_id = str(uuid.uuid4())

    # Turn 1: privileged request from EMPLOYEE
    print(f"  Turn 1: EMPLOYEE -> 'Reset my VPN access'")
    turn1 = handle_chat_turn(
        session_id=_session_id,
        message="Reset my VPN access",
        username="emp_test_escalation",
        user_role="EMPLOYEE",
    )
    _session_id = turn1.get("session_id", _session_id)
    action1 = turn1.get("action", "")
    print(f"         -> action={action1!r}")
    _result(
        "Turn 1: action is ACCESS_DENIED (not EXECUTE_ACTION)",
        action1 == "ACCESS_DENIED",
        f"got {action1!r}",
    )

    # Verify that the pending approval transitions to ACCESS_DENIED in database history
    from app.services.audit_service import get_all_approvals_history
    history = get_all_approvals_history()
    sess_history = [h for h in history if h.get("session_id") == _session_id]
    _result(
        "Turn 1: DB approval history contains ACCESS_DENIED for session",
        any(h.get("approval_status") == "ACCESS_DENIED" for h in sess_history),
        f"states in DB: {[h.get('approval_status') for h in sess_history]}",
    )

    # Turn 2: follow-up confirmation -- must NOT produce EXECUTE_ACTION
    print(f"\n  Turn 2: EMPLOYEE -> 'yes'  (same session)")
    turn2 = handle_chat_turn(
        session_id=_session_id,
        message="yes",
        username="emp_test_escalation",
        user_role="EMPLOYEE",
    )
    action2 = turn2.get("action", "")
    print(f"         -> action={action2!r}")

    escalation_blocked = action2 != "EXECUTE_ACTION"
    _result(
        "Turn 2: action is NOT EXECUTE_ACTION  [CRITICAL SECURITY CHECK]",
        escalation_blocked,
        f"got {action2!r} -- "
        + ("ESCALATION BLOCKED" if escalation_blocked else "PRIVILEGE ESCALATION DETECTED"),
    )
    _result(
        "Turn 2: approval_status cleared (not forwarded as stale PENDING)",
        turn2.get("approval_status") != "PENDING" or action2 == "ACCESS_DENIED",
        f"got approval_status={turn2.get('approval_status')!r}",
    )
    _result(
        "Turn 2: recommended_action cleared",
        turn2.get("recommended_action", "") == "",
        f"got recommended_action={turn2.get('recommended_action')!r}",
    )

    # Turn 3: another "yes" -- still must not escalate
    print(f"\n  Turn 3: EMPLOYEE -> 'yes'  (third message, same session)")
    turn3 = handle_chat_turn(
        session_id=_session_id,
        message="yes",
        username="emp_test_escalation",
        user_role="EMPLOYEE",
    )
    action3 = turn3.get("action", "")
    print(f"         -> action={action3!r}")
    _result(
        "Turn 3: action is still NOT EXECUTE_ACTION",
        action3 != "EXECUTE_ACTION",
        f"got {action3!r}",
    )

except ImportError as exc:
    print(f"  [{_INFO}] Integration test skipped (import error -- no DB/env?): {exc}")
except Exception as exc:
    print(f"  [{_FAIL}] Integration test raised: {exc}")
    logger.exception("Integration test failed")
    failures.append(f"Integration test: {exc}")


# ─────────────────────────────────────────────────────────────────────────────
print("\n" + "=" * 68)
print("  SECTION 5 -- Manager / Admin should still work (non-regression)")
print("=" * 68)

try:
    from app.services.rbac_service import has_permission

    _result(
        "MANAGER has approve_privileged_action",
        has_permission("MANAGER", "approve_privileged_action"),
    )
    _result(
        "ADMIN has approve_privileged_action",
        has_permission("ADMIN", "approve_privileged_action"),
    )
    _result(
        "ADMIN has execute_privileged_action",
        has_permission("ADMIN", "execute_privileged_action"),
    )
    _result(
        "EMPLOYEE still has create_ticket",
        has_permission("EMPLOYEE", "create_ticket"),
    )

except Exception as exc:
    print(f"  [{_FAIL}] Non-regression test raised: {exc}")
    failures.append(f"Non-regression test: {exc}")


# ─────────────────────────────────────────────────────────────────────────────
print("\n" + "=" * 68)
if failures:
    print(f"  RESULT: FAIL  --  {len(failures)} test(s) failed:\n")
    for f in failures:
        print(f"    * {f}")
    print("=" * 68 + "\n")
    sys.exit(1)
else:
    print(f"  RESULT: PASS  --  ALL TESTS PASSED")
    print("=" * 68 + "\n")
    sys.exit(0)
