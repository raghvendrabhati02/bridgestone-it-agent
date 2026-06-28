import logging
import time

from app.graph.state import AgentState
from app.services.ticket_service import create_ticket

logger = logging.getLogger("it-agent-backend")


def ticket_node(state: AgentState) -> dict:
    logger.info("--- Ticket Node ---")

    start_time = time.time()

    try:
        category = state.get("category", "GENERAL")
        user_msg = state.get("user_message", "")
        username = state.get("username")
        session_id = state.get("session_id")

        # ── Duplicate ticket guard ────────────────────────────────────────────
        existing_ticket_id = state.get("active_ticket") or ""
        if existing_ticket_id:
            logger.info(
                "Ticket Node: Duplicate ticket prevented. active_ticket=%s already exists.",
                existing_ticket_id,
            )
            return {
                "decision": "TICKET_STATUS",
                "decision_response": (
                    f"An open support ticket already exists for this issue: "
                    f"**{existing_ticket_id}**. "
                    f"I'll avoid creating a duplicate. "
                    f"Would you like me to check the current status instead?"
                ),
                # Keep existing context unchanged
                "active_ticket": existing_ticket_id,
            }
        # ───────────────────────────────────────────────────────────────

        from app.services.conversation_service import get_conversation

        conv_state = get_conversation(session_id)

        # Use first user message as ticket description
        description = user_msg

        if conv_state and getattr(conv_state, "conversation_history", None):
            user_msgs = [
                msg["text"]
                for msg in conv_state.conversation_history
                if msg["sender"] == "user"
            ]

            if user_msgs:
                description = user_msgs[0]

        # ── Memory enhancement ─────────────────────────────────────────────
        # If the current user_msg is a generic "create ticket" command,
        # use memory context for a richer ticket description.
        memory = state.get("memory") or {}
        msg_lower = user_msg.lower().strip()
        is_generic_create = any(
            kw in msg_lower for kw in (
                "create ticket", "raise ticket", "open ticket",
                "file ticket", "submit ticket",
            )
        ) and len(msg_lower) < 40

        if is_generic_create:
            problem_summary = memory.get("last_problem_summary", "")
            active_issue = memory.get("active_issue", "") or category
            last_root_cause = memory.get("last_root_cause", "")

            if problem_summary:
                description = problem_summary
                if last_root_cause:
                    description = (
                        f"{problem_summary} — "
                        f"Root cause analysis: {last_root_cause[:200]}"
                    )
                logger.info(
                    "Ticket Node: Using memory for description — "
                    "active_issue='%s', summary='%s'",
                    active_issue,
                    description[:80],
                )
            if active_issue and category == "GENERAL":
                category = active_issue
        # ───────────────────────────────────────────────────────────────

        # ── Duplicate check ───────────────────────────────────────────────────
        from app.database.session import get_db
        from app.services.workflow_service import WorkflowService

        bypass = state.get("bypass_duplicate_check", False)
        duplicates = []
        try:
            with get_db() as db:
                duplicates = WorkflowService.check_duplicate(db, description, threshold=0.6)
        except Exception as e:
            logger.error("Ticket Node: Failed to check for duplicate tickets: %s", e)

        if duplicates and not bypass:
            best_dup = duplicates[0]
            logger.info("Ticket Node: Duplicate warning triggered. Match ID=%s", best_dup["ticket_id"])
            return {
                "decision": "DUPLICATE_WARNING",
                "suggested_duplicate_id": best_dup["ticket_id"],
                "bypass_duplicate_check": False,
                "decision_response": (
                    f"Warning: A very similar ticket **{best_dup['ticket_id']}** already exists. "
                    f"Would you like me to link to this existing ticket, or create a new one anyway?"
                )
            }

        logger.info(
            "Ticket Node: Creating ticket | category=%s | created_by=%s",
            category,
            username,
        )

        ticket = create_ticket(
            category=category,
            issue_description=description,
            created_by=username,
        )

        ticket_id = ticket.get("ticket_id", "")
        logger.info(
            "Ticket Node: Ticket created successfully. ticket_id=%s",
            ticket_id,
        )

        # Log duplicate dismiss relations if bypassed
        if duplicates and bypass:
            best_dup = duplicates[0]
            try:
                with get_db() as db:
                    WorkflowService.dismiss_duplicate(db, ticket_id, best_dup["ticket_id"])
                    db.commit()
            except Exception as e:
                logger.error("Ticket Node: Failed to log dismissed duplicate: %s", e)

        # Automatically cluster the ticket
        try:
            from app.services.cluster_service import ClusterService
            from app.database.models.ticket import Ticket
            with get_db() as db:
                ticket_db = db.query(Ticket).filter(Ticket.ticket_id == ticket_id).first()
                if ticket_db:
                    ClusterService.cluster_ticket(db, ticket_db)
                    db.commit()
        except Exception as e:
            logger.error("Ticket Node: Failed to auto-cluster ticket: %s", e)


        # Audit Trace
        try:
            from app.services.audit_service import log_agent_trace

            log_agent_trace(
                session_id=session_id,
                agent_name="Ticket Agent",
                output={"ticket": ticket},
            )

        except Exception as e:
            logger.error(
                "Ticket Node: Failed to log trace: %s",
                str(e),
            )

        # IMPORTANT:
        # Return values update LangGraph state
        ticket_id = ticket.get("ticket_id", "")
        assigned_team = ticket.get("assigned_team", "IT Team")
        priority = ticket.get("priority", "MEDIUM")
        sla_hours = ticket.get("sla_hours", 8)
        return {
            "ticket": ticket,
            "active_ticket": ticket_id,
            "active_issue": category,
            "last_action": "CREATE_TICKET",
            "decision": "TICKET_CREATED",
            "decision_response": (
                f"I've created a support ticket for your issue. "
                f"Your ticket reference is **{ticket_id}**. "
                f"It has been assigned to the **{assigned_team}** with **{priority}** priority. "
                f"SLA target is **{sla_hours} hours**. "
                f"You'll receive updates as the team works on your case."
            ),
        }

    finally:
        try:
            from app.core.metrics import AGENT_EXECUTION_TIME

            AGENT_EXECUTION_TIME.labels(
                agent_name="Ticket Agent"
            ).observe(time.time() - start_time)

        except Exception:
            pass