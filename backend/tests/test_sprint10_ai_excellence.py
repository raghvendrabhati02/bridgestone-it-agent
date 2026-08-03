"""
test_sprint10_ai_excellence.py
─────────────────────────────────────────────────────────────────────────────
Sprint 10 — AI Excellence, Enterprise Intelligence & Version 2.0 Tests

Coverage:
  - AI Evaluation Framework
  - Prompt Management (View, Edit, Versioning, Restore, Preview)
  - AI Settings & Model Health
  - AI Feedback (👍 Helpful / 👎 Not Helpful) & Summary
  - Conversation Explorer
  - Admin Tools (Rebuild Index, Clear Cache)
  - Multi-Agent Interfaces extension points
"""

from __future__ import annotations

import os
import json
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("SECRET_KEY", "sprint10-test-secret-key-123456")
os.environ.setdefault("ALGORITHM", "HS256")

from app.main import app
from app.database.base import Base
from app.database.models.user import User
from app.core.security import get_current_user, get_db_context, RoleChecker, create_access_token

from app.services.ai_evaluation_service import get_ai_evaluation_metrics
from app.services.prompt_management_service import (
    get_all_prompts, update_prompt, get_prompt_history, restore_prompt_version, preview_prompt
)
from app.services.ai_settings_service import get_ai_settings, update_ai_settings, get_model_health_stats
from app.services.ai_feedback_service import submit_feedback, get_feedback_summary, search_conversations
from app.agents.multi_agent_interface import TriageAgentInterface, DiagnosticAgentInterface, ActionAgentInterface

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


@pytest.fixture
def as_admin():

    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    admin = User(id=1, username="admin", email="admin@bridgestone.com", role="ADMIN", is_active=True)
    db.add(admin)
    try:
        db.commit()
    except Exception:
        db.rollback()

    token = create_access_token({"sub": "admin", "role": "ADMIN"})
    app.dependency_overrides[get_db_context] = override_get_db
    app.dependency_overrides[get_current_user] = lambda: admin
    yield token
    app.dependency_overrides.clear()
    db.close()


@pytest.fixture
def as_employee():
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    emp = User(id=2, username="employee1", email="emp1@bridgestone.com", role="EMPLOYEE", is_active=True)
    db.add(emp)
    try:
        db.commit()
    except Exception:
        db.rollback()

    token = create_access_token({"sub": "employee1", "role": "EMPLOYEE"})
    app.dependency_overrides[get_db_context] = override_get_db
    app.dependency_overrides[get_current_user] = lambda: emp
    yield token
    app.dependency_overrides.clear()
    db.close()


# ─────────────────────────────────────────────────────────────────────────────
# 1. AI EVALUATION FRAMEWORK
# ─────────────────────────────────────────────────────────────────────────────

class TestAIEvaluation:

    def test_evaluation_metrics_service(self):
        metrics = get_ai_evaluation_metrics()
        assert "intent_classification_accuracy" in metrics
        assert "category_accuracy" in metrics
        assert "resolution_success_rate" in metrics
        assert "confidence_distribution" in metrics
        assert isinstance(metrics["confidence_distribution"], list)

    def test_evaluation_endpoint_as_admin(self, as_admin):
        resp = client.get("/api/admin/ai/evaluation", headers={"Authorization": f"Bearer {as_admin}"})
        assert resp.status_code == 200
        data = resp.json()
        assert "intent_classification_accuracy" in data
        assert "resolution_success_rate" in data


# ─────────────────────────────────────────────────────────────────────────────
# 2. PROMPT MANAGEMENT
# ─────────────────────────────────────────────────────────────────────────────

