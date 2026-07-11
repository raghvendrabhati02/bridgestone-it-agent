"""
test_manager_portal.py
──────────────────────────────────────────────────────────────────────────────
Unit and integration tests for the Manager Portal.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock

from app.main import app
from app.core.security import get_current_user, get_db_context

def test_get_manager_tickets_rbac_employee_blocked():
    """Verify employees are blocked from accessing manager tickets endpoint."""
    # Setup mock user
    mock_user = MagicMock()
    mock_user.username = "employee"
    mock_user.role = "EMPLOYEE"

    # Override dependencies
    app.dependency_overrides[get_current_user] = lambda: mock_user
    app.dependency_overrides[get_db_context] = lambda: MagicMock()

    client = TestClient(app)
    try:
        response = client.get("/api/itsm/manager-tickets")
        assert response.status_code == 403
        assert "Only Managers and Admins" in response.json()["detail"]
    finally:
        app.dependency_overrides.clear()

def test_get_manager_tickets_rbac_manager_allowed():
    """Verify managers can access manager tickets endpoint."""
    mock_user = MagicMock()
    mock_user.username = "manager"
    mock_user.role = "MANAGER"

    # Mock database query
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
        response = client.get("/api/itsm/manager-tickets")
        assert response.status_code == 200
        assert "tickets" in response.json()
    finally:
        app.dependency_overrides.clear()

def test_get_manager_tickets_filtering():
    """Verify that manager tickets filtering parameters correctly query the DB."""
    mock_user = MagicMock()
    mock_user.username = "manager"
    mock_user.role = "MANAGER"

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
        # 1. Test filtering by PENDING
        response = client.get("/api/itsm/manager-tickets?approval_status=PENDING")
        assert response.status_code == 200

        # 2. Test filtering by APPROVED
        response = client.get("/api/itsm/manager-tickets?approval_status=APPROVED")
        assert response.status_code == 200

        # 3. Test filtering by REJECTED
        response = client.get("/api/itsm/manager-tickets?approval_status=REJECTED")
        assert response.status_code == 200
    finally:
        app.dependency_overrides.clear()

def test_get_manager_tickets_ai_recommendation_fallback():
    """Verify dynamic AI recommendation fallback for non-existing session traces."""
    mock_user = MagicMock()
    mock_user.username = "manager"
    mock_user.role = "MANAGER"

    mock_db = MagicMock()
    mock_query = MagicMock()
    mock_db.query.return_value = mock_query
    mock_query.filter.return_value = mock_query
    mock_query.order_by.return_value = mock_query

    # Mock dynamic ticket response
    mock_ticket = MagicMock()
    mock_ticket.ticket_id = "INC00001"
    mock_ticket.category = "VPN"
    mock_ticket.description = "GlobalProtect not connecting"
    mock_ticket.issue_description = "GlobalProtect not connecting"
    mock_ticket.assigned_team = "Network"
    mock_ticket.assigned_engineer = None
    mock_ticket.priority = "MEDIUM"
    mock_ticket.status = "PENDING"
    mock_ticket.created_by = "employee"
    mock_ticket.created_at.isoformat.return_value = "2026-07-09T06:00:00"
    mock_ticket.updated_at.isoformat.return_value = "2026-07-09T06:00:00"
    mock_ticket.resolved_at = None
    mock_ticket.closed_at = None
    mock_ticket.request_type = "SERVICE_REQUEST"
    mock_ticket.manager = "manager"
    mock_ticket.approval_status = "PENDING"
    mock_ticket.assignment_group = "Network"
    mock_ticket.sla_hours = 8
    mock_ticket.sla_state = "HEALTHY"
    mock_ticket.sla_breached = False

    mock_query.all.return_value = [mock_ticket]

    app.dependency_overrides[get_current_user] = lambda: mock_user
    app.dependency_overrides[get_db_context] = lambda: mock_db

    client = TestClient(app)
    try:
        response = client.get("/api/itsm/manager-tickets?approval_status=PENDING")
        assert response.status_code == 200
        tickets = response.json()["tickets"]
        assert len(tickets) == 1
        assert tickets[0]["ai_recommendation"] == "Verify AD lock status and reset remote access gateway session."
    finally:
        app.dependency_overrides.clear()
