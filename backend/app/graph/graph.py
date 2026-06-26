import logging
from langgraph.graph import END, StateGraph
from app.graph.state import AgentState
from app.graph.nodes.context_router_node import context_router_node
from app.graph.nodes.ticket_status_node import ticket_status_node
from app.graph.nodes.planner_node import planner_node
from app.graph.nodes.root_cause_node import root_cause_node
from app.graph.nodes.memory_node import memory_node
from app.graph.nodes.approval_node import approval_node
from app.graph.nodes.ticket_lifecycle_node import ticket_lifecycle_node
from app.graph.nodes import (
    intent_node,
    knowledge_node,
    tool_node,
    reflection_node,
    decision_node,
    ticket_node,
    assignment_node,
    notification_node,
    sla_node,
    action_node,
    router_node,
    conversation_node,
    service_request_node,
    diagnostic_interview_node,
    multi_step_node,
)

logger = logging.getLogger("it-agent-backend")

# ── Routing functions ─────────────────────────────────────────────────────────

def route_after_router(state: AgentState) -> str:
    """Conditional routing after the router node."""
    decision = state.get("decision", "TROUBLESHOOT").upper().strip()
    logger.info("Graph Router: Evaluating post-router routing. Decision is '%s'", decision)
    if decision == "CHAT":
        logger.info("Graph Router: Routing to 'conversation' node.")
        return "conversation"
    logger.info("Graph Router: Routing to 'memory' node → context_router.")
    return "memory"


def route_decision(state: AgentState) -> str:
    """Conditional routing after the decision node."""
    decision = state.get("decision", "ASK_MORE_INFO").upper().strip()
    logger.info("Graph Router: Evaluating decision routing. Decision is '%s'", decision)
    if decision == "CREATE_TICKET":
        logger.info("Graph Router: Routing to 'ticket' node.")
        return "ticket"
    elif decision == "EXECUTE_ACTION":
        # Always pass through approval gate first
        logger.info("Graph Router: Routing to 'approval' node before action.")
        return "approval"
    logger.info("Graph Router: Routing to END.")
    return END


def route_after_approval(state: AgentState) -> str:
    """Conditional routing after the approval node."""
    approval_status = (state.get("approval_status") or "PENDING").upper().strip()
    decision = (state.get("decision") or "").upper().strip()

    logger.info(
        "Graph Router: Approval gate — approval_status='%s' decision='%s'",
        approval_status, decision,
    )

    if approval_status == "APPROVED" and decision == "EXECUTE_ACTION":
        logger.info("Graph Router: Approval APPROVED. Routing to 'action' node.")
        return "action"

    # PENDING or REJECTED → end the turn; the response has already been set
    logger.info(
        "Graph Router: Approval status is '%s'. Routing to END.", approval_status
    )
    return END


def route_after_diagnostic_interview(state: AgentState) -> str:
    """Conditional routing after the diagnostic interview node."""
    if state.get("decision_response"):
        logger.info("Graph Router: Diagnostic interview asked questions. Short-circuiting to END.")
        return END
    logger.info("Graph Router: Proceeding from Diagnostic interview to Planner.")
    return "planner"


def route_after_multi_step(state: AgentState) -> str:
    """Conditional routing after the multi_step node."""
    complete = state.get("troubleshooting_complete", False)
    next_tool = state.get("next_tool")
    if not complete and next_tool:
        logger.info("Graph Router: More tools needed (%s). Routing back to 'tool'.", next_tool)
        return "tool"
    logger.info("Graph Router: Troubleshooting complete. Routing to 'root_cause'.")
    return "root_cause"



# ── Build graph ────────────────────────────────────────────────────────────────

workflow = StateGraph(AgentState)

# ── Add all nodes ─────────────────────────────────────────────────────────────
workflow.add_node("router",           router_node)
workflow.add_node("conversation",     conversation_node)
workflow.add_node("memory",           memory_node)
workflow.add_node("intent",           intent_node)
workflow.add_node("planner",          planner_node)
workflow.add_node("knowledge",        knowledge_node)
workflow.add_node("tool",             tool_node)
workflow.add_node("diagnostic_interview", diagnostic_interview_node)
workflow.add_node("multi_step",           multi_step_node)
workflow.add_node("root_cause",       root_cause_node)
workflow.add_node("reflection",       reflection_node)
workflow.add_node("decision",         decision_node)
workflow.add_node("approval",         approval_node)           # NEW
workflow.add_node("ticket",           ticket_node)
workflow.add_node("ticket_lifecycle", ticket_lifecycle_node)   # NEW
workflow.add_node("assignment",       assignment_node)
workflow.add_node("notification",     notification_node)
workflow.add_node("sla",              sla_node)
workflow.add_node("action",           action_node)
workflow.add_node("context_router",   context_router_node)
workflow.add_node("ticket_status",    ticket_status_node)
workflow.add_node("service_request",  service_request_node)

