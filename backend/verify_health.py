import sys
import os
import unittest
from fastapi.testclient import TestClient

# Add app directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "app")))
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from app.main import app

class TestExtendedHealthCheck(unittest.TestCase):
    def setUp(self):
        from app.database.connection import engine
        from app.database.base import Base
        Base.metadata.create_all(bind=engine)
        from app.jobs.scheduler import run_database_migrations
        run_database_migrations()
        self.client = TestClient(app)

    def test_health_endpoint_details(self):
        """Verifies /health endpoint returns extended health diagnostic details."""
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        
        data = response.json()
        self.assertIn("status", data)
        self.assertIn("database", data)
        self.assertIn("redis", data)
        self.assertIn("gemini", data)
        self.assertIn("adapters", data)
        self.assertIn("scheduler", data)
        
        # Verify scheduler status structure
        scheduler = data["scheduler"]
        self.assertIn("running", scheduler)
        self.assertIn("jobs", scheduler)
        
        # Verify adapters check ServiceNow & AD structure
        adapters = data["adapters"]
        self.assertIn("ServiceNow", adapters)
        self.assertIn("Microsoft Graph", adapters)
        self.assertIn("Active Directory", adapters)
        
        print("[OK] Health check /health extended diagnostic payload validated successfully.")

if __name__ == "__main__":
    unittest.main()
