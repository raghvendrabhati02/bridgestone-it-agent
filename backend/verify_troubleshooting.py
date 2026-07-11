"""
verify_troubleshooting.py
─────────────────────────────────────────────────────────────────────────────
Sprint 2 - Troubleshooting Service verification suite.
"""

import os
import sys
import ast
import time
import threading
from datetime import datetime

# Setup sys path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Force UTF-8 output on Windows terminals
if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

PASS = "✔"
FAIL = "✘"
failures = []


def ok(name: str):
    print(f"  [{PASS}] {name}")


def err(name: str, info: str = ""):
    message = f"[{FAIL}] {name}" + (f": {info}" if info else "")
    print(f"  {message}")
    failures.append(message)


def section(name: str):
    print(f"\n--- {name} ---")


# ── 1. AST Parse ────────────────────────────────────────────────────────────
section("1. AST Parse")
service_path = os.path.join("app", "services", "troubleshooting_service.py")
try:
    with open(service_path, "r", encoding="utf-8") as f:
        ast.parse(f.read())
    ok("troubleshooting_service.py compiles without syntax errors")
except Exception as e:
    err("troubleshooting_service.py failed compilation", str(e))


# ── 2. Import ───────────────────────────────────────────────────────────────
section("2. Import")
try:
    import app.services.troubleshooting_service as ts
    import app.services.knowledge_service as ks
    ok("troubleshooting_service imported successfully")
except Exception as e:
    err("Failed to import troubleshooting_service", str(e))
    sys.exit(1)


# Pre-load articles if needed
ks.load_articles()


# ── 3. Start ────────────────────────────────────────────────────────────────
section("3. start()")
try:
    session = ts.start("KB0001")
    if session and session.article_id == "KB0001":
        ok("session successfully started for KB0001")
    else:
        err("start() returned incorrect session object")
except Exception as e:
    err("start() raised exception", str(e))


# ── 4. Invalid Article ───────────────────────────────────────────────────────
section("4. invalid article")
try:
    res = ts.start("KB9999")
    if res is None:
        ok("start() returned None for non-existent article ID")
    else:
        err("start() should return None for non-existent article ID")
except Exception as e:
    err("start() with invalid article ID raised exception", str(e))


# ── 5. Current Step ─────────────────────────────────────────────────────────
section("5. current_step()")
try:
    session = ts.start("KB0001")
    step = ts.current_step(session)
    if step and step.get("step") == 1:
        ok("current_step() returned step 1 details")
    else:
        err("current_step() returned wrong step", str(step))
except Exception as e:
    err("current_step() raised exception", str(e))


# ── 6. Next Step ────────────────────────────────────────────────────────────
section("6. next_step()")
try:
    session = ts.start("KB0001")
    step2 = ts.next_step(session)
    if step2 and step2.get("step") == 2 and session.current_step == 2:
        ok("next_step() advanced current_step to 2")
    else:
        err("next_step() failed to advance to step 2", str(step2))
except Exception as e:
    err("next_step() raised exception", str(e))


# ── 7. Previous Step ────────────────────────────────────────────────────────
section("7. previous_step()")
try:
    session = ts.start("KB0001")
    ts.next_step(session)  # Move to step 2
    prev = ts.previous_step(session)  # Move back to step 1
    if prev and prev.get("step") == 1 and session.current_step == 1:
        ok("previous_step() successfully decremented to step 1")
    else:
        err("previous_step() failed to return step 1 details", str(prev))
except Exception as e:
    err("previous_step() raised exception", str(e))


# ── 8. Mark Completed ───────────────────────────────────────────────────────
section("8. mark_completed()")
try:
    session = ts.start("KB0001")
    ts.mark_completed(session)
    if 1 in session.completed_steps:
        ok("mark_completed() added step 1 to completed list")
    else:
        err("mark_completed() failed to store step 1 in completed list")
except Exception as e:
    err("mark_completed() raised exception", str(e))


# ── 9. Duplicate Completion ─────────────────────────────────────────────────
section("9. duplicate completion")
try:
    session = ts.start("KB0001")
    ts.mark_completed(session)
    ts.mark_completed(session)
    if session.completed_steps == [1]:
        ok("mark_completed() does not create duplicate entries")
    else:
        err("mark_completed() allowed duplicate step completion entry", str(session.completed_steps))
except Exception as e:
    err("mark_completed() duplicate execution raised exception", str(e))


