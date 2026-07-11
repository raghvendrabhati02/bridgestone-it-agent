import ast, sys

# 1. AST check
for f in ['app/services/orchestrator_service.py', 'app/services/prompt_builder.py']:
    ast.parse(open(f, encoding='utf-8').read())
    print('AST OK:', f)

# 2. PromptBuilder new function
from app.services.prompt_builder import build_decision_prompt
dp = build_decision_prompt('VPN')
assert 'JSON' in dp and 'assistant_message' in dp and 'VPN' in dp
print('build_decision_prompt(VPN): OK  len=%d' % len(dp))
dp2 = build_decision_prompt('UNKNOWN_CAT')
assert 'JSON' in dp2
print('build_decision_prompt(UNKNOWN_CAT): OK  len=%d (GENERAL fallback)' % len(dp2))

# 3. OrchestratorService helpers
import app.services.orchestrator_service as orch

valid_dict = {
    "assistant_message": "Hello",
    "intent": "GENERAL_SUPPORT",
    "tool": None,
    "parameters": {},
    "confidence": 0.9,
    "requires_confirmation": False,
}
import json
clean = json.dumps(valid_dict)
fenced = "```json\n" + clean + "\n```"
prose  = "Sure:\n" + clean + "\nEnd."

for label, raw in [("clean", clean), ("fenced", fenced), ("prose", prose)]:
    r = orch._extract_json(raw)
    assert r is not None and r["intent"] == "GENERAL_SUPPORT", f"FAIL {label}"
    print("_extract_json(%s): OK" % label)

# 4. _validate_decision
good = {"assistant_message": "Test", "intent": "VPN_ACCESS_RESTORE",
        "tool": "VPN_ACCESS_RESTORE", "parameters": {"detail": "x"},
        "confidence": 1.5, "requires_confirmation": True}
v = orch._validate_decision(good)
assert v["confidence"] == 1.0, "should clamp to 1.0"
assert v["intent"] == "VPN_ACCESS_RESTORE"
print("_validate_decision (confidence clamp): OK")

bad = {"assistant_message": "Test", "intent": "MADE_UP",
       "tool": None, "parameters": {}, "confidence": 0.5, "requires_confirmation": False}
v2 = orch._validate_decision(bad)
assert v2["intent"] == "UNKNOWN"
print("_validate_decision (unknown intent -> UNKNOWN): OK")

# 5. Fallback
fb = orch._fallback_decision("VPN")
assert fb["_fallback"] is True and fb["intent"] == "GENERAL_SUPPORT"
print("_fallback_decision: OK")

print("\nAll checks passed.")
