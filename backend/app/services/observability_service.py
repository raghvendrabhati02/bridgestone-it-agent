from abc import ABC, abstractmethod
import logging
import time
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
import os
from sqlalchemy.orm import Session

from app.core.logging_context import session_id_ctx, user_ctx, role_ctx, turn_start_time_ctx
from app.database.models.conversation_event import ConversationEvent
from app.database.session import get_db

logger = logging.getLogger("it-agent-backend")

class BaseObservabilityBackend(ABC):
    """
    Abstract base class for all conversation engine observability backends.
    """
    @abstractmethod
    def log_event(self, event_name: str, db: Optional[Session], data: Dict[str, Any]) -> None:
        pass

class JsonLoggingBackend(BaseObservabilityBackend):
    """
    Structured JSON Logging backend. Outputs event telemetry via standard logger.
    """
    def log_event(self, event_name: str, db: Optional[Session], data: Dict[str, Any]) -> None:
        logger.info(f"Observability event: {event_name}", extra=data)

class DatabasePersistenceBackend(BaseObservabilityBackend):
    """
    SQLAlchemy database persistence backend. Saves events to the conversation_events table.
    """
    def log_event(self, event_name: str, db: Optional[Session], data: Dict[str, Any]) -> None:
        if db is None:
            return
        
        ts_str = data.get("timestamp")
        if ts_str:
            try:
                clean_ts = ts_str[:-1] if ts_str.endswith("Z") else ts_str
                ts = datetime.fromisoformat(clean_ts)
            except Exception:
                ts = datetime.utcnow()
        else:
            ts = datetime.utcnow()
            
        event = ConversationEvent(
            session_id=data.get("session_id") or "",
            conversation_id=data.get("conversation_id") or "",
            event_name=event_name,
            username=data.get("user_id"),
            user_role=data.get("user_role"),
            timestamp=ts,
            intent=data.get("intent"),
            category=data.get("category"),
            phase=data.get("conversation_phase"),
            clarifying_questions_asked=data.get("clarifying_questions_asked") or 0,
            troubleshooting_steps_suggested=data.get("troubleshooting_steps_suggested") or 0,
            escalation_reason=data.get("escalation_reason"),
            escalation_blocked=data.get("escalation_blocked"),
            ticket_id=data.get("ticket_id"),
            response_latency=data.get("response_latency") or 0.0,
            llm_confidence=data.get("llm_confidence") or 0.0,
            model_name=data.get("model_name"),
        )
        db.add(event)
        # Flush or commit inside the transaction. Since db might be managed externally,
        # we flush to ensure it is written to session, and commit only if we own it.
        # But wait! If get_db() is transient, we commit. If it is passed in, it will be committed
        # by the caller or we can commit here safely since it's a separate audit record.
        # Commit is safe here to guarantee audit logs are persisted immediately.
        db.commit()

_backends: List[BaseObservabilityBackend] = [
    JsonLoggingBackend(),
    DatabasePersistenceBackend()
]

def register_backend(backend: BaseObservabilityBackend) -> None:
    """
    Allows registering additional telemetry backends dynamically (e.g. Kafka, Redis, OpenTelemetry).
    """
    if backend not in _backends:
        _backends.append(backend)

def get_backends() -> List[BaseObservabilityBackend]:
    return list(_backends)

def log_event(
    event_name: str,
    db: Optional[Session] = None,
    intent: Optional[str] = None,
    category: Optional[str] = None,
    phase: Optional[str] = None,
    clarifying_questions_asked: Optional[int] = None,
    troubleshooting_steps_suggested: Optional[int] = None,
    escalation_reason: Optional[str] = None,
    escalation_blocked: Optional[bool] = None,
    ticket_id: Optional[str] = None,
    llm_confidence: Optional[float] = None,
    model_name: Optional[str] = None,
) -> None:
    """
    Conversation Engine Observability event logging entrypoint.
    Acts as the single abstraction layer.
    """
    session_id = session_id_ctx.get()
    username = user_ctx.get()
    user_role = role_ctx.get()
    
    start_time = turn_start_time_ctx.get()
    response_latency = 0.0
    if start_time > 0:
        response_latency = round(time.time() - start_time, 4)
        
    log_data = {
        "conversation_id": session_id,
        "session_id": session_id,
        "user_id": username,
        "user_role": user_role,
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "intent": intent,
        "category": category,
        "conversation_phase": phase,
        "clarifying_questions_asked": clarifying_questions_asked,
        "troubleshooting_steps_suggested": troubleshooting_steps_suggested,
        "escalation_reason": escalation_reason,
        "escalation_blocked": escalation_blocked,
        "ticket_id": ticket_id,
        "response_latency": response_latency,
        "llm_confidence": llm_confidence or 0.0,
        "model_name": model_name or os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    }
    
    if db is None:
        try:
            with get_db() as db_session:
                for backend in _backends:
                    try:
                        backend.log_event(event_name, db_session, log_data)
                    except Exception as exc:
                        logger.error("Observability Backend %s failed: %s", backend.__class__.__name__, exc)
        except Exception as exc:
            logger.error("Failed to log event dynamically: %s", exc)
            # Run json logging backend even if DB connection failed
            for backend in _backends:
                if isinstance(backend, JsonLoggingBackend):
                    try:
                        backend.log_event(event_name, None, log_data)
                    except Exception:
                        pass
    else:
        for backend in _backends:
            try:
                backend.log_event(event_name, db, log_data)
            except Exception as exc:
                logger.error("Observability Backend %s failed: %s", backend.__class__.__name__, exc)
