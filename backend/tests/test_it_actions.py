from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock

from app.main import app
from app.core.security import get_current_user, get_db_context
from app.database.models.ticket import TicketState

def test_list_device_actions():
    mock_user = MagicMock()
    mock_user.username = "employee"
    mock_user.role = "EMPLOYEE"

    mock_db = MagicMock()
    mock_query = MagicMock()
    mock_db.query.return_value = mock_query
    mock_query.filter.return_value = mock_query
    mock_query.all.return_value = [] # no approved tickets for employee

    app.dependency_overrides[get_current_user] = lambda: mock_user
    app.dependency_overrides[get_db_context] = lambda: mock_db

    client = TestClient(app)
    try:
        response = client.get("/api/it-actions/list")
        assert response.status_code == 200
        data = response.json()
        assert "actions" in data
        assert len(data["actions"]) > 0
        
        # Verify Restart Computer doesn't require approval
        restart_pc = next(x for x in data["actions"] if x["action_name"] == "Restart Computer")
        assert restart_pc["approval_required"] == "NONE"
        assert restart_pc["approved_for_user"] is True

        # Verify BitLocker Recovery requires ADMIN approval and is restricted (false) for employee without ticket
        bitlocker = next(x for x in data["actions"] if x["action_name"] == "BitLocker Recovery")
        assert bitlocker["approval_required"] == "ADMIN"
        assert bitlocker["approved_for_user"] is False
    finally:
        app.dependency_overrides.clear()

def test_execute_device_action_no_approval_required():
    mock_user = MagicMock()
    mock_user.username = "employee"
    mock_user.role = "EMPLOYEE"

    mock_db = MagicMock()
    mock_query = MagicMock()
    mock_db.query.return_value = mock_query
    mock_query.filter.return_value = mock_query
    mock_query.first.return_value = mock_user

    app.dependency_overrides[get_current_user] = lambda: mock_user
    app.dependency_overrides[get_db_context] = lambda: mock_db

    client = TestClient(app)
    try:
        response = client.post("/api/it-actions/execute", json={
            "action_name": "Restart Computer",
            "device_id": "BS-EMP-WS09"
        })
        assert response.status_code == 200
        data = response.json()
        assert data["result"] == "SUCCESS"
        assert data["action_name"] == "Restart Computer"
        assert "Command execution completed successfully." in data["logs"]
    finally:
        app.dependency_overrides.clear()

def test_execute_device_action_restricted_blocked():
    mock_user = MagicMock()
    mock_user.username = "employee"
    mock_user.role = "EMPLOYEE"

    mock_db = MagicMock()
    mock_query = MagicMock()
    mock_db.query.return_value = mock_query
    mock_query.filter.return_value = mock_query
    mock_query.first.return_value = mock_user
    mock_query.all.return_value = [] # no approved tickets

    app.dependency_overrides[get_current_user] = lambda: mock_user
    app.dependency_overrides[get_db_context] = lambda: mock_db

    client = TestClient(app)
    try:
        response = client.post("/api/it-actions/execute", json={
            "action_name": "BitLocker Recovery",
            "device_id": "BS-EMP-WS09"
        })
        assert response.status_code == 200
        data = response.json()
        assert data["result"] == "FAILED"
        assert "Admin approval is required" in data["logs"]
    finally:
        app.dependency_overrides.clear()

def test_execute_device_action_approved_via_ticket():
    mock_user = MagicMock()
    mock_user.username = "employee"
    mock_user.role = "EMPLOYEE"

    mock_ticket = MagicMock()
    mock_ticket.category = "Software Installation"
    mock_ticket.status = TicketState.APPROVED.value
    mock_ticket.created_by = "employee"

    mock_db = MagicMock()
    mock_query = MagicMock()
    mock_db.query.return_value = mock_query
    mock_query.filter.return_value = mock_query
    mock_query.first.side_effect = [mock_user]  # User query returns employee user
    mock_query.all.return_value = [mock_ticket] # approved ticket check

    app.dependency_overrides[get_current_user] = lambda: mock_user
    app.dependency_overrides[get_db_context] = lambda: mock_db

    client = TestClient(app)
    try:
        response = client.post("/api/it-actions/execute", json={
            "action_name": "Install Approved Software",
            "device_id": "BS-EMP-WS09"
        })
        assert response.status_code == 200
        data = response.json()
        assert data["result"] == "SUCCESS"
    finally:
        app.dependency_overrides.clear()

def test_get_device_action_history():
    mock_user = MagicMock()
    mock_user.username = "employee"
    mock_user.role = "EMPLOYEE"

    mock_db = MagicMock()
    mock_query = MagicMock()
    mock_db.query.return_value = mock_query
    mock_query.filter.return_value = mock_query
    mock_query.order_by.return_value = mock_query
    mock_query.all.return_value = []

    app.dependency_overrides[get_current_user] = lambda: mock_user
    app.dependency_overrides[get_db_context] = lambda: mock_db

    client = TestClient(app)
    try:
        response = client.get("/api/it-actions/history")
        assert response.status_code == 200
        data = response.json()
        assert "history" in data
    finally:
        app.dependency_overrides.clear()