# ── Entry point ───────────────────────────────────────────────────────────────
workflow.set_entry_point("router")
workflow.add_conditional_edges(
    "router",
    route_after_router,
    {
        "conversation": "conversation",
        "memory":       "memory",
    },
)

# Memory → Context Router
workflow.add_edge("memory", "context_router")

# Context Router: ticket_lifecycle | ticket_status | service_request | full troubleshoot pipeline
workflow.add_conditional_edges(
    "context_router",
    lambda state: state.get("route", "intent"),
    {
        "ticket_lifecycle": "ticket_lifecycle",
        "ticket_status":    "ticket_status",
        "service_request":  "service_request",
        "intent":           "intent",
    },
)

# Conversation path ends immediately
workflow.add_edge("conversation", END)

# Full troubleshoot pipeline: Intent → Diagnostic Interview → Planner → Knowledge → Tool → MultiStep → Loop/RootCause → Reflection → Decision
workflow.add_edge("intent", "diagnostic_interview")

workflow.add_conditional_edges(
    "diagnostic_interview",
    route_after_diagnostic_interview,
    {
        "planner": "planner",
        END: END,
    },
)

workflow.add_edge("planner",     "knowledge")
workflow.add_edge("knowledge",   "tool")
workflow.add_edge("tool",        "multi_step")

workflow.add_conditional_edges(
    "multi_step",
    route_after_multi_step,
    {
        "tool": "tool",
        "root_cause": "root_cause",
    },
)

workflow.add_edge("root_cause",  "reflection")
workflow.add_edge("reflection",  "decision")
workflow.add_edge("ticket_status", END)
workflow.add_edge("service_request", END)

# Decision conditional routing
workflow.add_conditional_edges(
    "decision",
    route_decision,
    {
        "ticket":   "ticket",
        "approval": "approval",          # EXECUTE_ACTION now goes through approval gate
        END:        END,
    },
)

# ── Approval gate ─────────────────────────────────────────────────────────────
workflow.add_conditional_edges(
    "approval",
    route_after_approval,
    {
        "action": "action",
        END:      END,
    },
)

# ── Ticket creation path: ticket → ticket_lifecycle → assignment → notification → sla → END ──
workflow.add_edge("ticket",           "ticket_lifecycle")  # lifecycle inserted here

# ticket_lifecycle has TWO callers:
#   a) ticket creation  → continues to assignment → notification → sla → END
#   b) standalone lifecycle command (from context_router) → goes to notification → END
# We use a conditional edge to distinguish these two cases.
def route_after_lifecycle(state: AgentState) -> str:
    """If a ticket was just created (ticket dict has ticket_id), go to assignment.
    If it is a standalone lifecycle command, skip assignment and go straight to notification."""
    ticket = state.get("ticket") or {}
    if ticket.get("ticket_id"):
        logger.info("Graph Router: ticket_lifecycle → assignment (ticket creation path).")
        return "assignment"
    logger.info("Graph Router: ticket_lifecycle → notification (standalone lifecycle path).")
    return "notification"

workflow.add_conditional_edges(
    "ticket_lifecycle",
    route_after_lifecycle,
    {
        "assignment":   "assignment",
        "notification": "notification",
    },
)

workflow.add_edge("assignment",   "notification")
workflow.add_edge("action",       "notification")
workflow.add_edge("notification", "sla")
workflow.add_edge("sla",          END)

# ── Compile ───────────────────────────────────────────────────────────────────
app_graph = workflow.compile()
logger.info(
    "LangGraph workflow compiled successfully. "
    "Pipeline: Router → (Conversation | Memory → Context Router) → "
    "(Ticket Status | Intent → Planner → Knowledge → Tool → "
    "RootCause → Reflection → Decision → (Approval → Action | Ticket → Lifecycle → Assignment))"
)