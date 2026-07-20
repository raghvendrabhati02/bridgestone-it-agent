"""
conversation_repository.py  (services layer)
─────────────────────────────────────────────────────────────────────────────
Single-responsibility: persist and restore conversation sessions and turns.

This is the *services-layer* repository. It is distinct from
app/database/repositories/conversation_repository.py (the DB-layer DAO).

Responsibilities:
  • Serialise TroubleshootingSession into the tool_result JSON blob.
  • Deserialise TroubleshootingSession from the tool_result JSON blob.
  • Write session + turn to DB via the DB-layer DAO.
  • Never raise — all exceptions are caught and logged.

Design contract:
  • No business logic — only data transformation and I/O.
  • All methods are instance methods for easy test injection.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import TYPE_CHECKING, Optional

import app.services.conversation_memory as memory
import app.services.conversation_persistence as persistence

if TYPE_CHECKING:
    from app.services.conversation_service import SessionState

logger = logging.getLogger("it-agent-backend")


class ConversationRepository:
    """Services-layer repository for session and turn persistence."""

    # ── Troubleshooting session serialisation ─────────────────────────────────

    def serialize_ts(self, state: "SessionState") -> None:
        """Embed the TroubleshootingSession into state.tool_result for DB storage."""
        if not isinstance(state.tool_result, dict):
            state.tool_result = {}

        ts = state.troubleshooting_session
        if ts:
            state.tool_result["_tb_state"] = {
                "article_id": ts.article_id,
                "current_step": ts.current_step,
                "completed_steps": ts.completed_steps,
                "attempts": ts.attempts,
                "finished": ts.finished,
                "created_at": ts.created_at.isoformat(),
                "updated_at": ts.updated_at.isoformat(),
            }
        else:
            state.tool_result.pop("_tb_state", None)

        if getattr(state, "diagnostic_answers", None) is not None:
            state.tool_result["_diagnostic_answers"] = state.diagnostic_answers
        else:
            state.tool_result.pop("_diagnostic_answers", None)

        if getattr(state, "attempted_actions", None) is not None:
            state.tool_result["_attempted_actions"] = state.attempted_actions
        else:
            state.tool_result.pop("_attempted_actions", None)

        state.tool_result["clarifying_questions_asked"] = getattr(state, "clarifying_questions_asked", 0)
        state.tool_result["troubleshooting_steps_suggested"] = getattr(state, "troubleshooting_steps_suggested", 0)

    def restore_ts(self, state: "SessionState") -> None:
        """Deserialise a TroubleshootingSession stored inside state.tool_result."""
        from app.services.troubleshooting_service import TroubleshootingSession

        blob = (
            state.tool_result.get("_tb_state")
            if isinstance(state.tool_result, dict)
            else None
        )
        if not blob:
            state.diagnostic_answers = state.tool_result.get("_diagnostic_answers", {}) if isinstance(state.tool_result, dict) else {}
            state.attempted_actions = state.tool_result.get("_attempted_actions", []) if isinstance(state.tool_result, dict) else []
            return
        try:
            created = blob.get("created_at")
            updated = blob.get("updated_at")
            state.troubleshooting_session = TroubleshootingSession(
                article_id=blob["article_id"],
                current_step=blob["current_step"],
                completed_steps=blob["completed_steps"],
                attempts=blob["attempts"],
                finished=blob["finished"],
                created_at=datetime.fromisoformat(created) if created else datetime.now(),
                updated_at=datetime.fromisoformat(updated) if updated else datetime.now(),
            )
        except Exception as exc:
            logger.warning(
                "ConversationRepository: Could not restore TroubleshootingSession: %s", exc
            )
        state.diagnostic_answers = state.tool_result.get("_diagnostic_answers", {}) if isinstance(state.tool_result, dict) else {}
        state.attempted_actions = state.tool_result.get("_attempted_actions", []) if isinstance(state.tool_result, dict) else []
        state.clarifying_questions_asked = state.tool_result.get("clarifying_questions_asked", 0) if isinstance(state.tool_result, dict) else 0
        state.troubleshooting_steps_suggested = state.tool_result.get("troubleshooting_steps_suggested", 0) if isinstance(state.tool_result, dict) else 0

    # ── Write ─────────────────────────────────────────────────────────────────

    def persist(
        self, state: "SessionState", user_message: str, bot_text: str
    ) -> None:
        """
        Save session state + conversation turn to DB and append to memory cache.
        Never raises.
        """
        try:
            self.serialize_ts(state)
            persistence.save_session(state.session_id, state)
            memory.append_turn_pair(
                state.session_id, user_message, bot_text, state.category
            )
        except Exception as exc:
            logger.error(
                "ConversationRepository: persist failed for session %s: %s",
                state.session_id,
                exc,
            )
