"""
knowledge_orchestrator.py
─────────────────────────────────────────────────────────────────────────────
Single responsibility: run a KB search and start a TroubleshootingSession.

Design contract:
  • Calls knowledge_service.search() → troubleshooting_service.start().
  • Updates state.troubleshooting_session and state.phase on success.
  • Returns the formatted first step string, or None if no article found.
  • Never raises — all exceptions are caught and logged.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Optional

import app.services.knowledge_service as knowledge_service
import app.services.troubleshooting_service as troubleshooting_service
from app.services.response_builder import format_step

if TYPE_CHECKING:
    from app.services.conversation_service import SessionState, ConversationPhase

logger = logging.getLogger("it-agent-backend")


class KnowledgeOrchestrator:
    """Orchestrates KB lookup → TroubleshootingEngine startup."""

    def start_troubleshooting(
        self, state: "SessionState", message: str
    ) -> Optional[str]:
        """
        Search the KB for an article matching `message`.

        If found:
          • Creates a TroubleshootingSession.
          • Sets state.troubleshooting_session.
          • Returns the formatted first step string.
          • Does NOT change state.phase — that is the orchestrator's responsibility.

        If not found or on error:
          • Returns None (caller falls through to Gemini).
        """
        try:
            kb_result = knowledge_service.search(message)
            article = kb_result.get("article")
            if not article:
                # Fallback to category search to ensure Knowledge Base always has priority
                article = knowledge_service.search_by_category(state.category)
                if not article:
                    logger.info(
                        "KnowledgeOrchestrator: No KB article for session %s or category %s",
                        state.session_id, state.category
                    )
                    return None

            article_id = article.get("article_id")
            logger.info(
                "KnowledgeOrchestrator: Found article %s for session %s",
                article_id,
                state.session_id,
            )

            session = troubleshooting_service.start(article_id)
            if not session:
                logger.warning(
                    "KnowledgeOrchestrator: Could not start session for article %s", article_id
                )
                return None

            state.troubleshooting_session = session
            # NOTE: phase is NOT changed here — ConversationService._transition() does that.

            step_details = troubleshooting_service.current_step(session)
            if not step_details:
                logger.warning(
                    "KnowledgeOrchestrator: Article %s has no step 1", article_id
                )
                return None

            return format_step(step_details)

        except Exception as exc:
            logger.error(
                "KnowledgeOrchestrator: KB lookup failed for session %s: %s",
                state.session_id,
                exc,
            )
            return None