# ── 10. Attempts Increment ──────────────────────────────────────────────────
section("10. attempts increment")
try:
    session = ts.start("KB0001")
    total_steps = ts.get_total_steps(session)
    for _ in range(total_steps - 1):
        ts.next_step(session)
    
    # We are at final step (e.g. Step 5). Attempts should still be 0.
    if session.attempts != 0:
        err("attempts counter should be 0 before final step completion", f"got {session.attempts}")
        
    # Mark the final step completed to finish the cycle. Attempts should become 1.
    ts.mark_completed(session)
    if session.attempts == 1:
        ok("attempts counter increments to 1 on final step completion (exhaustion)")
    else:
        err("attempts counter did not track transitions correctly", f"expected 1, got {session.attempts}")
except Exception as e:
    err("attempts increment verification raised exception", str(e))


# ── 11. Reset ───────────────────────────────────────────────────────────────
section("11. reset()")
try:
    session = ts.start("KB0001")
    ts.next_step(session)
    ts.mark_completed(session)
    ts.reset(session)
    if (session.current_step == 1 and 
            session.completed_steps == [] and 
            session.attempts == 0 and 
            session.finished is False):
        ok("reset() clears all session counters and steps")
    else:
        err("reset() failed to restore initial state", str(session))
except Exception as e:
    err("reset() raised exception", str(e))


# ── 12. Finished False ──────────────────────────────────────────────────────
section("12. finished false")
try:
    session = ts.start("KB0001")
    if ts.is_finished(session) is False:
        ok("is_finished() returns False when steps remain")
    else:
        err("is_finished() returned True prematurely")
except Exception as e:
    err("is_finished() raised exception", str(e))


# ── 13. Finished True ───────────────────────────────────────────────────────
section("13. finished true")
try:
    session = ts.start("KB0001")
    total_steps = ts.get_total_steps(session)
    for _ in range(total_steps - 1):
        ts.next_step(session)
        
    ts.mark_completed(session)  # Complete the final step
    if ts.is_finished(session) is True:
        ok("is_finished() returns True immediately when final step is marked completed")
    else:
        err("is_finished() returned False after last step marked completed")
except Exception as e:
    err("is_finished() validation raised exception", str(e))


# ── 14. Verification Retrieval ──────────────────────────────────────────────
section("14. verification retrieval")
try:
    session = ts.start("KB0001")
    verif = ts.get_verification(session)
    if verif and len(verif) > 0:
        ok("get_verification() retrieved verification conditions list")
    else:
        err("get_verification() returned empty list or None")
except Exception as e:
    err("get_verification() raised exception", str(e))


# ── 15. Escalation Retrieval ────────────────────────────────────────────────
section("15. escalation retrieval")
try:
    session = ts.start("KB0001")
    esc = ts.get_escalation(session)
    if esc and "team" in esc:
        ok("get_escalation() returned escalation policy details")
    else:
        err("get_escalation() returned invalid format or None")
except Exception as e:
    err("get_escalation() raised exception", str(e))


# ── 16. Invalid Session ─────────────────────────────────────────────────────
section("16. invalid session")
try:
    res1 = ts.current_step(None)
    res2 = ts.next_step(None)
    res3 = ts.previous_step(None)
    res4 = ts.is_finished(None)
    res5 = ts.get_verification(None)
    res6 = ts.get_escalation(None)
    
    if (res1 is None and 
            res2 is None and 
            res3 is None and 
            res4 is False and 
            res5 == [] and 
            res6 is None):
        ok("functions handle None session gracefully")
    else:
        err("functions failed to handle None session correctly")
except Exception as e:
    err("None session validation raised exception", str(e))


# ── 17. Invalid Article (Inside APIs) ───────────────────────────────────────
section("17. invalid article inside session")
try:
    bad_session = ts.TroubleshootingSession(article_id="KB_INVALID")
    res1 = ts.current_step(bad_session)
    res2 = ts.next_step(bad_session)
    res3 = ts.previous_step(bad_session)
    
    if res1 is None and res2 is None and res3 is None:
        ok("APIs return None gracefully for invalid article_id in session")
    else:
        err("APIs failed to return None for invalid article_id in session")
except Exception as e:
    err("invalid article_id session validation raised exception", str(e))


