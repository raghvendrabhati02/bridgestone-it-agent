import sys
import os
import unittest
import uuid
from fastapi.testclient import TestClient

# Add app directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "app")))
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from app.main import app
from app.database.connection import SessionLocal
from app.core.logging_context import correlation_id_ctx
from app.database.repositories.trace_repository import TraceRepository
from app.database.repositories.audit_repository import AuditRepository

class TestRequestTracing(unittest.TestCase):
    def setUp(self):
        from app.database.connection import engine
        from app.database.base import Base
        Base.metadata.create_all(bind=engine)
        from app.jobs.scheduler import run_database_migrations
        run_database_migrations()

        self.db = SessionLocal()
        self.trace_repo = TraceRepository(self.db)
        self.audit_repo = AuditRepository(self.db)
        self.client = TestClient(app)

    def tearDown(self):
        self.db.close()

    def test_correlation_id_propagation(self):
        """Verifies correlation ID is propagated to DB trace and audit entities automatically."""
        test_corr_id = f"corr-test-{uuid.uuid4().hex[:6]}"
        correlation_id_ctx.set(test_corr_id)

        # 1. Save an agent trace
        trace = self.trace_repo.save(
            session_id="session-trace-test",
            agent_name="Test Tracing Agent",
            input_data={"test": "input"},
            output_data={"test": "output"}
        )
        self.assertEqual(trace.correlation_id, test_corr_id)

        # 2. Save an audit log
        audit = self.audit_repo.save(
            session_id="session-trace-test",
            user_message="test message",
            category="testing",
            decision="verify",
            approval_status="APPROVED"
        )
        self.assertEqual(audit.correlation_id, test_corr_id)
        print(f"[OK] Correlation ID '{test_corr_id}' successfully propagated to database models.")

if __name__ == "__main__":
    unittest.main()
