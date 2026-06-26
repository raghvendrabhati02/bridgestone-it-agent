import sys
import os
import unittest
from fastapi.testclient import TestClient

# Add app directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "app")))
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from app.main import app

class TestObservabilityMetrics(unittest.TestCase):
    def setUp(self):
        from app.database.connection import engine
        from app.database.base import Base
        Base.metadata.create_all(bind=engine)
        from app.jobs.scheduler import run_database_migrations
        run_database_migrations()
        self.client = TestClient(app)

    def test_system_status_metrics(self):
        """Verifies that the /system-status endpoint exposes all required dynamic metrics."""
        response = self.client.get("/system-status")
        self.assertEqual(response.status_code, 200)

        data = response.json()
        self.assertIn("rpm", data)
        self.assertIn("error_rate", data)
        self.assertIn("slowest_apis", data)
        self.assertIn("average_ai_latency", data)
        self.assertIn("tool_success_rate", data)
        self.assertIn("active_sessions", data)
        self.assertIn("notification_backlog", data)
        self.assertIn("metrics_summary", data)

        metrics_summary = data["metrics_summary"]
        self.assertIn("rpm", metrics_summary)
        self.assertIn("error_rate", metrics_summary)
        self.assertIn("average_ai_latency", metrics_summary)
        self.assertIn("tool_success_rate", metrics_summary)
        self.assertIn("active_sessions", metrics_summary)
        self.assertIn("notification_backlog", metrics_summary)

        print("[OK] /system-status metrics structure and validation verified.")

if __name__ == "__main__":
    unittest.main()
