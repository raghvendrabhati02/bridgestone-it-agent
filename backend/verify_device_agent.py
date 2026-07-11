import sys
import os
import unittest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

# Add app directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "app")))
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from app.main import app
from app.services.device_agent_client import DeviceAgentClient
from app.services.device_agent_service import DeviceAgentService
from app.database.connection import engine
from app.database.base import Base

class TestDeviceAgentIntegration(unittest.TestCase):
    def setUp(self):
        Base.metadata.create_all(bind=engine)
        self.client = TestClient(app)
        
        # Clear the service class level cache before every test
        DeviceAgentService._cached_status = None
        DeviceAgentService._cached_time = 0
        
        # Log in to get token
        login_res = self.client.post(
            "/auth/login",
            json={"username": "admin", "password": "adminpassword"}
        )
        self.assertEqual(login_res.status_code, 200)
        self.token = login_res.json()["access_token"]
        self.admin_headers = {"Authorization": f"Bearer {self.token}"}
        
    @patch('requests.get')
    @patch('requests.post')
    def test_client_methods_connected(self, mock_post, mock_get):
        """Verifies Client and Service methods when agent is online and responsive."""
        mock_get_response = MagicMock()
        mock_get_response.status_code = 200
        mock_get_response.json.side_effect = [
            {"status": "healthy", "version": "v1.2.4", "uptime": 3600}, # health call
            {"cpu": 12.5, "hostname": "BS-EMP-WS09"}, # system info call
            {"success": True, "history": []}, # history call
            {"status": "healthy"} # service status call (cache is cleared, so it calls client again)
        ]
        mock_get.return_value = mock_get_response
        
        # Mock POST response
        mock_post_response = MagicMock()
        mock_post_response.status_code = 200
        mock_post_response.json.return_value = {"success": True, "message": "Flush DNS succeeded", "logs": ["DNS cache flushed"]}
        mock_post.return_value = mock_post_response
        
        client = DeviceAgentClient()
        
        # 1. Test Client methods
        h_res = client.health()
        self.assertTrue(h_res["connected"])
        self.assertEqual(h_res["status"], "healthy")
        
        si_res = client.system_info()
        self.assertTrue(si_res["connected"])
        self.assertEqual(si_res["hostname"], "BS-EMP-WS09")
        
        hist_res = client.history()
        self.assertTrue(hist_res["connected"])
        self.assertTrue(hist_res["success"])
        
        exec_res = client.execute("flush_dns", {})
        self.assertTrue(exec_res["connected"])
        self.assertTrue(exec_res["success"])
        
        # 2. Test Service methods
        service = DeviceAgentService()
        self.assertEqual(service.get_status()["status"], "healthy")
        
        print("[OK] Online DeviceAgentClient and DeviceAgentService methods verified.")

    @patch('requests.get')
    def test_client_offline_graceful(self, mock_get):
        """Verifies Client retries and returns standard offline response when agent is offline."""
        import requests
        mock_get.side_effect = requests.exceptions.ConnectionError("Connection refused")
        
        client = DeviceAgentClient()
        # Adjust retries for testing to speed up test execution
        client.retries = 1
        client.retry_delay = 0.01
        
        res = client.health()
        self.assertFalse(res["connected"])
        self.assertEqual(res["message"], "Enterprise Device Agent Offline")
        print("[OK] Offline error handled gracefully without raising exceptions.")

    @patch('requests.get')
    @patch('requests.post')
    def test_endpoints_workflow(self, mock_post, mock_get):
        """Verifies API endpoints map correctly to the client logic."""
        mock_get_response = MagicMock()
        mock_get_response.status_code = 200
        mock_get_response.json.side_effect = [
            {"status": "healthy"}, # status call
            {"cpu": 15.0}, # system-info call
            {"success": True, "history": []} # history call
        ]
        mock_get.return_value = mock_get_response
        
        mock_post_response = MagicMock()
        mock_post_response.status_code = 200
        mock_post_response.json.return_value = {"success": True, "message": "Done", "logs": ["Success"]}
        mock_post.return_value = mock_post_response
        
        # Test GET /api/device-agent/status
        res = self.client.get("/api/device-agent/status", headers=self.admin_headers)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["status"], "healthy")
        
        # Test GET /api/device-agent/system-info
        res = self.client.get("/api/device-agent/system-info", headers=self.admin_headers)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["cpu"], 15.0)
        
        # Test GET /api/device-agent/history
        res = self.client.get("/api/device-agent/history", headers=self.admin_headers)
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.json()["success"])
        
        # Test POST /api/device-agent/action
        res = self.client.post(
            "/api/device-agent/action",
            json={"action": "flush_dns", "parameters": {}},
            headers=self.admin_headers
        )
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.json()["success"])
        print("[OK] API endpoints (status, system-info, history, action) verified successfully.")

if __name__ == "__main__":
    unittest.main()
