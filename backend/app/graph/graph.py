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

# Context Router: ticket_status or full troubleshoot pipeline
workflow.add_conditional_edges(
    "context_router",
    lambda state: state.get("route", "intent"),
    {
        "ticket_status": "ticket_status",
        "intent":        "intent",
    },
)

# Conversation path ends immediately
workflow.add_edge("conversation", END)

# Full troubleshoot pipeline: Intent → Planner → Knowledge → Tool → RootCause → Reflection → Decision
workflow.add_edge("intent",      "planner")
workflow.add_edge("planner",     "knowledge")
workflow.add_edge("knowledge",   "tool")
workflow.add_edge("tool",        "root_cause")
workflow.add_edge("root_cause",  "reflection")
workflow.add_edge("reflection",  "decision")
workflow.add_edge("ticket_status", END)

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

# ── Ticket path: ticket → ticket_lifecycle → assignment → notification → sla → END ──
workflow.add_edge("ticket",           "ticket_lifecycle")  # lifecycle inserted here
workflow.add_edge("ticket_lifecycle", "assignment")
workflow.add_edge("assignment",       "notification")
workflow.add_edge("action",           "notification")
workflow.add_edge("notification",     "sla")
workflow.add_edge("sla",              END)

# ── Compile ───────────────────────────────────────────────────────────────────
app_graph = workflow.compile()
logger.info(
    "LangGraph workflow compiled successfully. "
    "Pipeline: Router → (Conversation | Memory → Context Router) → "
    "(Ticket Status | Intent → Planner → Knowledge → Tool → "
    "RootCause → Reflection → Decision → (Approval → Action | Ticket → Lifecycle → Assignment))"
)