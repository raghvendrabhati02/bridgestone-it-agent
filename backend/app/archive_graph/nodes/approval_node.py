"""
Approval Node  (Enterprise Edition)
=====================================
Sits between decision_node and action_node.

Routing logic:
  • If the action is NOT privileged       → pass straight through (decision = EXECUTE_ACTION)
  • If privileged and role lacks permission → ACCESS_DENIED  ← NEW
  • If privileged and NOT yet approved    → set approval_status = PENDING, return REQUEST_APPROVAL
  • If privileged and APPROVED            → let the action proceed (decision = EXECUTE_ACTION)
  • If privileged and REJECTED            → block execution (decision = REJECTED)

Enterprise additions:
  • RBAC check via rbac_service.has_permission() for "approve_privileged_action"
  • Structured audit via rbac_audit_service.log_rbac_event()

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
        username           = state.get("username", "unknown")
        user_role          = (state.get("user_role") or "EMPLOYEE").upper().strip()

        # ── 1. Check whether this action requires approval ────────────────────
        from app.services.approval_service import detect_privileged
        is_privileged = detect_privileged(state)

        if not is_privileged:
            # ── Security: even when detect_privileged() returns False (e.g.
            # recommended_action was cleared by our state-wipe fix, or the LLM
            # returned EXECUTE_ACTION with an empty action name), an EMPLOYEE
            # must never receive an APPROVED result for an EXECUTE_ACTION
            # decision.  Without this guard the non-privileged fast-path
            # auto-approves any execution request for any role.
            decision_field = (state.get("decision") or "").upper().strip()
            if decision_field == "EXECUTE_ACTION":
                from app.services import rbac_service, rbac_audit_service
                if not rbac_service.has_permission(user_role, "approve_privileged_action"):
                    logger.warning(
                        "Approval Node: SECURITY — role '%s' (user '%s') attempted "
                        "EXECUTE_ACTION via non-privileged bypass. Denying.",
                        user_role, username,
                    )
                    try:
                        from app.services.approval_service import update_approval
                        update_approval(session_id, "ACCESS_DENIED")
                    except Exception as e:
                        logger.error("Approval Node: Failed to update database approval status: %s", e)

                    rbac_audit_service.log_rbac_event(
                        user=username,
                        role=user_role,
                        action="ACCESS_DENIED",
                        ticket_id=state.get("active_ticket") or None,
                        old_state=None,
                        new_state=None,
                        details={
                            "reason": "EXECUTE_ACTION_NON_PRIVILEGED_BYPASS_BLOCKED",
                            "is_privileged_detected": False,
                            "recommended_action": recommended_action,
                            "session_id": session_id,
                        },
                    )
                    access_denied = rbac_service.build_access_denied_response(
                        role=user_role,
                        action="approve_privileged_action",
                    )
                    return {
                        **access_denied,
                        "approval_status":    "ACCESS_DENIED",
                        "approval_required":  False,
                        "recommended_action": "",
                        "approval_action":    None,
                    }

            logger.info("Approval Node: Action is NOT privileged. Bypassing approval gate.")
            return {
                "approval_required": False,
                "approval_status":   "APPROVED",   # treat as auto-approved
            }

        logger.info(
            "Approval Node: Privileged action detected. "
            "action='%s' current_status='%s' user='%s' role='%s'",
            recommended_action, current_status, username, user_role,
        )

        # ── 2. RBAC check — only MANAGER / ADMIN may approve privileged actions ─
        from app.services import rbac_service, rbac_audit_service

        if not rbac_service.has_permission(user_role, "approve_privileged_action"):
            try:
                from app.services.approval_service import update_approval
                update_approval(session_id, "ACCESS_DENIED")
            except Exception as e:
                logger.error("Approval Node: Failed to update database approval status: %s", e)

            rbac_audit_service.log_rbac_event(
                user=username,
                role=user_role,
                action="ACCESS_DENIED",
                ticket_id=state.get("active_ticket") or None,
                old_state=None,
                new_state=None,
                details={
                    "reason": "RBAC_DENIED",
                    "required_action": "approve_privileged_action",
                    "recommended_action": recommended_action,
                    "session_id": session_id,
                },
            )
            # ── Security: clear all approval-related state to prevent privilege
            # escalation via session poisoning.  build_access_denied_response()
            # only returns {decision, decision_response}; without explicit resets
            # the LangGraph merge keeps approval_status="PENDING" and
            # recommended_action intact, allowing a follow-up "yes" to re-trigger
            # the privileged action on the next turn.
            access_denied = rbac_service.build_access_denied_response(
                role=user_role,
                action="approve_privileged_action",
            )
            return {
                **access_denied,
                "approval_status":    "ACCESS_DENIED",   # must NOT be PENDING
                "approval_required":  False,
                "recommended_action": "",                 # wipe stale action name
                "approval_action":    None,               # wipe stale action payload
            }

        # ── 3. Already decided? ───────────────────────────────────────────────
        if current_status == "APPROVED":
            logger.info("Approval Node: Status is APPROVED. Allowing execution.")
            _audit(session_id, recommended_action, "APPROVED")
            rbac_audit_service.log_rbac_event(
                user=username,
                role=user_role,
                action="approve_privileged_action",
                ticket_id=state.get("active_ticket") or None,
                old_state="PENDING",
                new_state="APPROVED",
                details={"recommended_action": recommended_action, "session_id": session_id},
            )
            return {
                "approval_required": True,
                "approval_status":   "APPROVED",
                "decision":          "EXECUTE_ACTION",
                "decision_response": "Your request has been approved and is being executed.",
            }

        if current_status == "REJECTED":
            logger.info("Approval Node: Status is REJECTED. Blocking execution.")
            _audit(session_id, recommended_action, "REJECTED")
            rbac_audit_service.log_rbac_event(
                user=username,
                role=user_role,
                action="approve_privileged_action",
                ticket_id=state.get("active_ticket") or None,
                old_state="PENDING",
                new_state="REJECTED",
                details={"recommended_action": recommended_action, "session_id": session_id},
            )
            return {
                "approval_required": True,
                "approval_status":   "REJECTED",
                "decision":          "REJECTED",
                "decision_response":  "This action was rejected and will not be executed.",
            }

        # ── 4. Gate: request approval ─────────────────────────────────────────
        from app.services.approval_service import create_approval_entry, audit_approval
        create_approval_entry(session_id, recommended_action)
        audit_approval(session_id, recommended_action, "PENDING")

        rbac_audit_service.log_rbac_event(
            user=username,
            role=user_role,
            action="approve_privileged_action",
            ticket_id=state.get("active_ticket") or None,
            old_state=None,
            new_state="PENDING",
            details={"recommended_action": recommended_action, "session_id": session_id},
        )

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
