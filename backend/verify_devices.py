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

class TestDevicesModule(unittest.TestCase):
    def setUp(self):
        # Make sure tables exist
        Base.metadata.create_all(bind=engine)
        self.client = TestClient(app)
        
        # Get admin auth token
        login_res = self.client.post(
            "/auth/login",
            json={"username": "admin", "password": "adminpassword"}
        )
        self.assertEqual(login_res.status_code, 200)
        self.token = login_res.json()["access_token"]
        self.admin_headers = {"Authorization": f"Bearer {self.token}"}
        
    def test_devices_endpoints_workflow(self):
        """Verifies the complete devices management lifecycle and heartbeat ingestion."""
        # 1. Device agent sends heartbeat to register itself
        heartbeat_data = {
            "id": "TEST-HOST-999",
            "hostname": "TEST-HOST-999",
            "serial_number": "BS-TEST-999",
            "manufacturer": "Dell",
            "model": "Precision 5550",
            "operating_system": "Windows 11 Enterprise",
            "ram": 16.0,
            "cpu": 15.5,
            "disk": 80.0,
            "ip_address": "192.168.1.99",
            "mac_address": "AA:BB:CC:DD:EE:FF",
            "agent_version": "1.0",
            "status": "Online",
            "username": "tester",
            "department": "QA",
            "installed_software": ["Python", "Chrome", "Git"],
            "running_processes": ["python.exe", "chrome.exe"],
            "network_interfaces": [{"name": "Ethernet", "ip": "192.168.1.99", "status": "up"}]
        }
        
        hb_res = self.client.post("/api/devices/heartbeat", json=heartbeat_data)
        self.assertEqual(hb_res.status_code, 200)
        self.assertEqual(hb_res.json()["status"], "success")
        print("[OK] Heartbeat registration test passed.")
        
        # 2. Query /api/devices (unfiltered) and check if TEST-HOST-999 is listed
        list_res = self.client.get("/api/devices", headers=self.admin_headers)
        self.assertEqual(list_res.status_code, 200)
        list_data = list_res.json()
        self.assertIn("devices", list_data)
        self.assertIn("stats", list_data)
        self.assertGreaterEqual(list_data["total"], 1)
        
        # Check stats
        stats = list_data["stats"]
        self.assertGreaterEqual(stats["total_devices"], 1)
        self.assertGreaterEqual(stats["online_devices"], 1)
        self.assertGreaterEqual(stats["healthy_devices"], 1)
        print("[OK] GET /api/devices and statistics mapping verified.")
        
        # 3. Search for TEST-HOST-999
        search_res = self.client.get("/api/devices?search=TEST-HOST-999", headers=self.admin_headers)
        self.assertEqual(search_res.status_code, 200)
        search_data = search_res.json()
        self.assertEqual(search_data["total"], 1)
        self.assertEqual(search_data["devices"][0]["hostname"], "TEST-HOST-999")
        print("[OK] Search filter by hostname verified.")
        
        # 4. Get specific device details
        details_res = self.client.get("/api/devices/TEST-HOST-999", headers=self.admin_headers)
        self.assertEqual(details_res.status_code, 200)
        device_details = details_res.json()
        self.assertEqual(device_details["serial_number"], "BS-TEST-999")
        self.assertEqual(device_details["mac_address"], "AA:BB:CC:DD:EE:FF")
        self.assertEqual(device_details["installed_software"], ["Python", "Chrome", "Git"])
        print("[OK] GET /api/devices/{id} detailed response schema verified.")
        
        # 5. Get device health diagnostics
        health_res = self.client.get("/api/devices/TEST-HOST-999/health", headers=self.admin_headers)
        self.assertEqual(health_res.status_code, 200)
        health_data = health_res.json()
        self.assertEqual(health_data["overall_health"], "healthy")
        self.assertEqual(health_data["cpu_health"], "healthy")
        self.assertEqual(health_data["metrics"]["cpu_load_pct"], 15.5)
        print("[OK] GET /api/devices/{id}/health diagnostics layout verified.")
        
        # 6. Execute refresh command
        refresh_res = self.client.post("/api/devices/TEST-HOST-999/refresh", headers=self.admin_headers)
        self.assertEqual(refresh_res.status_code, 200)
        refresh_data = refresh_res.json()
        self.assertEqual(refresh_data["status"], "success")
        print("[OK] POST /api/devices/{id}/refresh command verified.")
        
        # 7. Check device history (should be empty or populated)
        hist_res = self.client.get("/api/devices/TEST-HOST-999/history", headers=self.admin_headers)
        self.assertEqual(hist_res.status_code, 200)
        self.assertIsInstance(hist_res.json(), list)
        print("[OK] GET /api/devices/{id}/history logs fetch verified.")

if __name__ == "__main__":
    unittest.main()
