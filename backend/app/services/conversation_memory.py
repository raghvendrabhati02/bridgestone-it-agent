"""
conversation_memory.py
─────────────────────────────────────────────────────────────────────────────
Sprint 1 — Phase 2: Memory Service

Responsible for managing and formatting conversation history turns.
Owns memory updates, formatting conversions, history retrieval, and trimming.
Exposes only public interfaces to interact with persistence.
"""

from __future__ import annotations

import logging
from typing import List, Optional

import app.services.conversation_persistence as persistence

logger = logging.getLogger("it-agent-backend")


def get_history(session_id: str) -> List[dict]:
    """
    Retrieve the full conversation history as a list of sender turns.
    Format: [{"sender": "user"|"agent", "text": str}, ...]
    """
    # 1. Try to read from cache first via persistence cache API
    state = persistence.cache_get(session_id)
    if state is not None:
        return getattr(state, "conversation_history", []) or []

    # 2. Fall back to database turns
    turns = persistence.get_turns_data(session_id)
    history = []
    for t in turns:
        history.append({"sender": "user", "text": t.get("user_message", "")})
        history.append({"sender": "agent", "text": t.get("agent_response", "")})
    return history


def get_trimmed_history(session_id: str, last_n_turns: int) -> List[dict]:
    """
    Retrieve only the last `last_n_turns` messages from the conversation history.
    """
    history = get_history(session_id)
    if last_n_turns <= 0:
        return []
    return history[-last_n_turns:]


def append_message(session_id: str, sender: str, text: str) -> None:
    """
    Append a single user or agent message turn to the in-memory history cache.
    """
    state = persistence.cache_get(session_id)
    if state is not None:
        history = getattr(state, "conversation_history", None)
        if history is None:
            state.conversation_history = []
            history = state.conversation_history
        history.append({"sender": sender, "text": text})
        logger.debug("ConversationMemory: Appended message to cache for session %s (sender=%s)", session_id, sender)
    else:
        logger.warning("ConversationMemory: Cannot append message to cache; session %s not in cache.", session_id)


def append_turn_pair(session_id: str, user_message: str, agent_response: str, category: str = "GENERAL") -> None:
    """
    Append user message and agent response to the cache history, and persist
    the turn to the database.
    """
    # 1. Append in-memory messages
    append_message(session_id, "user", user_message)
    append_message(session_id, "agent", agent_response)

    # 2. Persist turn to SQL database
    persistence.save_turn(
        session_id=session_id,
        user_message=user_message,
        agent_response=agent_response,
        category=category,
    )
    logger.info("ConversationMemory: Persisted turn pair for session %s (category=%s)", session_id, category)


def format_for_orchestrator(session_id: str, last_n_turns: Optional[int] = None) -> List[dict]:
    """
    Retrieve and convert history into the format expected by OrchestratorService/Gemini:
    [{"role": "user"|"model", "text": str}, ...]
    """
    if last_n_turns is not None:
        history = get_trimmed_history(session_id, last_n_turns)
    else:
        history = get_history(session_id)

    formatted = []
    for msg in history:
        role = "model" if msg.get("sender") == "agent" else "user"
        text = msg.get("text", "").strip()
        if text:
            formatted.append({"role": role, "text": text})
    return formatted
