"""
Memory Agent — session-scoped context memory for the IT support agent.

Extracts and stores conversation-level context so downstream nodes
(ticket_node, ticket_status_node, decision_node) can reference
previously discussed issues without the user restating them.

Memory schema:
{
    "active_issue":           str,   # e.g. "VPN"
    "conversation_goal":      str,   # e.g. "troubleshooting" | "ticket_creation"
    "last_problem_summary":   str,   # plain-English issue description
    "last_root_cause":        str,   # last root-cause summary, if available
    "last_ticket":            str,   # last ticket ID created in this session
}
"""

import logging
import re

logger = logging.getLogger("it-agent-backend")


class MemoryAgent:
    """Extracts and manages session-scoped issue memory."""

    # ──────────────────────────────────────────────────────────
    # Public API
    # ──────────────────────────────────────────────────────────

    def load_memory(self, *, session_id: str, state: dict) -> dict:
        """
        Build the memory dict from current state and persisted session.

        This is called at the start of each graph run (memory_node)
        so that downstream nodes always have access to session context.
        """
        memory = {
            "active_issue": state.get("active_issue", ""),
            "conversation_goal": state.get("conversation_goal", ""),
            "last_problem_summary": "",
            "last_root_cause": "",
            "last_ticket": state.get("active_ticket", ""),
        }

        # Extract problem summary from conversation history
        history = self._get_history(session_id)
        if history:
            memory["last_problem_summary"] = self._extract_problem_summary(history)
            memory["conversation_goal"] = (
                memory["conversation_goal"]
                or self._infer_goal(state.get("user_message", ""), history)
            )

        # Carry forward root-cause from previous turn if available
        last_reflection = state.get("reflection")
        if last_reflection and isinstance(last_reflection, dict):
            memory["last_root_cause"] = last_reflection.get("findings", "")

        # Carry forward root cause analysis from previous turn
        rca = state.get("root_cause_analysis")
        if rca and isinstance(rca, dict) and rca.get("summary"):
            memory["last_root_cause"] = rca["summary"]

        # Infer active_issue from user message if not already set
        if not memory["active_issue"]:
            memory["active_issue"] = self._infer_issue_category(
                state.get("user_message", "")
            )

        logger.info(
            "MemoryAgent: loaded — active_issue='%s', goal='%s', "
            "problem_summary='%s', last_ticket='%s'",
            memory["active_issue"],
            memory["conversation_goal"],
            memory["last_problem_summary"][:60] if memory["last_problem_summary"] else "",
            memory["last_ticket"],
        )
        return memory

    def update_memory_after_graph(self, memory: dict, final_state: dict) -> dict:
        """
        Called after graph completion to update memory with new results.
        Returns an updated memory dict.
        """
        updated = dict(memory)

        # Update ticket reference
        ticket_id = final_state.get("active_ticket") or ""
        if ticket_id:
            updated["last_ticket"] = ticket_id

        # Update active issue
        active_issue = final_state.get("active_issue") or ""
        if active_issue:
            updated["active_issue"] = active_issue

        # Update root cause from this turn's analysis
        rca = final_state.get("root_cause_analysis")
        if rca and isinstance(rca, dict) and rca.get("summary"):
            updated["last_root_cause"] = rca["summary"]

        # Update conversation goal
        decision = final_state.get("decision", "")
        if decision in ("CREATE_TICKET", "TICKET_CREATED"):
            updated["conversation_goal"] = "ticket_creation"
        elif decision == "TICKET_STATUS":
            updated["conversation_goal"] = "status_check"
        elif decision in ("ASK_MORE_INFO", "TROUBLESHOOT"):
            updated["conversation_goal"] = "troubleshooting"

        return updated

    # ──────────────────────────────────────────────────────────
    # Internal helpers
    # ──────────────────────────────────────────────────────────

    def _get_history(self, session_id: str) -> list:
        """Fetch conversation history from the database."""
        if not session_id:
            return []
        try:
            from app.services.conversation_service import get_conversation
            conv_state = get_conversation(session_id)
            if conv_state and hasattr(conv_state, "conversation_history"):
                return conv_state.conversation_history or []
        except Exception as e:
            logger.warning("MemoryAgent: Could not fetch history: %s", e)
        return []

    def _extract_problem_summary(self, history: list) -> str:
        """
        Extract the first substantive user message as the problem summary.
        Skips greetings and very short messages.
        """
        greetings = {"hi", "hello", "hey", "good morning", "good evening",
                      "good afternoon", "thanks", "thank you", "bye", "goodbye"}

        for msg in history:
            if msg.get("sender") != "user":
                continue
            text = msg.get("text", "").strip()
            if text.lower() in greetings:
                continue
            if len(text) < 5:
                continue
            # This is the first real problem description
            return text

        return ""

    def _infer_goal(self, user_message: str, history: list) -> str:
        """Infer the conversation goal from the current message context."""
        msg_lower = user_message.lower()
        if any(kw in msg_lower for kw in ("create ticket", "raise ticket", "open ticket",
                                           "file ticket", "submit ticket")):
            return "ticket_creation"
        if any(kw in msg_lower for kw in ("status", "update", "progress", "where is")):
            return "status_check"
        return "troubleshooting"

    def _infer_issue_category(self, user_message: str) -> str:
        """Lightweight keyword-based issue detection for memory seeding."""
        msg_lower = user_message.lower()
        if any(kw in msg_lower for kw in ("vpn", "virtual private", "remote access")):
            return "VPN"
        if any(kw in msg_lower for kw in ("outlook", "email", "mail", "exchange")):
            return "OUTLOOK"
        if any(kw in msg_lower for kw in ("network", "internet", "wifi", "wi-fi", "connectivity")):
            return "NETWORK"
        if any(kw in msg_lower for kw in ("install", "software", "application", "app")):
            return "SOFTWARE"
        return ""
