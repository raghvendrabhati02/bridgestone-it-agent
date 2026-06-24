from typing import TypedDict, List, Dict, Any, Optional

class AgentState(TypedDict):
    """
    State definition for the IT support agent orchestrator graph.
    """
    session_id: str
    user_message: str
    category: str
    knowledge_context: str
    tool_result: Dict[str, Any]
    plan: Dict[str, Any]
    # ── Root Cause Agent output ────────────────────────────────────────────────
    # Populated by root_cause_node; consumed by reflection_node and decision_node.
    root_cause_analysis: Optional[Dict[str, Any]]
    # ── Reflection Agent output ────────────────────────────────────────────────
    # Populated by reflection_node; consumed by decision_node and response_agent.
    reflection: Optional[Dict[str, Any]]
    # ── Memory Agent output ────────────────────────────────────────────────────
    # Populated by memory_node; consumed by ticket_node, ticket_status_node.
    memory: Optional[Dict[str, Any]]
    # ── Approval Agent output ──────────────────────────────────────────────────
    # Populated by approval_node.
    # approval_required : True when the recommended action is privileged.
    # approval_status   : PENDING | APPROVED | REJECTED
    # approval_action   : dict describing the action awaiting approval.
    approval_action: Optional[Dict[str, Any]]
    # ── Ticket Lifecycle Agent output ──────────────────────────────────────────
    # Populated by ticket_lifecycle_node; reflects current lifecycle state machine.
    # Schema: { "ticket_id": str, "state": str, "history": [...], ... }
    ticket_lifecycle: Optional[Dict[str, Any]]
    # ──────────────────────────────────────────────────────────────────────────
    decision: str
    decision_response: str
    approval_required: bool
    approval_status: str
    recommended_action: str
    action_result: Dict[str, Any]
    ticket: Dict[str, Any]
    assigned_team: str
    notifications: List[Dict[str, Any]]
    sla: Dict[str, Any]
    username: str
    active_issue: str
    active_ticket: str
    active_request: str
    conversation_goal: str
    last_action: str
    route: str

