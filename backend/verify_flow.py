"""
Verify conversation_flow functionality.
"""
import ast
import sys

# 1. AST check
ast.parse(open('app/services/conversation_flow.py', encoding='utf-8').read())
print("AST OK")

# 2. Imports check
from app.services.conversation_flow import (
    ConversationStage,
    ConversationFlowState,
    create_flow,
    move_to_stage,
    can_execute_action,
    should_create_ticket,
    increment_attempt,
    mark_resolved,
    mark_escalated,
    reset,
)

# 3. Test initial flow creation
session_id = "test-session-123"
state = create_flow(session_id, "VPN", max_attempts=3)
assert state.conversation_id == session_id
assert state.stage == ConversationStage.NEW
assert state.issue_category == "VPN"
assert state.attempt_number == 0
assert state.issue_resolved is False
print("create_flow: OK")

# 4. Test state transitions
# Valid transition: NEW -> UNDERSTANDING
move_to_stage(state, ConversationStage.UNDERSTANDING)
assert state.stage == ConversationStage.UNDERSTANDING

# Invalid transition: UNDERSTANDING -> RESOLVED (should raise ValueError)
try:
    move_to_stage(state, ConversationStage.RESOLVED)
    assert False, "Should have raised ValueError on invalid transition"
except ValueError as e:
    print("Invalid transition check: OK (raised expected error)")

# Valid transition sequence: UNDERSTANDING -> TROUBLESHOOTING -> WAITING_CONFIRMATION
move_to_stage(state, ConversationStage.TROUBLESHOOTING)
move_to_stage(state, ConversationStage.WAITING_CONFIRMATION)
assert state.stage == ConversationStage.WAITING_CONFIRMATION
print("Valid transition sequence: OK")

# 5. Action Execution Guard (can_execute_action)
# Awaiting confirmation, but no approval yet
assert can_execute_action(state, approval_received=False) is False
# Awaiting confirmation and approved
assert can_execute_action(state, approval_received=True) is True

# Not in WAITING_CONFIRMATION stage
state.stage = ConversationStage.TROUBLESHOOTING
assert can_execute_action(state, approval_received=True) is False
print("can_execute_action: OK")

# 6. Ticket Escalation Guard (should_create_ticket)
state.stage = ConversationStage.TROUBLESHOOTING
assert should_create_ticket(state, employee_approved=True) is False  # attempts = 0

increment_attempt(state)  # 1
increment_attempt(state)  # 2
increment_attempt(state)  # 3 (reached max_attempts=3)

# Attempts = 3, but no employee approval
assert should_create_ticket(state, employee_approved=False) is False
# Attempts = 3, and employee approved
assert should_create_ticket(state, employee_approved=True) is True

# If issue is already marked resolved
state.issue_resolved = True
assert should_create_ticket(state, employee_approved=True) is False
print("should_create_ticket: OK")

# 7. Mark resolved / escalated
state2 = create_flow("test-2")
mark_resolved(state2)
assert state2.stage == ConversationStage.RESOLVED
assert state2.issue_resolved is True

state3 = create_flow("test-3")
# Must transition state3 NEW -> UNDERSTANDING -> TROUBLESHOOTING to validly move to ESCALATED
move_to_stage(state3, ConversationStage.UNDERSTANDING)
move_to_stage(state3, ConversationStage.TROUBLESHOOTING)
mark_escalated(state3)
assert state3.stage == ConversationStage.ESCALATED
assert state3.ticket_created is True
print("mark_resolved / mark_escalated: OK")

# 8. Reset
reset(state2)
assert state2.stage == ConversationStage.NEW
assert state2.attempt_number == 0
assert state2.issue_resolved is False
print("reset: OK")

print("\nAll flow checks passed.")
