"""
verify_conversation_troubleshooting.py
─────────────────────────────────────────────────────────────────────────────
Sprint 2 - Verification suite for conversation troubleshooting integration.
"""

import os
import sys
import ast
import uuid
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
service_path = os.path.join("app", "services", "conversation_service.py")
try:
    with open(service_path, "r", encoding="utf-8") as f:
        ast.parse(f.read())
    ok("conversation_service.py compiles without syntax errors")
except Exception as e:
    err("conversation_service.py failed compilation", str(e))


# ── 2. Import & Setup ───────────────────────────────────────────────────────
section("2. Import & Setup")
try:
    import app.services.conversation_service as cs
    import app.services.knowledge_service as ks
    import app.services.troubleshooting_service as ts
    import app.services.approval_service as aserv
    import app.services.conversation_memory as memory
    ok("all required services imported successfully")
except Exception as e:
    err("Import failed", str(e))
    sys.exit(1)


# Setup mock DB & RAG contexts
ks.load_articles()


# ── 3. Test Start of Troubleshooting Session ───────────────────────────────
section("3. start of troubleshooting session on intent match")
try:
    # Trigger start of conversation with message matching a KB keyword
    state = cs.start_conversation("my VPN client is disconnected", "VPN")
    state = cs.conversations[state.session_id]
    
    if (state.is_troubleshooting is True and 
            state.troubleshooting_session is not None and 
            state.troubleshooting_session.article_id == "KB0002" and
            state.waiting_for_step_confirmation is True):
        ok("successfully started troubleshooting session for VPN category")
        
        # Verify first step formatted response
        first_step = state.steps[0] if state.steps else ""
        if "Step 1" in first_step and "Have you completed this step?" in first_step:
            ok("first step is correctly formatted and asks 'Have you completed this step?'")
        else:
            err("first step formatted response is incorrect", first_step)
    else:
        err("failed to auto-launch troubleshooting session", f"is_tb={state.is_troubleshooting}")
except Exception as e:
    err("start of troubleshooting session raised exception", str(e))


# ── 4. Test Step Advancement on Approval ─────────────────────────────────────
section("4. step advancement on yes / completion confirmation")
try:
    session_id = str(uuid.uuid4())
    # Start fresh session manually matching VPN
    state = cs.ConversationState(session_id, "VPN", "VPN not connecting")
    state.conversation_history = []
    cs.conversations[session_id] = state
    
    session = ts.start("KB0002")
    state.troubleshooting_session = session
    state.is_troubleshooting = True
    state.waiting_for_step_confirmation = True
    
    # User responds "Yes" to Step 1 (Open GlobalProtect)
    res = cs.handle_chat_turn(session_id, "yes")
    state = cs.conversations[session_id]
    
    # Troubleshooting session should be on Step 2
    if state.troubleshooting_session.current_step == 2:
        ok("successfully marked Step 1 completed and advanced to Step 2")
    else:
        err("failed to advance step", f"current_step={state.troubleshooting_session.current_step}")
        
    if "Step 2" in res["response"] and "Did that work?" in res["response"]:
        ok("Step 2 response formatted and asks 'Did that work?'")
    else:
        err("Step 2 response formatting is incorrect", res["response"])
except Exception as e:
    err("step advancement verification raised exception", str(e))


# ── 5. Test Step Transition on Verification Failure (No / Still not working) ─
section("5. step transition on verification failure ('Still not working')")
try:
    session_id = str(uuid.uuid4())
    state = cs.ConversationState(session_id, "VPN", "VPN not connecting")
    state.conversation_history = []
    cs.conversations[session_id] = state
    
    session = ts.start("KB0002")
    state.troubleshooting_session = session
    state.is_troubleshooting = True
    state.waiting_for_step_confirmation = True
    
    # Complete Step 1
    cs.handle_chat_turn(session_id, "yes")
    
    # We are now at Step 2 (Click Connect). User responds "Still not working"
    res = cs.handle_chat_turn(session_id, "still not working")
    state = cs.conversations[session_id]
    
    if state.troubleshooting_session.current_step == 3:
        ok("successfully advanced to Step 3 after user replied 'still not working'")
    else:
        err("failed to advance step on verification failure", f"current_step={state.troubleshooting_session.current_step}")
except Exception as e:
    err("step transition verification raised exception", str(e))


