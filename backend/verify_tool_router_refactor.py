import ast, os, sys

# 1. AST check all handler files + router
targets = []
handler_dir = "app/services/handlers"
for f in sorted(os.listdir(handler_dir)):
    if f.endswith(".py"):
        targets.append(os.path.join(handler_dir, f))
targets.append("app/services/tool_router.py")

errors = []
for path in targets:
    try:
        ast.parse(open(path, encoding="utf-8").read())
        print(f"AST OK  {path}")
    except SyntaxError as e:
        errors.append(f"SYNTAX ERROR in {path}: {e}")
        print(f"FAIL    {path}: {e}")

if errors:
    sys.exit(1)

# 2. Import tool_router and verify routing table
import app.services.tool_router as tr

tools = tr.supported_tools()
print(f"\nTools registered: {len(tools)}")
for t in tools:
    print(f"  {t}")

expected = {
    "INSTALL_SOFTWARE", "CREATE_TICKET", "ESCALATE_TO_HUMAN",
    "VPN_ACCESS_RESTORE", "CHECK_VPN_STATUS",
    "CHECK_DEVICE_STATUS", "RESTART_SERVICE", "CHECK_OUTLOOK", "CHECK_DEVICE_HEALTH",
    "RESET_PASSWORD", "SEARCH_KNOWLEDGE_BASE",
}
missing = expected - set(tools)
if missing:
    print(f"\nMISSING tools: {missing}")
    sys.exit(1)

# 3. Live route test (SEARCH_KNOWLEDGE_BASE — no external deps)
result = tr.route({"tool": "SEARCH_KNOWLEDGE_BASE", "parameters": {"category": "VPN"}})
assert result["status"] == "SUCCESS", f"Unexpected status: {result['status']}"
assert result["tool"] == "SEARCH_KNOWLEDGE_BASE"
print(f"\nLive route test: status={result['status']} tool={result['tool']}")

# 4. Unknown tool returns ERROR, not exception
bad = tr.route({"tool": "DOES_NOT_EXIST", "parameters": {}})
assert bad["status"] == "ERROR"
print(f"Unknown tool test: status={bad['status']}")

print("\nAll checks passed.")
