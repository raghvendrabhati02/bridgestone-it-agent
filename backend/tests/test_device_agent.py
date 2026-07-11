from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch

from app.main import app
from app.core.security import get_current_user, get_db_context

@pytest.fixture
def mock_user():
    user = MagicMock()
    user.username = "employee"
    user.role = "EMPLOYEE"
    return user

@patch("requests.get")
def test_device_agent_health_endpoint(mock_get, mock_user):
    """Verify GET /api/device-agent/health queries the Device Agent API."""
    mock_get.return_value.status_code = 200
    mock_get.return_value.json.return_value = {"success": True, "version": "v1.2.4"}

    app.dependency_overrides[get_current_user] = lambda: mock_user

    client = TestClient(app)
    try:
        response = client.get("/api/device-agent/health")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["version"] == "v1.2.4"
    finally:
        app.dependency_overrides.clear()

@patch("requests.get")
def test_device_agent_system_info_endpoint(mock_get, mock_user):
    """Verify GET /api/device-agent/system-info queries the Device Agent API."""
    mock_get.return_value.status_code = 200
    mock_get.return_value.json.return_value = {
        "success": True,
        "hostname": "BS-EMP-WS09",
        "os": "Windows 11 Enterprise"
    }

    app.dependency_overrides[get_current_user] = lambda: mock_user

    client = TestClient(app)
    try:
        response = client.get("/api/device-agent/system-info")
        assert response.status_code == 200
        data = response.json()
        assert data["hostname"] == "BS-EMP-WS09"
        assert data["os"] == "Windows 11 Enterprise"
    finally:
        app.dependency_overrides.clear()

@patch("requests.post")
def test_device_agent_action_endpoint(mock_post, mock_user):
    """Verify POST /api/device-agent/action executes actions and updates logs."""
    mock_post.return_value.status_code = 200
    mock_post.return_value.json.return_value = {
        "success": True,
        "message": "DNS flushed successfully",
        "logs": ["ipconfig /flushdns executed"]
    }

    mock_db = MagicMock()

    app.dependency_overrides[get_current_user] = lambda: mock_user
    app.dependency_overrides[get_db_context] = lambda: mock_db

    client = TestClient(app)
    try:
        payload = {"action": "flush_dns", "parameters": {}}
        response = client.post("/api/device-agent/action", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["message"] == "DNS flushed successfully"
        assert data["duration_ms"] >= 0
        assert mock_db.add.call_count == 2 # 1 ExecutionHistory + 1 RbacAuditLog
        mock_db.commit.assert_called_once()
    finally:
        app.dependency_overrides.clear()
