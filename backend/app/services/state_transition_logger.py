"""
state_transition_logger.py
─────────────────────────────────────────────────────────────────────────────
Records every conversation phase transition with full context.

Design contract:
  • Thread-safe in-process ring buffer (last 500 records per process lifetime).
  • Also writes to the standard logger so existing log pipelines capture it.
  • No DB I/O — zero risk of crashing the caller.
  • get_transitions() exposed for test assertions.
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Optional

logger = logging.getLogger("it-agent-backend")

_lock = threading.RLock()
_MAX_RECORDS = 500
_records: List["TransitionRecord"] = []


@dataclass
class TransitionRecord:
    session_id: str
    previous_phase: str
    next_phase: str
    reason: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


def log_transition(
    session_id: str,
    previous_phase: str,
    next_phase: str,
    reason: str,
    timestamp: Optional[datetime] = None,
) -> None:
    """
    Record a phase transition and emit a structured log entry.

    Parameters
    ----------
    session_id      : str  — conversation session identifier
    previous_phase  : str  — phase before the transition
    next_phase      : str  — phase after the transition
    reason          : str  — human-readable explanation (e.g. "KB article found")
    timestamp       : datetime, optional — defaults to utcnow
    """
    ts = timestamp or datetime.now(timezone.utc)
    record = TransitionRecord(
        session_id=session_id,
        previous_phase=str(previous_phase),
        next_phase=str(next_phase),
        reason=reason,
        timestamp=ts,
    )

    with _lock:
        _records.append(record)
        if len(_records) > _MAX_RECORDS:
            _records.pop(0)

    logger.info(
        "StateTransition: session=%s  %s → %s  reason='%s'",
        session_id,
        previous_phase,
        next_phase,
        reason,
    )


def get_transitions(session_id: Optional[str] = None) -> List[TransitionRecord]:
    """
    Return transition records, optionally filtered by session_id.
    Used by tests to assert state machine correctness.
    """
    with _lock:
        if session_id is None:
            return list(_records)
        return [r for r in _records if r.session_id == session_id]


def clear() -> None:
    """Clear all records — call between tests to prevent cross-test pollution."""
    with _lock:
        _records.clear()
