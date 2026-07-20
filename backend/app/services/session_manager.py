"""
session_manager.py
─────────────────────────────────────────────────────────────────────────────
Single responsibility: manage the lifecycle of SessionState objects.

Responsibilities:
  • Load sessions from cache (fast path) or DB (cold start).
  • Create new sessions and prime the cache.
  • Expose get() / load_or_create() for the orchestrator.

Design contract:
  • No business logic — only session construction and cache management.
  • All DB calls are wrapped; never raises to caller.
  • Injected ConversationRepository handles TroubleshootingSession restore.
"""

from __future__ import annotations

import logging
import uuid
from typing import Optional

import app.services.conversation_memory as memory
import app.services.conversation_persistence as persistence

logger = logging.getLogger("it-agent-backend")


class SessionManager:
    """Manages creation, caching, and restoration of SessionState objects."""

    def __init__(self, repo=None) -> None:
        # repo is injected so tests can swap it out
        from app.services.conversation_repository import ConversationRepository
        self._repo = repo or ConversationRepository()

    # ── Public API ────────────────────────────────────────────────────────────

    def get(self, session_id: str):
        """Return SessionState from cache, then DB. None if not found anywhere."""
        cached = persistence.cache_get(session_id)
        if cached is not None:
            return cached
        return self._load_from_db(session_id)

    def create(self, category: str) -> tuple[str, object]:
        """Create a fresh SessionState; return (session_id, state)."""
        from app.services.conversation_service import SessionState, ConversationPhase
        session_id = str(uuid.uuid4())
        state = SessionState(session_id=session_id, category=category)
        persistence.cache_set(session_id, state)
        logger.info(
            "SessionManager: Created new session %s (category=%s)", session_id, category
        )
        return session_id, state

    def load_or_create(
        self, session_id: Optional[str], category: str
    ) -> tuple[str, object]:
        """
        If session_id is provided, try loading from cache/DB.
        If not found (or session_id is None), create fresh.
        Returns (session_id, state).
        """
        if session_id:
            state = self.get(session_id)
            if state is not None:
                return session_id, state
            logger.warning(
                "SessionManager: session %s not found — creating fresh", session_id
            )
            from app.services.conversation_service import SessionState
            state = SessionState(session_id=session_id, category=category)
            persistence.cache_set(session_id, state)
            logger.info(
                "SessionManager: Created new session %s (category=%s)", session_id, category
            )
            return session_id, state
        return self.create(category)

    def save_to_cache(self, state) -> None:
        """Persist the state object back to the in-process cache."""
        persistence.cache_set(state.session_id, state)

    # ── Internal ──────────────────────────────────────────────────────────────

    def _load_from_db(self, session_id: str):
        """Cold-start restore from database."""
        from app.database.session import get_db
        from app.database.repositories.conversation_repository import (
            ConversationRepository as DBRepo,
        )
        from app.services.conversation_service import SessionState, ConversationPhase

        try:
            with get_db() as db:
                repo = DBRepo(db)
                db_session = repo.get_session(session_id)
                if not db_session:
                    return None

                try:
                    phase = ConversationPhase(db_session.status)
                except ValueError:
                    phase = ConversationPhase.UNDERSTANDING

                state = SessionState(
                    session_id=session_id,
                    category=db_session.category,
                    phase=phase,
                    current_step=db_session.current_step,
                    approval_required=db_session.approval_required,
                    approval_status=db_session.approval_status,
                    recommended_action=db_session.recommended_action or "",
                    action_result=db_session.action_result,
                    tool_result=db_session.tool_result or {},
                    active_ticket=db_session.active_ticket or "",
                    active_issue=db_session.active_issue or "",
                    active_request=db_session.active_request or "",
                    conversation_goal=db_session.conversation_goal or "",
                    last_action=db_session.last_action or "",
                )
                state.conversation_history = memory.get_history(session_id)

                # Restore embedded TroubleshootingSession
                self._repo.restore_ts(state)

                persistence.cache_set(session_id, state)
                logger.info(
                    "SessionManager: Restored session %s from DB (phase=%s)",
                    session_id,
                    phase,
                )
                return state

        except Exception as exc:
            logger.error(
                "SessionManager: Error restoring session %s: %s", session_id, exc
            )
            return None
