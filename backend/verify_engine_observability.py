import os
import sys
import datetime
from unittest.mock import patch, MagicMock

# Force UTF-8 output on Windows terminals
if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "app")))

from app.database.connection import SessionLocal
from app.database.models.conversation_event import ConversationEvent
from app.services.observability_service import (
    log_event,
    register_backend,
    BaseObservabilityBackend,
    JsonLoggingBackend,
    DatabasePersistenceBackend
)
from app.core.logging_context import session_id_ctx, user_ctx, role_ctx, turn_start_time_ctx
from fastapi.testclient import TestClient
from app.main import app
from app.core.security import get_current_user, get_db_context, User

# Custom mock backend to test pluggable architecture
class MockObservabilityBackend(BaseObservabilityBackend):
    def __init__(self):
        self.events_logged = []
        
    def log_event(self, event_name, db, data):
        self.events_logged.append((event_name, data))

def test_engine_observability():
    print("==============================================================")
    print("  VERIFY_ENGINE_OBSERVABILITY.PY - Telemetry & Metrics Tests")
    print("==============================================================")
    
    db = SessionLocal()
    try:
        # Clear existing conversation events to have clean counts
        db.query(ConversationEvent).delete()
        db.commit()
        
        # Test 1: Pluggable architecture
        print("[TEST 1] Pluggable backend registration")
        mock_backend = MockObservabilityBackend()
        register_backend(mock_backend)
        
        session_id_ctx.set("sess-test-ob-1")
        user_ctx.set("alice")
        role_ctx.set("EMPLOYEE")
        turn_start_time_ctx.set(100.0)  # dummy start time
        
        log_event(
            event_name="Test pluggable event",
            db=db,
            intent="TEST_INTENT",
            category="TEST_CATEGORY",
            phase="TEST_PHASE",
            clarifying_questions_asked=2,
            troubleshooting_steps_suggested=3,
            escalation_reason="TEST_REASON",
            escalation_blocked=True,
            ticket_id="INC_TEST_001",
            llm_confidence=0.85,
            model_name="test-model"
        )
        
        assert len(mock_backend.events_logged) == 1, "Mock backend should have captured the event"
        evt_name, evt_data = mock_backend.events_logged[0]
        assert evt_name == "Test pluggable event"
        assert evt_data["user_id"] == "alice"
        assert evt_data["intent"] == "TEST_INTENT"
        print("  [PASS] Custom backend successfully registered and captured event.")
        
        # Test 2: Database persistence
        print("[TEST 2] Database persistence of telemetry events")
        db_events = db.query(ConversationEvent).filter(ConversationEvent.session_id == "sess-test-ob-1").all()
        assert len(db_events) == 1, "Should have saved 1 event in database"
        db_evt = db_events[0]
        assert db_evt.event_name == "Test pluggable event"
        assert db_evt.username == "alice"
        assert db_evt.user_role == "EMPLOYEE"
        assert db_evt.intent == "TEST_INTENT"
        assert db_evt.category == "TEST_CATEGORY"
        assert db_evt.phase == "TEST_PHASE"
        assert db_evt.clarifying_questions_asked == 2
        assert db_evt.troubleshooting_steps_suggested == 3
        assert db_evt.escalation_reason == "TEST_REASON"
        assert db_evt.escalation_blocked is True
        assert db_evt.ticket_id == "INC_TEST_001"
        assert db_evt.llm_confidence == 0.85
        assert db_evt.model_name == "test-model"
        print("  [PASS] Event fields correctly persisted to database.")
        
        # Test 3: Log all 14 required events
        print("[TEST 3] Log all 14 telemetry events")
        required_events = [
            "Conversation started",
            "Intent detected",
            "Category detected",
            "Conversation phase transition",
            "Clarifying question asked",
            "Troubleshooting step suggested",
            "Ticket recommendation generated",
            "Premature escalation blocked",
            "Ticket created",
            "Service request created",
            "Manager approval requested",
            "Admin approval requested",
            "LAPS password generated",
            "Conversation completed"
        ]
        
        # Set session id for DB population
        session_id_ctx.set("sess-test-14-events")
        for event in required_events:
            blocked = True if event == "Premature escalation blocked" else (False if event == "Ticket recommendation generated" else None)
            ticket_id = "INC_14_001" if event in ("Ticket created", "Conversation completed") else None
            log_event(
                event_name=event,
                db=db,
                intent="CREATE_TICKET" if "escalation" in event.lower() or "recommendation" in event.lower() else "GENERAL",
                category="VPN",
                phase="AI_TROUBLESHOOTING",
                escalation_blocked=blocked,
                escalation_reason="ADMIN_REQUIRED",
                ticket_id=ticket_id,
                llm_confidence=0.9,
                model_name="gemini-2.5-flash"
            )
            
        # Verify database counts
        for event in required_events:
            db_cnt = db.query(ConversationEvent).filter(
                ConversationEvent.session_id == "sess-test-14-events",
                ConversationEvent.event_name == event
            ).count()
            assert db_cnt >= 1, f"Event '{event}' should be persisted in database"
        print("  [PASS] All 14 conversation engine events successfully persisted.")
        
        # Test 4: Exposing and validating /api/analytics/engine-observability endpoint
        print("[TEST 4] Expose and validate engine-observability API metrics")
        
        mock_user = MagicMock()
        mock_user.username = "admin"
        mock_user.role = "ADMIN"
        
        app.dependency_overrides[get_current_user] = lambda: mock_user
        app.dependency_overrides[get_db_context] = lambda: db
        
        client = TestClient(app)
        response = client.get("/api/analytics/engine-observability")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        required_metrics = [
            "total_conversations",
            "average_troubleshooting_turns",
            "ticket_creation_rate",
            "ticket_block_rate",
            "resolution_without_ticket",
            "average_response_latency",
            "average_llm_confidence",
            "most_common_categories",
            "most_common_escalation_reasons"
        ]
        
        for metric in required_metrics:
            assert metric in data, f"Metric '{metric}' should be present in the API response"
            
        print("  [PASS] All 8 observability metrics returned correctly by API.")
        print(f"         Total conversations: {data['total_conversations']}")
        print(f"         Avg troubleshooting turns: {data['average_troubleshooting_turns']}")
        print(f"         Ticket creation rate: {data['ticket_creation_rate']}")
        print(f"         Ticket block rate: {data['ticket_block_rate']}")
        print(f"         Resolution without ticket: {data['resolution_without_ticket']}")
        print(f"         Avg LLM confidence: {data['average_llm_confidence']}")
        print(f"         Most common categories: {data['most_common_categories']}")
        print(f"         Most common escalation reasons: {data['most_common_escalation_reasons']}")
        
    finally:
        app.dependency_overrides.clear()
        # Clean up database test rows
        db.query(ConversationEvent).filter(ConversationEvent.session_id.in_(["sess-test-ob-1", "sess-test-14-events"])).delete()
        db.commit()
        db.close()
        
    print("\n  ALL OBSERVABILITY ENGINE TESTS PASSED ✅")

if __name__ == "__main__":
    test_engine_observability()
