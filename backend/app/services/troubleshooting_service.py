"""
troubleshooting_service.py
─────────────────────────────────────────────────────────────────────────────
Sprint 2 - Enterprise Troubleshooting Engine.
Manages KB troubleshooting sessions cleanly and states.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List, Dict, Any

import app.services.knowledge_service as knowledge_service

logger = logging.getLogger("it-agent-backend")


@dataclass
class TroubleshootingSession:
    """
    Dataclass representing the current state of a troubleshooting session.
    """
    article_id: str
    current_step: int = 1
    completed_steps: List[int] = field(default_factory=list)
    attempts: int = 0
    finished: bool = False
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)


def start(article_id: str) -> Optional[TroubleshootingSession]:
    """
    Starts a new troubleshooting session.
    Returns None if article_id is invalid.
    """
    if not article_id:
        logger.warning("TroubleshootingService: Attempted to start session with empty article_id")
        return None
    
    try:
        article = knowledge_service.get_article(article_id)
        if not article:
            logger.warning("TroubleshootingService: Article %s not found in knowledge base", article_id)
            return None
        
        now = datetime.now()
        return TroubleshootingSession(
            article_id=article_id,
            completed_steps=[],
            created_at=now,
            updated_at=now
        )
    except Exception as e:
        logger.warning("TroubleshootingService: Error starting session for article %s: %s", article_id, e)
        return None


def current_step(session: TroubleshootingSession) -> Optional[Dict[str, Any]]:
    """
    Returns the current step details dictionary for the session.
    """
    if not session or not getattr(session, "article_id", None):
        logger.warning("TroubleshootingService: Invalid session passed to current_step")
        return None
    
    try:
        return knowledge_service.get_step(session.article_id, session.current_step)
    except Exception as e:
        logger.warning("TroubleshootingService: Error getting current step: %s", e)
        return None


def next_step(session: TroubleshootingSession) -> Optional[Dict[str, Any]]:
    """
    Advances the session to the next step.
    If already on the final step, sets finished=True and returns None.
    """
    if not session or not getattr(session, "article_id", None):
        logger.warning("TroubleshootingService: Invalid session passed to next_step")
        return None
    
    try:
        steps = knowledge_service.get_steps(session.article_id)
        total_steps = len(steps)
        
        session.updated_at = datetime.now()
        
        if session.current_step >= total_steps:
            if not session.finished:
                session.finished = True
                session.attempts += 1
            logger.info("TroubleshootingService: Session for %s finished at step %d", session.article_id, session.current_step)
            return None
            
        session.current_step += 1
        return knowledge_service.get_step(session.article_id, session.current_step)
    except Exception as e:
        logger.warning("TroubleshootingService: Error moving to next step: %s", e)
        return None


def previous_step(session: TroubleshootingSession) -> Optional[Dict[str, Any]]:
    """
    Moves the session back to the previous step.
    Cannot move before step 1.
    """
    if not session or not getattr(session, "article_id", None):
        logger.warning("TroubleshootingService: Invalid session passed to previous_step")
        return None
        
    try:
        session.updated_at = datetime.now()
        
        if session.current_step <= 1:
            session.current_step = 1
            logger.info("TroubleshootingService: Session for %s already at step 1", session.article_id)
            return None
            
        session.current_step -= 1
        return knowledge_service.get_step(session.article_id, session.current_step)
    except Exception as e:
        logger.warning("TroubleshootingService: Error moving to previous step: %s", e)
        return None


def mark_completed(session: TroubleshootingSession) -> None:
    """
    Marks the current step as completed without duplicates.
    Validates that the step actually exists in the KB.
    """
    if not session or not getattr(session, "article_id", None):
        logger.warning("TroubleshootingService: Invalid session passed to mark_completed")
        return
        
    try:
        steps = knowledge_service.get_steps(session.article_id)
        total_steps = len(steps)
        
        if session.current_step < 1 or session.current_step > total_steps:
            logger.warning("TroubleshootingService: Step %d does not exist in article %s", session.current_step, session.article_id)
            return
            
        if session.current_step not in session.completed_steps:
            session.completed_steps.append(session.current_step)
            session.updated_at = datetime.now()
            
        if session.current_step == total_steps:
            if not session.finished:
                session.finished = True
                session.attempts += 1
    except Exception as e:
        logger.warning("TroubleshootingService: Error marking step completed: %s", e)


def is_finished(session: TroubleshootingSession) -> bool:
    """
    Returns True if the session has completed the final step.
    """
    if not session or not getattr(session, "article_id", None):
        logger.warning("TroubleshootingService: Invalid session passed to is_finished")
        return False
    return session.finished


def get_verification(session: TroubleshootingSession) -> List[str]:
    """
    Returns the verification criteria list for the session's article.
    """
    if not session or not getattr(session, "article_id", None):
        logger.warning("TroubleshootingService: Invalid session passed to get_verification")
        return []
    try:
        return knowledge_service.get_verification(session.article_id)
    except Exception as e:
        logger.warning("TroubleshootingService: Error getting verification: %s", e)
        return []


def get_escalation(session: TroubleshootingSession) -> Optional[Dict[str, Any]]:
    """
    Returns the escalation policy for the session's article.
    """
    if not session or not getattr(session, "article_id", None):
        logger.warning("TroubleshootingService: Invalid session passed to get_escalation")
        return None
    try:
        return knowledge_service.get_escalation(session.article_id)
    except Exception as e:
        logger.warning("TroubleshootingService: Error getting escalation: %s", e)
        return None


def reset(session: TroubleshootingSession) -> None:
    """
    Resets the session state back to step 1.
    """
    if not session:
        logger.warning("TroubleshootingService: Invalid session passed to reset")
        return
    session.current_step = 1
    session.completed_steps = []
    session.attempts = 0
    session.finished = False
    session.updated_at = datetime.now()


def remaining_steps(session: TroubleshootingSession) -> int:
    """
    Returns the count of remaining troubleshooting steps from current_step.
    """
    if not session or not getattr(session, "article_id", None):
        return 0
    try:
        total = get_total_steps(session)
        return max(0, total - session.current_step)
    except Exception:
        return 0


def current_progress(session: TroubleshootingSession) -> float:
    """
    Returns the progress of completed steps as a percentage (0.0 to 1.0).
    """
    if not session or not getattr(session, "article_id", None):
        return 0.0
    try:
        total = get_total_steps(session)
        if total == 0:
            return 0.0
        return round(len(session.completed_steps) / total, 2)
    except Exception:
        return 0.0


def restart_from_step(session: TroubleshootingSession, step: int) -> Optional[Dict[str, Any]]:
    """
    Restarts the troubleshooting session from a specific step, clearing later completions.
    """
    if not session or not getattr(session, "article_id", None):
        return None
    try:
        steps = knowledge_service.get_steps(session.article_id)
        if step < 1 or step > len(steps):
            logger.warning("TroubleshootingService: Invalid step %d for restart", step)
            return None
        session.current_step = step
        session.completed_steps = [s for s in session.completed_steps if s < step]
        session.finished = False
        session.updated_at = datetime.now()
        return knowledge_service.get_step(session.article_id, step)
    except Exception as e:
        logger.warning("TroubleshootingService: Error restarting from step %d: %s", step, e)
        return None


def get_total_steps(session: TroubleshootingSession) -> int:
    """
    Returns the total number of steps for the session's article.
    """
    if not session or not getattr(session, "article_id", None):
        return 0
    try:
        return len(knowledge_service.get_steps(session.article_id))
    except Exception:
        return 0
