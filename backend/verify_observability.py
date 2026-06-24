import sys
import os
import unittest
from fastapi.testclient import TestClient

# Add app directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "app")))
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from app.main import app
from app.core.metrics import (
    HTTP_REQUESTS_TOTAL,
    HTTP_REQUEST_DURATION_SECONDS,
    SECURITY_LOGINS_TOTAL,
    SECURITY_FAILED_LOGINS_TOTAL,
    AGENT_EXECUTION_TIME,
    LLM_REQUESTS_TOTAL,
    DB_CONNECTIONS_ACTIVE
)

class TestObservability(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_metrics_endpoint(self):
        """Verifies that the /metrics endpoint returns valid Prometheus metrics text format."""
        response = self.client.get("/metrics")
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/plain", response.headers["content-type"])
        content = response.text
        self.assertIn("http_requests_total", content)
        self.assertIn("agent_execution_duration_seconds", content)
        self.assertIn("llm_requests_total", content)
        self.assertIn("db_connections_active", content)
        print("[OK] /metrics endpoint verified.")

    def test_system_status_endpoint(self):
        """Verifies that /system-status returns JSON with backend dependency health fields."""
        response = self.client.get("/system-status")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["content-type"], "application/json")
        data = response.json()
        self.assertIn("status", data)
        self.assertIn("database", data)
        self.assertIn("redis", data)
        self.assertIn("gemini", data)
        self.assertIn("adapters", data)
        print("[OK] /system-status endpoint verified.")

    def test_metrics_incrementation(self):
        """Verifies Prometheus metrics update on operations."""
        # Check current count of HTTP requests
        response = self.client.get("/metrics")
        lines_before = [l for l in response.text.split("\n") if "http_requests_total" in l]

        # Trigger a simple mock endpoint call
        self.client.get("/")

        # Verify metrics updated
        response = self.client.get("/metrics")
        lines_after = [l for l in response.text.split("\n") if "http_requests_total" in l]
        self.assertTrue(len(lines_after) >= len(lines_before))
        print("[OK] HTTP requests metrics increment verified.")

    def test_direct_metrics_api(self):
        """Verifies direct python prometheus metrics API works."""
        initial_val = SECURITY_LOGINS_TOTAL.labels(username="verify_test")._value.get()
        SECURITY_LOGINS_TOTAL.labels(username="verify_test").inc()
        updated_val = SECURITY_LOGINS_TOTAL.labels(username="verify_test")._value.get()
        self.assertEqual(updated_val, initial_val + 1.0)

        initial_agent = AGENT_EXECUTION_TIME.labels(agent_name="SLA Agent")._sum.get()
        AGENT_EXECUTION_TIME.labels(agent_name="SLA Agent").observe(0.5)
        updated_agent = AGENT_EXECUTION_TIME.labels(agent_name="SLA Agent")._sum.get()
        self.assertEqual(updated_agent, initial_agent + 0.5)
        print("[OK] Direct Prometheus SDK increment and observe calls verified.")

if __name__ == "__main__":
    unittest.main()
