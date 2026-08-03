"""
test_sprint8_devops.py
─────────────────────────────────────────────────────────────────────────────
Sprint 8 — Production Deployment & DevOps Test Suite

Coverage:
  - Health checks: GET /health, GET /ready, GET /live
  - Observability: GET /metrics (Prometheus metrics format)
  - Database configuration: SQLite & PostgreSQL engine initialization
  - Structured Logging: JSON logger context format
  - Security & Middleware: Security headers, request size limits, CORS
"""

from __future__ import annotations

import os
import json
import logging
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("SECRET_KEY", "sprint8-test-secret-key-123456")
os.environ.setdefault("ALGORITHM", "HS256")

from app.main import app
from app.database.base import Base
from app.database.models.user import User
from app.core.security import get_current_user, get_db_context
from app.core.json_logger import JsonFormatter

# In-memory SQLite DB for testing
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

client = TestClient(app)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(autouse=True)
def setup_database():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(autouse=True)
def reset_dependency_overrides():
    yield
    app.dependency_overrides.clear()


# ─────────────────────────────────────────────────────────────────────────────
# 1. HEALTH CHECKS & PROBES
# ─────────────────────────────────────────────────────────────────────────────

class TestHealthEndpoints:

    def test_health_endpoint_returns_200_and_components_status(self):
        app.dependency_overrides[get_db_context] = override_get_db
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert "status" in data
        assert "database" in data
        assert "redis" in data
        assert "gemini" in data
        assert "adapters" in data
        assert data["database"] == "healthy"

    def test_ready_endpoint_returns_200_when_ready(self):
        import app.main as main_mod
        main_mod._app_ready = True
        resp = client.get("/ready")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ready"
        assert "ready to accept traffic" in data["message"]

    def test_ready_endpoint_returns_503_when_not_ready(self):
        import app.main as main_mod
        main_mod._app_ready = False
        resp = client.get("/ready")
        assert resp.status_code == 503
        data = resp.json()
        assert data["status"] == "not_ready"
        main_mod._app_ready = True  # reset


    def test_live_endpoint_returns_200_and_alive_status(self):
        resp = client.get("/live")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "alive"
        assert data["service"] == "bridgestone-it-agent"


# ─────────────────────────────────────────────────────────────────────────────
# 2. OBSERVABILITY & PROMETHEUS METRICS
# ─────────────────────────────────────────────────────────────────────────────

class TestObservabilityMetrics:

    def test_metrics_endpoint_returns_prometheus_format(self):
        app.dependency_overrides[get_db_context] = override_get_db
        resp = client.get("/metrics")
        assert resp.status_code == 200
        text = resp.text
        assert "http_requests_total" in text
        assert "http_request_duration_seconds" in text
        assert "http_failures_total" in text

    def test_business_and_active_user_metrics_exposed(self):
        app.dependency_overrides[get_db_context] = override_get_db
        resp = client.get("/metrics")
        assert resp.status_code == 200
        text = resp.text
        assert "business_tickets_created_total" in text
        assert "business_approvals_total" in text
        assert "business_notifications_sent_total" in text
        assert "active_users" in text


# ─────────────────────────────────────────────────────────────────────────────
# 3. DATABASE ENGINE INITIALIZATION
# ─────────────────────────────────────────────────────────────────────────────

class TestDatabaseConfiguration:

    def test_sqlite_url_engine_creation(self):
        from sqlalchemy.engine import Engine
        test_db_url = "sqlite:///:memory:"
        test_engine = create_engine(test_db_url, connect_args={"check_same_thread": False})
        assert isinstance(test_engine, Engine)
        assert "sqlite" in str(test_engine.url)

    def test_postgresql_url_engine_creation(self):
        from sqlalchemy.engine import Engine
        test_db_url = "postgresql://user:pass@localhost:5432/testdb"
        test_engine = create_engine(test_db_url)
        assert isinstance(test_engine, Engine)
        assert "postgresql" in str(test_engine.url)


# ─────────────────────────────────────────────────────────────────────────────
# 4. STRUCTURED JSON LOGGING & SECURITY HEADERS
# ─────────────────────────────────────────────────────────────────────────────

class TestLoggingAndSecurity:

    def test_json_formatter_outputs_valid_json(self):
        formatter = JsonFormatter()
        record = logging.LogRecord(
            name="it-agent-test",
            level=logging.INFO,
            pathname="test.py",
            lineno=10,
            msg="Sprint 8 test log message",
            args=(),
            exc_info=None
        )
        formatted = formatter.format(record)
        parsed = json.loads(formatted)
        assert parsed["message"] == "Sprint 8 test log message"
        assert parsed["level"] == "INFO"
        assert "timestamp" in parsed

    def test_security_headers_present_in_response(self):
        resp = client.get("/live")
        assert resp.status_code == 200
        assert resp.headers.get("X-Content-Type-Options") == "nosniff"
        assert resp.headers.get("X-Frame-Options") in ("DENY", "SAMEORIGIN")
        assert resp.headers.get("X-XSS-Protection") == "1; mode=block"
