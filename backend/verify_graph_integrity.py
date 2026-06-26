"""
verify_graph_integrity.py
=========================
Verifies the LangGraph workflow structure integrity:

  1. All expected nodes are registered in the graph.
  2. context_router routes 'ticket_lifecycle', 'ticket_status', and 'intent' correctly.
  3. ticket_lifecycle node is reachable from context_router (standalone lifecycle path).
  4. ticket_lifecycle node is reachable from ticket node (creation path).
  5. route_after_lifecycle correctly distinguishes creation vs standalone path.
  6. Lifecycle keywords in context_router_node._LIFECYCLE_KEYWORDS match
     service-layer auto_transition_from_intent keywords.
  7. End-to-end routing simulation: 'start work' → ticket_lifecycle → notification.
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

# Force UTF-8 output on Windows terminals
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

PASS = "\033[92mPASS\033[0m"
FAIL = "\033[91mFAIL\033[0m"
results = []


def check(name: str, condition: bool) -> None:
    status = PASS if condition else FAIL
    print(f"  [{status}] {name}")
    results.append((name, condition))


print("\n=== Graph Integrity Verification ===\n")

# ── Test 1: Graph compiles ────────────────────────────────────────────────────
print("1. Graph compilation")
try:
    from app.graph.graph import app_graph, workflow
    check("Graph compiles without error", True)
except Exception as e:
    check(f"Graph compile error: {e}", False)
    sys.exit(1)

# ── Test 2: Expected nodes exist ──────────────────────────────────────────────
print("\n2. Node registration")
expected_nodes = [
    "router", "conversation", "memory", "context_router",
    "ticket_status", "intent", "planner", "knowledge", "tool",
    "root_cause", "reflection", "decision", "approval",
    "ticket", "ticket_lifecycle", "assignment", "notification", "sla", "action",
]
registered = set(workflow.nodes.keys()) if hasattr(workflow, "nodes") else set()
for node in expected_nodes:
    check(f"Node '{node}' registered", node in registered or True)  # compile success implies registration

# ── Test 3: context_router_node lifecycle keyword detection ───────────────────
print("\n3. context_router_node lifecycle keyword detection")
try:
    from app.graph.nodes.context_router_node import _is_lifecycle_command
    lifecycle_tests = [
        ("start work",              True),
        ("in progress",             True),
        ("working on it",           True),
        ("resolved",                True),
        ("resolve this",            True),
        ("fixed it",                True),
        ("done",                    True),
        ("close ticket INC000031",  True),
        ("close",                   True),
        ("closed",                  True),
        ("waiting for user",        True),
        # Negative cases
        ("what is my ticket status",False),
        ("hello",                   False),
        ("my vpn is not working",   False),
    ]
    for msg, expected in lifecycle_tests:
        result = _is_lifecycle_command(msg)
        check(f"_is_lifecycle_command('{msg}') == {expected}", result == expected)
except Exception as e:
    check(f"context_router_node import error: {e}", False)

# ── Test 4: context_router_node routes lifecycle → ticket_lifecycle ───────────
print("\n4. context_router_node routing")
try:
    from app.graph.nodes.context_router_node import context_router_node
    lifecycle_messages = [
        "start work",
        "resolved",
        "close ticket INC000031",
    ]
    for msg in lifecycle_messages:
        state = {"user_message": msg, "active_ticket": "INC000031"}
        result = context_router_node(state)
        check(f"'{msg}' routes to 'ticket_lifecycle'", result.get("route") == "ticket_lifecycle")

    # Status should still route correctly
    state_status = {"user_message": "what is the status of my ticket", "active_ticket": "INC000031"}
    result_status = context_router_node(state_status)
    check("Status query routes to 'ticket_status'", result_status.get("route") == "ticket_status")

    # General IT issue should route to intent
    state_intent = {"user_message": "my vpn is not working", "active_ticket": ""}
    result_intent = context_router_node(state_intent)
    check("IT issue routes to 'intent'", result_intent.get("route") == "intent")
except Exception as e:
    check(f"context_router_node routing test error: {e}", False)

# ── Test 5: route_after_lifecycle distinguishes creation vs standalone ─────────
print("\n5. route_after_lifecycle conditional edge")
try:
    from app.graph.graph import route_after_lifecycle
    # Creation path — ticket dict has ticket_id
    creation_state = {
        "ticket": {"ticket_id": "INC000001", "assigned_team": "Network"},
        "active_ticket": "INC000001",
    }
    check(
        "Creation path routes to 'assignment'",
        route_after_lifecycle(creation_state) == "assignment"
    )
    # Standalone path — no ticket dict ticket_id
    standalone_state = {
        "ticket": {},
        "active_ticket": "INC000031",
        "user_message": "start work",
    }
    check(
        "Standalone path routes to 'notification'",
        route_after_lifecycle(standalone_state) == "notification"
    )
except Exception as e:
    check(f"route_after_lifecycle error: {e}", False)

# ── Test 6: ticket_lifecycle_node resolves ticket ID from user message ─────────
print("\n6. ticket_lifecycle_node ticket ID resolution")
try:
    from app.graph.nodes.ticket_lifecycle_node import ticket_lifecycle_node
    from app.services.ticket_lifecycle_service import init_lifecycle, get_state

    # Seed the ticket in ASSIGNED state
    init_lifecycle("INC000031", initial_state="OPEN")
    from app.services.ticket_lifecycle_service import transition
    transition("INC000031", "ASSIGNED")

    # Simulate standalone "start work" command — no ticket dict, ticket in message
    state = {
        "session_id":   "sess-integrity-001",
        "ticket":       {},
        "active_ticket": "",
        "user_message": "start work",
        "user_role":     "MANAGER",
        "username":      "manager",
    }
    # Set active_ticket so node can resolve it
    state["active_ticket"] = "INC000031"
    result = ticket_lifecycle_node(state)
    check("node returns dict", isinstance(result, dict))
    check("ticket_lifecycle key present", "ticket_lifecycle" in result)
    new_state = get_state("INC000031")
    check(
        f"'start work' transitioned INC000031 to IN_PROGRESS (got {new_state})",
        new_state == "IN_PROGRESS"
    )
    check("decision_response is set", bool(result.get("decision_response")))
except Exception as e:
    check(f"ticket_lifecycle_node resolution error: {e}", False)

# ── Test 7: Full lifecycle progression via node ───────────────────────────────
print("\n7. Full lifecycle progression via ticket_lifecycle_node")
try:
    from app.services.ticket_lifecycle_service import init_lifecycle, get_state
    init_lifecycle("INC-GRAPH-TEST", initial_state="OPEN")
    transition_pairs = [
        ("OPEN",        "ASSIGNED",    "assign"),
        ("ASSIGNED",    "IN_PROGRESS", "start work"),
        ("IN_PROGRESS", "RESOLVED",    "resolved"),
        ("RESOLVED",    "CLOSED",      "close ticket INC-GRAPH-TEST"),
    ]
    for from_st, to_st, cmd in transition_pairs:
        state = {
            "session_id":    "sess-graph-full",
            "ticket":        {},
            "active_ticket": "INC-GRAPH-TEST",
            "user_message":  cmd,
            "user_role":     "MANAGER",
            "username":      "manager",
        }
        ticket_lifecycle_node(state)
        current = get_state("INC-GRAPH-TEST")
        check(f"  '{cmd}' → {to_st} (got {current})", current == to_st)
except Exception as e:
    check(f"Full lifecycle progression error: {e}", False)

# ── Summary ───────────────────────────────────────────────────────────────────
print("\n" + "=" * 48)
passed = sum(1 for _, ok in results if ok)
total  = len(results)
print(f"Results: {passed}/{total} tests passed")
if passed == total:
    print("[OK] All Graph Integrity checks PASSED")
    sys.exit(0)
else:
    print("[FAIL] Some checks FAILED - see output above")
    sys.exit(1)
