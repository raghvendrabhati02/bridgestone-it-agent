"""
conversation_persistence.py
─────────────────────────────────────────────────────────────────────────────
Sprint 1 — Phase 1: Persistence Service

Acts as the Data Access Object (DAO) for both in-memory cache and SQL database
storage. Encapsulates all serialization, deserialization, and database transactions.

Public API:
    - save_session(session_id: str, state_or_ctx: Any) -> None
    - get_session_data(session_id: str) -> Optional[dict]
    - save_turn(session_id: str, user_message: str, agent_response: str, category: str) -> None
    - get_turns_data(session_id: str) -> list[dict]

    # In-memory Cache management (keeps conversations dict decoupled)
    - cache_get(session_id: str) -> Optional[Any]
    - cache_set(session_id: str, value: Any) -> None
    - cache_remove(session_id: str) -> None
"""

from __future__ import annotations

import logging
import threading
from typing import Any, Optional

from app.database.session import get_db
from app.database.repositories.conversation_repository import ConversationRepository
from app.services.conversation_state import ConversationContext

logger = logging.getLogger("it-agent-backend")

# Thread-safe in-memory session cache
_cache_lock = threading.RLock()
_cache: dict[str, Any] = {}


def save_session(session_id: str, state_or_ctx: Any) -> None:
    """
    Persist or update the session state in the database.

    Supports both legacy ConversationState and new ConversationContext
    for complete backward compatibility.
    """
    try:
        # Extract properties dynamically to support both legacy and new dataclass
        if isinstance(state_or_ctx, ConversationContext):
            category = state_or_ctx.category
            current_step = state_or_ctx.current_step
            status = state_or_ctx.state.value if hasattr(state_or_ctx.state, 'value') else str(state_or_ctx.state)
            approval_required = False
            approval_status = "PENDING"
            recommended_action = ""
            action_result = None
            tool_result = None
            active_ticket = ""
            active_issue = ""
            active_request = ""
            conversation_goal = ""
            last_action = ""
        else:
            category = getattr(state_or_ctx, "category", "GENERAL")
            current_step = getattr(state_or_ctx, "current_step", 0)
            status = getattr(state_or_ctx, "status", "ACTIVE")
            approval_required = getattr(state_or_ctx, "approval_required", False)
            approval_status = getattr(state_or_ctx, "approval_status", "PENDING")
            recommended_action = getattr(state_or_ctx, "recommended_action", "")
            action_result = getattr(state_or_ctx, "action_result", None)
            tool_result = getattr(state_or_ctx, "tool_result", None)
            active_ticket = getattr(state_or_ctx, "active_ticket", "")
            active_issue = getattr(state_or_ctx, "active_issue", "")
            active_request = getattr(state_or_ctx, "active_request", "")
            conversation_goal = getattr(state_or_ctx, "conversation_goal", "")
            last_action = getattr(state_or_ctx, "last_action", "")

        with get_db() as db:
            repo = ConversationRepository(db)
            repo.save_session(
                session_id=session_id,
                category=category,
                current_step=current_step,
                status=status,
                approval_required=approval_required,
                approval_status=approval_status,
                recommended_action=recommended_action,
                action_result=action_result,
                tool_result=tool_result,
                active_ticket=active_ticket,
                active_issue=active_issue,
                active_request=active_request,
                conversation_goal=conversation_goal,
                last_action=last_action,
            )
        logger.info("ConversationPersistence: Persisted session %s to database", session_id)
    except Exception:
        logger.exception("ConversationPersistence: Failed to save session %s to database", session_id)


def get_session_data(session_id: str) -> Optional[dict]:
    """
    Retrieve session row attributes as a dict from the database.
    """
    try:
        with get_db() as db:
            repo = ConversationRepository(db)
            db_session = repo.get_session(session_id)
            if not db_session:
                return None

            return {
                "session_id": db_session.session_id,
                "category": db_session.category,
                "current_step": db_session.current_step,
                "status": db_session.status,
                "approval_required": db_session.approval_required,
                "approval_status": db_session.approval_status,
                "recommended_action": db_session.recommended_action,
                "action_result": db_session.action_result,
                "tool_result": db_session.tool_result or {},
                "active_ticket": db_session.active_ticket or "",
                "active_issue": db_session.active_issue or "",
                "active_request": db_session.active_request or "",
                "conversation_goal": db_session.conversation_goal or "",
                "last_action": db_session.last_action or "",
            }
    except Exception:
        logger.exception("ConversationPersistence: Error loading session %s from database", session_id)
        return None


def save_turn(session_id: str, user_message: str, agent_response: str, category: str) -> None:
    """
    Save a single turn in the database.
    """
    try:
        with get_db() as db:
            repo = ConversationRepository(db)
            repo.save_turn(
                session_id=session_id,
                user_message=user_message,
                agent_response=agent_response,
                category=category,
            )
        logger.info("ConversationPersistence: Saved turn for session %s to database", session_id)
    except Exception:
        logger.exception("ConversationPersistence: Failed to save turn for session %s", session_id)


def get_turns_data(session_id: str) -> list[dict]:
    """
    Retrieve all turns for a session from the database.
    """
    try:
        with get_db() as db:
            repo = ConversationRepository(db)
            turns = repo.get_turns(session_id)
            return [
                {
                    "user_message": t.user_message,
                    "agent_response": t.agent_response,
                    "category": t.category,
                }
                for t in turns
            ]
    except Exception:
        logger.exception("ConversationPersistence: Error loading turns for session %s", session_id)
        return []


# ── Cache management ─────────────────────────────────────────────────────────

def cache_get(session_id: str) -> Optional[Any]:
    """Retrieve an item from the in-memory cache in a thread-safe manner."""
    with _cache_lock:
        return _cache.get(session_id)


def cache_set(session_id: str, value: Any) -> None:
    """Store an item in the in-memory cache in a thread-safe manner."""
    with _cache_lock:
        _cache[session_id] = value


def cache_remove(session_id: str) -> None:
    """Remove an item from the in-memory cache in a thread-safe manner."""
    with _cache_lock:
        _cache.pop(session_id, None)

