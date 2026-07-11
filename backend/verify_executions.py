import sys
import os
import unittest
from fastapi.testclient import TestClient

# Add app directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "app")))
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from app.main import app
from app.database.connection import engine
from app.database.base import Base

class TestExecutionsAPI(unittest.TestCase):
    def setUp(self):
        Base.metadata.create_all(bind=engine)
        self.client = TestClient(app)
        
        # Log in to get admin token
        login_res = self.client.post(
            "/auth/login",
            json={"username": "admin", "password": "adminpassword"}
        )
        self.assertEqual(login_res.status_code, 200)
        self.token = login_res.json()["access_token"]
        self.admin_headers = {"Authorization": f"Bearer {self.token}"}
        
    def test_executions_workflow(self):
        """Verifies the complete executions retrieval, search, filter, and stats flow."""
        # 1. Fetch statistics
        stats_res = self.client.get("/api/executions/statistics", headers=self.admin_headers)
        self.assertEqual(stats_res.status_code, 200)
        stats = stats_res.json()
        self.assertIn("total_executions", stats)
        self.assertIn("success_rate", stats)
        self.assertIn("average_duration", stats)
        self.assertGreaterEqual(stats["total_executions"], 5)
        print("[OK] GET /api/executions/statistics verified successfully.")
        
        # 2. Fetch list (unfiltered)
        list_res = self.client.get("/api/executions", headers=self.admin_headers)
        self.assertEqual(list_res.status_code, 200)
        data = list_res.json()
        self.assertIn("total", data)
        self.assertIn("executions", data)
        self.assertGreaterEqual(len(data["executions"]), 5)
        print("[OK] GET /api/executions base list verified.")
        
        # 3. Test Search filter (by employee)
        search_res = self.client.get("/api/executions?search=employee", headers=self.admin_headers)
        self.assertEqual(search_res.status_code, 200)
        search_data = search_res.json()
        for e in search_data["executions"]:
            self.assertTrue("employee" in e["username"].lower() or "employee" in e["device_id"].lower())
        print("[OK] Search logic verified.")
        
        # 4. Test status filter
        status_res = self.client.get("/api/executions?status_filter=Failed", headers=self.admin_headers)
        self.assertEqual(status_res.status_code, 200)
        status_data = status_res.json()
        for e in status_data["executions"]:
            self.assertEqual(e["status"], "Failed")
        print("[OK] Status filter verified.")
        
        # 5. Fetch single execution detail
        first_id = data["executions"][0]["id"]
        detail_res = self.client.get(f"/api/executions/{first_id}", headers=self.admin_headers)
        self.assertEqual(detail_res.status_code, 200)
        detail = detail_res.json()
        self.assertEqual(detail["id"], first_id)
        self.assertIn("logs", detail)
        self.assertIn("parameters", detail)
        print("[OK] GET /api/executions/{id} details verified.")

if __name__ == "__main__":
    unittest.main()
