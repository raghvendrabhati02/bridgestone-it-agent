from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock

from app.main import app
from app.core.security import get_current_user, get_db_context

def test_analytics_dashboard_blocked_for_employee():
    """Verify employees are blocked from accessing the analytics dashboard."""
    mock_user = MagicMock()
    mock_user.username = "employee"
    mock_user.role = "EMPLOYEE"

    app.dependency_overrides[get_current_user] = lambda: mock_user
    app.dependency_overrides[get_db_context] = lambda: MagicMock()

    client = TestClient(app)
    try:
        response = client.get("/api/analytics/dashboard")
        assert response.status_code == 403
    finally:
        app.dependency_overrides.clear()

def test_analytics_dashboard_allowed_for_manager():
    """Verify managers can retrieve analytics dashboard data successfully."""
    mock_user = MagicMock()
    mock_user.username = "manager"
    mock_user.role = "MANAGER"

    mock_db = MagicMock()
    # Mock return values for queries
    mock_query = MagicMock()
    mock_db.query.return_value = mock_query
    mock_query.filter.return_value = mock_query
    mock_query.all.return_value = []
    mock_query.count.return_value = 0

    app.dependency_overrides[get_current_user] = lambda: mock_user
    app.dependency_overrides[get_db_context] = lambda: mock_db

    client = TestClient(app)
    try:
        response = client.get("/api/analytics/dashboard?time_filter=month")
        assert response.status_code == 200
        data = response.json()
        assert "cards" in data
        assert "charts" in data
        assert "tables" in data
    finally:
        app.dependency_overrides.clear()