# ── 6. Test Final Step Completion & Verification ────────────────────────────
section("6. final step completion and verification question prompt")
try:
    session_id = str(uuid.uuid4())
    state = cs.ConversationState(session_id, "VPN", "VPN not connecting")
    state.conversation_history = []
    cs.conversations[session_id] = state
    
    session = ts.start("KB0002")
    state.troubleshooting_session = session
    state.is_troubleshooting = True
    state.waiting_for_step_confirmation = True
    
    total_steps = ts.get_total_steps(session)
    # Step 1: "Have you completed this step?" -> reply "yes"
    cs.handle_chat_turn(session_id, "yes")
    # Steps 2, 3, 4: "Did that work?" -> reply "no" to continue
    for _ in range(total_steps - 2):
        cs.handle_chat_turn(session_id, "no")
        
    # We are on Step 5. User replies "still not working" to Step 5
    res = cs.handle_chat_turn(session_id, "still not working")
    state = cs.conversations[session_id]
    
    if (state.waiting_for_step_confirmation is False and 
            state.waiting_for_solution_verification is True and
            state.troubleshooting_session.finished is True):
        ok("successfully completed the last step and transitioned to waiting_for_solution_verification")
        
        # Verify verification question prompt
        if "guided you through all" in res["response"]:
            ok("successfully prompted the correct verification question")
        else:
            err("incorrect verification question response", res["response"])
    else:
        err("failed final step completion transitions", f"finished={state.troubleshooting_session.finished}")
except Exception as e:
    err("final step verification raised exception", str(e))


# ── 7. Test Ticket Creation on Approval ─────────────────────────────────────
section("7. ticket creation on verification failure + approval")
try:
    session_id = str(uuid.uuid4())
    state = cs.ConversationState(session_id, "VPN", "VPN not connecting")
    state.conversation_history = []
    cs.conversations[session_id] = state
    
    session = ts.start("KB0002")
    state.troubleshooting_session = session
    state.is_troubleshooting = True
    state.waiting_for_solution_verification = True  # Setup state at verification step
    
    # User replies "no" to verification question (it did not solve it)
    res1 = cs.handle_chat_turn(session_id, "no")
    state = cs.conversations[session_id]
    
    if (state.waiting_for_solution_verification is False and 
            state.waiting_for_ticket_confirmation is True and
            "create a ServiceNow ticket" in res1["response"]):
        ok("correctly asked permission to create a ServiceNow ticket")
        
        # User responds "yes" to ticket permission question
        res2 = cs.handle_chat_turn(session_id, "yes")
        state = cs.conversations[session_id]
        
        if (state.status == "TICKET_CREATED" and 
                state.is_troubleshooting is False and 
                res2["ticket_created"] is True and
                res2["ticket_id"] is not None):
            ok(f"successfully created ticket {res2['ticket_id']} and transitioned status to TICKET_CREATED")
        else:
            err("failed to create ticket or transition status correctly", f"status={state.status}")
    else:
        err("failed ticket permission prompt verification")
except Exception as e:
    err("ticket creation verification raised exception", str(e))


# ── 8. Test Reject Ticket Creation (Conversation Continues) ─────────────────
section("8. conversation continues if user rejects ticket creation")
try:
    session_id = str(uuid.uuid4())
    state = cs.ConversationState(session_id, "VPN", "VPN not connecting")
    state.conversation_history = []
    cs.conversations[session_id] = state
    
    session = ts.start("KB0002")
    state.troubleshooting_session = session
    state.is_troubleshooting = True
    state.waiting_for_ticket_confirmation = True
    
    # User responds "no" to ticket permission question
    res = cs.handle_chat_turn(session_id, "no")
    state = cs.conversations[session_id]
    
    if (state.is_troubleshooting is False and 
            state.waiting_for_ticket_confirmation is False and 
            state.status == "ACTIVE"):
        ok("successfully reset troubleshooting and let the conversation continue")
    else:
        err("failed to reset troubleshooting on ticket rejection", f"is_tb={state.is_troubleshooting}")
except Exception as e:
    err("reject ticket verification raised exception", str(e))


# ── 9. Test Category Switch Resets Session ──────────────────────────────────
section("9. category switch resets troubleshooting session")
try:
    session_id = str(uuid.uuid4())
    state = cs.ConversationState(session_id, "VPN", "VPN not connecting")
    state.conversation_history = []
    cs.conversations[session_id] = state
    
    session = ts.start("KB0002")
    state.troubleshooting_session = session
    state.is_troubleshooting = True
    state.waiting_for_step_confirmation = True
    
    # User switches category by saying "printer is not working"
    res = cs.handle_chat_turn(session_id, "printer is not working")
    state = cs.conversations[session_id]
    
    # Verify that the session category switched to PRINTER and troubleshooting is running for printer
    if (state.category == "PRINTER" and 
            state.is_troubleshooting is True and 
            state.troubleshooting_session.article_id == "KB0007" and
            "Step 1" in res["response"] and "printer" in res["response"].lower()):
        ok("successfully reset VPN session and launched new PRINTER troubleshooting session")
    else:
        err("category switch failed to reset or start new troubleshooting session", f"cat={state.category}")
except Exception as e:
    err("category switch verification raised exception", str(e))


# ── End Report ──────────────────────────────────────────────────────────────
print("\n" + "=" * 60)
if failures:
    print(f"FAILED: {len(failures)} verification issues detected:")
    for f in failures:
        print(f"  {f}")
    sys.exit(1)
else:
    print("ALL TESTS PASSED - Conversation Troubleshooting integration is production ready.")
print("=" * 60)
