"""
Approval Node
=============
Sits between decision_node and action_node.

Routing logic:
  • If the action is NOT privileged       → pass straight through (decision = EXECUTE_ACTION)
  • If privileged and NOT yet approved   → set approval_status = PENDING, return REQUEST_APPROVAL
  • If privileged and APPROVED           → let the action proceed (decision = EXECUTE_ACTION)
  • If privileged and REJECTED           → block execution (decision = REJECTED)

The node NEVER raises an exception that would crash the graph.
"""
import logging
import time

from app.graph.state import AgentState

logger = logging.getLogger("it-agent-backend")


def approval_node(state: AgentState) -> dict:
    logger.info("--- Approval Node ---")
    start_time = time.time()

    try:
        session_id         = state.get("session_id", "")
        recommended_action = state.get("recommended_action", "")
        current_status     = (state.get("approval_status") or "PENDING").upper().strip()

        # ── 1. Check whether this action requires approval ────────────────────
        from app.services.approval_service import detect_privileged
        is_privileged = detect_privileged(state)

        if not is_privileged:
            logger.info("Approval Node: Action is NOT privileged. Bypassing approval gate.")
            return {
                "approval_required": False,
                "approval_status":   "APPROVED",   # treat as auto-approved
            }

        logger.info(
            "Approval Node: Privileged action detected. "
            "action='%s' current_status='%s'",
            recommended_action, current_status,
        )

        # ── 2. Already decided? ───────────────────────────────────────────────
        if current_status == "APPROVED":
            logger.info("Approval Node: Status is APPROVED. Allowing execution.")
            _audit(session_id, recommended_action, "APPROVED")
            return {
                "approval_required": True,
                "approval_status":   "APPROVED",
                "decision":          "EXECUTE_ACTION",
                "decision_response": "Your request has been approved and is being executed.",
            }

        if current_status == "REJECTED":
            logger.info("Approval Node: Status is REJECTED. Blocking execution.")
            _audit(session_id, recommended_action, "REJECTED")
            return {
                "approval_required": True,
                "approval_status":   "REJECTED",
                "decision":          "REJECTED",
                "decision_response":  "This action was rejected and will not be executed.",
            }

        # ── 3. Gate: request approval ─────────────────────────────────────────
        from app.services.approval_service import create_approval_entry, audit_approval
        create_approval_entry(session_id, recommended_action)
        audit_approval(session_id, recommended_action, "PENDING")

        action_label = recommended_action.replace("_", " ").title() if recommended_action else "this action"
        response = (
            f"⚠️ **Approval Required**\n\n"
            f"The action **{action_label}** requires your explicit approval before execution.\n\n"
            f"**Action:** {recommended_action or 'N/A'}\n"
            f"**Status:** Pending your approval\n\n"
            f"Please reply **APPROVE** to proceed or **REJECT** to cancel."
        )
        logger.info(
            "Approval Node: Approval requested for session=%s action='%s'",
            session_id, recommended_action,
        )
        return {
            "approval_required": True,
            "approval_status":   "PENDING",
            "decision":          "REQUEST_APPROVAL",
            "decision_response": response,
        }

    except Exception as e:
        logger.error("Approval Node: Unexpected error — %s", e, exc_info=True)
        # Safe fallback: do not block the graph
        return {
            "approval_required": False,
            "approval_status":   "PENDING",
            "decision":          "ASK_MORE_INFO",
            "decision_response":  "An error occurred during the approval check. Please try again.",
        }

    finally:
        try:
            from app.core.metrics import AGENT_EXECUTION_TIME
            AGENT_EXECUTION_TIME.labels(agent_name="Approval Agent").observe(
                time.time() - start_time
            )
        except Exception:
            pass


# ── helpers ───────────────────────────────────────────────────────────────────

def _audit(session_id: str, action: str, status: str) -> None:
    try:
        from app.services.approval_service import audit_approval
        audit_approval(session_id, action, status)
    except Exception as e:
        logger.error("Approval Node: Audit failed: %s", e)
