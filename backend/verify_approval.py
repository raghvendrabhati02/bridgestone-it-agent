"""
Verify approval_service parser functionality.
"""
import ast
import sys

# 1. AST check
ast.parse(open('app/services/approval_service.py', encoding='utf-8').read())
print("AST OK")

# 2. Imports check
from app.services.approval_service import ApprovalStatus, ApprovalResult, detect_approval

# 3. Test explicit approvals
res1 = detect_approval("yes, please do it.")
assert res1.status == ApprovalStatus.APPROVED
assert res1.confidence >= 0.95
assert res1.matched_phrase == "please do"
print("Explicit approval test (please do): OK")

res2 = detect_approval("go ahead")
assert res2.status == ApprovalStatus.APPROVED
assert res2.confidence >= 0.95
assert res2.matched_phrase == "go ahead"
print("Explicit approval test (go ahead): OK")

# 4. Test weak approvals
res3 = detect_approval("ok, thanks.")
assert res3.status == ApprovalStatus.APPROVED
assert 0.70 <= res3.confidence <= 0.90
assert res3.matched_phrase == "ok"
print("Weak approval test (ok): OK")

res4 = detect_approval("yep")
assert res4.status == ApprovalStatus.APPROVED
assert res4.confidence == 0.90
assert res4.matched_phrase == "yep"
print("Weak approval test (yep): OK")

# 5. Test explicit rejections
res5 = detect_approval("no way, please stop!")
assert res5.status == ApprovalStatus.REJECTED
assert res5.confidence >= 0.95
assert res5.matched_phrase in ("no", "stop")
print("Explicit rejection test (no/stop): OK")

res6 = detect_approval("never mind")
assert res6.status == ApprovalStatus.REJECTED
assert res6.confidence >= 0.95
assert res6.matched_phrase == "never mind"
print("Explicit rejection test (never mind): OK")

# 6. Test ambiguous responses (must be UNKNOWN and 0.0 confidence)
res7 = detect_approval("thank you very much")
assert res7.status == ApprovalStatus.UNKNOWN
assert res7.confidence == 0.0
print("Ambiguous reply test (thank you): OK")

res8 = detect_approval("not sure, maybe")
assert res8.status == ApprovalStatus.UNKNOWN
assert res8.confidence == 0.0
print("Ambiguous reply test (not sure/maybe): OK")

res9 = detect_approval("hello there")
assert res9.status == ApprovalStatus.UNKNOWN
assert res9.confidence == 0.0
print("Ambiguous reply test (hello): OK")

print("\nAll approval checks passed.")