# ── 18. Boundary Conditions ─────────────────────────────────────────────────
section("18. boundary conditions")
try:
    session = ts.start("KB0001")
    
    # Test previous_step boundary
    res_prev = ts.previous_step(session)
    if res_prev is None and session.current_step == 1:
        ok("previous_step boundary (step 1 limit) handles correctly")
    else:
        err("previous_step allowed decrement before step 1", f"step={session.current_step}")
        
    # Test next_step boundary
    total_steps = ts.get_total_steps(session)
    for _ in range(total_steps - 1):
        ts.next_step(session)
        
    ts.mark_completed(session)
    res_next = ts.next_step(session)
    if res_next is None and session.finished is True:
        ok("next_step boundary (last step limit) handles correctly")
    else:
        err("next_step allowed increment past final step boundary")
except Exception as e:
    err("boundary conditions validation raised exception", str(e))


# ── 19. Thread-safe Concurrent Sessions ─────────────────────────────────────
section("19. thread-safe concurrent sessions")
errors = []

def run_session_thread(article_id: str, thread_id: int):
    try:
        session = ts.start(article_id)
        if not session:
            errors.append(f"Thread-{thread_id}: start() returned None")
            return
            
        # Simulate active session work
        ts.next_step(session)
        ts.mark_completed(session)
        ts.next_step(session)
        
        # Verify thread state isolation
        if session.current_step != 3:
            errors.append(f"Thread-{thread_id}: Isolated current_step mutated. Expected 3, got {session.current_step}")
        if len(session.completed_steps) != 1:
            errors.append(f"Thread-{thread_id}: Isolated completed_steps list mutated.")
    except Exception as e:
        errors.append(f"Thread-{thread_id}: Raised exception: {e}")

threads = []
for i in range(10):
    t = threading.Thread(target=run_session_thread, args=("KB0001", i))
    threads.append(t)
    t.start()

for t in threads:
    t.join()

if not errors:
    ok("thread-safe concurrent execution isolates session memory")
else:
    err("thread-safety violations observed", "; ".join(errors))


# ── 20. No Uncaught Exceptions ──────────────────────────────────────────────
section("20. no uncaught exceptions")
try:
    # Trigger all functions with empty string, missing types, invalid params
    ts.start("")
    ts.current_step(ts.TroubleshootingSession(article_id=""))
    ts.next_step(ts.TroubleshootingSession(article_id=""))
    ts.previous_step(ts.TroubleshootingSession(article_id=""))
    ts.mark_completed(None)
    ts.is_finished(None)
    ts.get_verification(None)
    ts.get_escalation(None)
    ts.reset(None)
    ts.remaining_steps(None)
    ts.current_progress(None)
    ts.restart_from_step(None, 0)
    ts.get_total_steps(None)
    ok("no uncaught exceptions raised for bad payloads")
except Exception as e:
    err("uncaught exception observed during error conditions", str(e))


# ── 21. Helpers & Step Validation (New) ──────────────────────────────────────
section("21. Helpers & Step Validation")
try:
    session = ts.start("KB0001")
    total = ts.get_total_steps(session)
    if total == 5:
        ok("get_total_steps() returned 5 for KB0001")
    else:
        err("get_total_steps() returned incorrect total steps", f"got {total}")
        
    ts.mark_completed(session)  # Complete Step 1
    rem = ts.remaining_steps(session)
    if rem == 4:
        ok("remaining_steps() returns correct remaining steps")
    else:
        err("remaining_steps() returned wrong amount", f"expected 4, got {rem}")
        
    prog = ts.current_progress(session)
    if prog == 0.20:
        ok("current_progress() returns correct progress percentage")
    else:
        err("current_progress() returned wrong percentage", f"expected 0.20, got {prog}")
        
    # Test restart_from_step
    ts.next_step(session)  # Move to step 2
    ts.mark_completed(session)  # Complete Step 2
    
    ts.restart_from_step(session, 1)
    if session.current_step == 1 and session.completed_steps == [] and session.finished is False:
        ok("restart_from_step() correctly resets step and later completions")
    else:
        err("restart_from_step() failed to reset step and completions", str(session))
        
    # Validate mark_completed step checking
    bad_sess = ts.TroubleshootingSession(article_id="KB0001", current_step=999)
    ts.mark_completed(bad_sess)
    if bad_sess.completed_steps == []:
        ok("mark_completed() rejects invalid steps that do not exist in KB")
    else:
        err("mark_completed() accepted step 999 which does not exist in KB")
except Exception as e:
    err("helper validation raised exception", str(e))


# ── End Report ──────────────────────────────────────────────────────────────
print("\n" + "=" * 50)
if failures:
    print(f"FAILED: {len(failures)} verification issues detected:")
    for f in failures:
        print(f"  {f}")
    sys.exit(1)
else:
    print("ALL TESTS PASSED - Troubleshooting Service is production ready.")
print("=" * 50)
