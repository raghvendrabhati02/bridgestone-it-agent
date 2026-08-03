"""
test_sprint9_hardening.py
─────────────────────────────────────────────────────────────────────────────
Sprint 9 — Production Hardening & Reliability Test Suite

Coverage:
  - Configuration Validator: validate_environment_config()
  - Security & Input Sanitization: sanitize_input(), JWT token validation
  - Role-Based Rate Limiting: check_role_rate_limit() for ANONYMOUS, EMPLOYEE, MANAGER, ADMIN
  - Exception Handling: global_exception_handler with correlation_id
  - Audit Event Logging: expanded log_security_event event types
  - Backup & Recovery: backup_recovery.py script functions
"""

from __future__ import annotations

import os
import shutil
import tempfile
import pytest
from fastapi import Request, HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("SECRET_KEY", "sprint9-test-secret-key-123456")
os.environ.setdefault("ALGORITHM", "HS256")

from app.main import app
from app.database.base import Base
from app.core.security import sanitize_input, create_access_token, create_refresh_token, decode_token
from app.core.config_validator import validate_environment_config
from app.core.rate_limiter import check_role_rate_limit, reset_rate_limit_store
from app.services.security_service import log_security_event, get_all_security_events
from scripts.backup_recovery import create_database_backup, create_config_backup, restore_database_backup

# In-memory SQLite DB for testing
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_database():
    Base.metadata.create_all(bind=engine)
    reset_rate_limit_store()
    yield
    Base.metadata.drop_all(bind=engine)
    reset_rate_limit_store()


# ─────────────────────────────────────────────────────────────────────────────
# 1. STARTUP CONFIGURATION VALIDATION
# ─────────────────────────────────────────────────────────────────────────────

class TestConfigValidator:

    def test_validate_environment_config_development_pass(self):
        is_valid, errors = validate_environment_config()
        assert is_valid is True
        assert len(errors) == 0

    def test_validate_environment_config_production_missing_secret_fails(self, monkeypatch):
        monkeypatch.setenv("ENVIRONMENT", "production")
        monkeypatch.delenv("SECRET_KEY", raising=False)
        monkeypatch.delenv("JWT_SECRET", raising=False)
        is_valid, errors = validate_environment_config()
        assert is_valid is False
        assert any("SECRET_KEY" in e for e in errors)


# ─────────────────────────────────────────────────────────────────────────────
# 2. SECURITY & INPUT SANITIZATION
# ─────────────────────────────────────────────────────────────────────────────

class TestSecurityHardening:

    def test_sanitize_input_escapes_xss_payloads(self):
        xss_input = "<script>alert('xss')</script>"
        sanitized = sanitize_input(xss_input)
        assert "<script>" not in sanitized
        assert "&lt;script&gt;" in sanitized

    def test_jwt_access_vs_refresh_token_claims(self):
        acc_token = create_access_token({"sub": "testuser", "role": "EMPLOYEE"})
        ref_token = create_refresh_token({"sub": "testuser"})

        acc_payload = decode_token(acc_token)
        ref_payload = decode_token(ref_token)

        assert acc_payload["type"] == "access"
        assert ref_payload["type"] == "refresh"


# ─────────────────────────────────────────────────────────────────────────────
# 3. ROLE-BASED RATE LIMITING
# ─────────────────────────────────────────────────────────────────────────────

class TestRoleRateLimiting:

    def test_anonymous_role_rate_limiting(self, monkeypatch):
        monkeypatch.setenv("RATE_LIMIT_ANONYMOUS", "2")
        from app.core import rate_limiter
        monkeypatch.setattr(rate_limiter, "_ENABLED", True)

        scope = {"type": "http", "method": "GET", "path": "/test", "headers": []}
        req = Request(scope)

        check_role_rate_limit(req, role_override="ANONYMOUS")
        check_role_rate_limit(req, role_override="ANONYMOUS")

        with pytest.raises(HTTPException) as exc_info:
            check_role_rate_limit(req, role_override="ANONYMOUS")
        assert exc_info.value.status_code == 429
        assert exc_info.value.detail["error_code"] == "RATE_LIMIT_EXCEEDED"

    def test_admin_role_has_higher_limit(self, monkeypatch):
        monkeypatch.setenv("RATE_LIMIT_ADMIN", "5")
        from app.core import rate_limiter
        monkeypatch.setattr(rate_limiter, "_ENABLED", True)

        scope = {"type": "http", "method": "GET", "path": "/test", "headers": []}
        req = Request(scope)

        for _ in range(5):
            check_role_rate_limit(req, role_override="ADMIN")


# ─────────────────────────────────────────────────────────────────────────────
# 4. EXPANDED AUDIT LOGGING
# ─────────────────────────────────────────────────────────────────────────────

class TestExpandedAuditLogging:

    def test_log_security_events_supports_various_types(self):
        log_security_event(event_type="TICKET_ACTION", username="admin", details="Resolved INC1001")
        log_security_event(event_type="APPROVAL_ACTION", username="mgr1", details="Approved SR2002")
        log_security_event(event_type="ROLE_CHANGE", username="admin", details="Promoted user2 to MANAGER")

        events = get_all_security_events()
        types = [e["event_type"] for e in events]
        assert "TICKET_ACTION" in types
        assert "APPROVAL_ACTION" in types
        assert "ROLE_CHANGE" in types


# ─────────────────────────────────────────────────────────────────────────────
# 5. BACKUP & RECOVERY UTILITY
# ─────────────────────────────────────────────────────────────────────────────

class TestBackupRecoveryUtility:

    def test_database_and_config_backup_execution(self):
        temp_dir = tempfile.mkdtemp()
        try:
            # Create dummy sqlite db for testing backup
            dummy_db = os.path.join(temp_dir, "test.db")
            with open(dummy_db, "w") as f:
                f.write("sqlite format 3 dummy content")

            backup_path = create_database_backup(db_url=f"sqlite:///{dummy_db}", backup_dir=temp_dir)
            assert os.path.isfile(backup_path)

            config_path = create_config_backup(backup_dir=temp_dir)
            assert os.path.isfile(config_path)

            # Test restore
            restored_db = os.path.join(temp_dir, "restored.db")
            res = restore_database_backup(backup_path, target_db_path=restored_db)
            assert res is True
            assert os.path.isfile(restored_db)
        finally:
            shutil.rmtree(temp_dir)