class TestPromptManagement:

    def test_get_all_prompts(self):
        prompts = get_all_prompts()
        assert isinstance(prompts, list)
        assert len(prompts) > 0

    def test_update_prompt_and_history(self):
        updated = update_prompt("BASE_SYSTEM_PROMPT", "New prompt content test v1.1", updated_by="admin")
        assert "version" in updated
        assert updated["content"] == "New prompt content test v1.1"

        history = get_prompt_history("BASE_SYSTEM_PROMPT")
        assert isinstance(history, list)

    def test_restore_prompt_version(self):
        v1 = update_prompt("CLASSIFICATION_PROMPT", "V1 Content", updated_by="admin")
        v2 = update_prompt("CLASSIFICATION_PROMPT", "V2 Content", updated_by="admin")

        restored = restore_prompt_version("CLASSIFICATION_PROMPT", v1["version"], restored_by="admin")
        assert restored is not None

    def test_preview_prompt_variables(self):
        preview = preview_prompt("BASE_SYSTEM_PROMPT", {"user": "Alice"})
        assert isinstance(preview, str)
        assert len(preview) > 0



# ─────────────────────────────────────────────────────────────────────────────
# 3. AI SETTINGS & MODEL HEALTH
# ─────────────────────────────────────────────────────────────────────────────

class TestAISettingsAndHealth:

    def test_get_and_update_ai_settings(self):
        settings = get_ai_settings()
        assert "provider" in settings
        assert "temperature" in settings

        updated = update_ai_settings({"temperature": 0.5}, updated_by="admin")
        assert updated["temperature"] == 0.5

    def test_model_health_stats(self):
        health = get_model_health_stats()
        assert "current_provider" in health
        assert "provider_status" in health
        assert "average_response_time_ms" in health
        assert "token_usage" in health

    def test_model_health_endpoint(self, as_admin):
        resp = client.get("/api/admin/ai/model-health", headers={"Authorization": f"Bearer {as_admin}"})
        assert resp.status_code == 200
        data = resp.json()
        assert "current_provider" in data


# ─────────────────────────────────────────────────────────────────────────────
# 4. AI FEEDBACK & CONVERSATION EXPLORER
# ─────────────────────────────────────────────────────────────────────────────

class TestAIFeedbackAndExplorer:

    def test_submit_feedback_and_summary(self):
        fb1 = submit_feedback("sess-101", "helpful", user_id="employee1", comment="Great job!")
        fb2 = submit_feedback("sess-102", "not_helpful", user_id="employee2", comment="Need more details")

        assert fb1["rating"] == "helpful"
        assert fb2["rating"] == "not_helpful"

        summary = get_feedback_summary()
        assert summary["total_feedback_count"] >= 2
        assert "user_satisfaction_percentage" in summary

    def test_submit_feedback_endpoint(self, as_employee):
        payload = {"session_id": "sess-201", "rating": "helpful", "comment": "Fast help!"}
        resp = client.post("/api/chat/feedback", json=payload, headers={"Authorization": f"Bearer {as_employee}"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["rating"] == "helpful"

    def test_conversation_explorer_search(self):
        convs = search_conversations(q=None, status_filter=None)
        assert isinstance(convs, list)


# ─────────────────────────────────────────────────────────────────────────────
# 5. ADMIN TOOLS & MULTI-AGENT EXTENSION POINTS
# ─────────────────────────────────────────────────────────────────────────────

class TestAdminToolsAndMultiAgent:

    def test_rebuild_index_endpoint(self, as_admin):
        resp = client.post("/api/admin/ai/rebuild-index", headers={"Authorization": f"Bearer {as_admin}"})
        assert resp.status_code == 200
        data = resp.json()
        assert "indexed_articles" in data

    def test_clear_cache_endpoint(self, as_admin):
        resp = client.post("/api/admin/ai/clear-cache", headers={"Authorization": f"Bearer {as_admin}"})
        assert resp.status_code == 200
        data = resp.json()
        assert "cleared successfully" in data["message"]


    def test_multi_agent_interface_stubs(self):
        triage = TriageAgentInterface()
        diagnostic = DiagnosticAgentInterface()
        action = ActionAgentInterface()

        assert triage.agent_name == "triage_agent"
        assert diagnostic.agent_name == "diagnostic_agent"
        assert action.agent_name == "action_agent"
        assert "intent_classification" in triage.capabilities
