"""
Unit & Integration Tests for Sprint 6: Enterprise Analytics & SLA Dashboard
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.database.base import Base
from app.database.models.user import User
from app.database.models.ticket import Ticket
from app.core.security import get_current_user, get_db_context

# In-memory SQLite DB for testing
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_database():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db_session():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


def test_analytics_overview_endpoint(db_session):
    """Verify GET /analytics/overview returns valid operational metrics."""
    admin = User(username="admin_sprint6", email="admin6@bridgestone.com", role="ADMIN", hashed_password="pw", is_active=True)
    db_session.add(admin)

    t1 = Ticket(ticket_id="INC6001", category="Software", description="Visio", assigned_team="Helpdesk", status="IN_PROGRESS", created_by="emp1", sla_state="HEALTHY")
    t2 = Ticket(ticket_id="INC6002", category="VPN", description="Cannot connect", assigned_team="Network", status="RESOLVED", created_by="emp2", sla_state="HEALTHY")
    db_session.add_all([t1, t2])
    db_session.commit()

    app.dependency_overrides[get_current_user] = lambda: admin
    app.dependency_overrides[get_db_context] = override_get_db

    res = client.get("/analytics/overview")
    assert res.status_code == 200
    data = res.json()
    assert "total_tickets" in data
    assert "open_tickets" in data
    assert "compliance_pct" in data
    assert data["total_tickets"] >= 2


def test_analytics_tickets_endpoint(db_session):
    """Verify GET /analytics/tickets returns status and priority distributions."""
    mgr = User(username="mgr_sprint6", email="mgr6@bridgestone.com", role="MANAGER", hashed_password="pw", is_active=True)
    db_session.add(mgr)

    t1 = Ticket(ticket_id="INC6003", category="Hardware", description="Keyboard broken", priority="HIGH", status="NEW", created_by="emp1")
    t2 = Ticket(ticket_id="INC6004", category="Database", description="Slow query", priority="CRITICAL", status="ASSIGNED", created_by="emp2")
    db_session.add_all([t1, t2])
    db_session.commit()

    app.dependency_overrides[get_current_user] = lambda: mgr
    app.dependency_overrides[get_db_context] = override_get_db

    res = client.get("/analytics/tickets")
    assert res.status_code == 200
    data = res.json()
    assert "status_distribution" in data
    assert "priority_distribution" in data


def test_analytics_sla_endpoint(db_session):
    """Verify GET /analytics/sla returns SLA health state breakdown."""
    admin = User(username="admin_sprint6", email="admin6@bridgestone.com", role="ADMIN", hashed_password="pw", is_active=True)
    db_session.add(admin)

    t1 = Ticket(ticket_id="INC6005", category="VPN", description="SLA Breach test", status="IN_PROGRESS", created_by="emp1", sla_state="BREACHED", sla_breached=True)
    db_session.add(t1)
    db_session.commit()

    app.dependency_overrides[get_current_user] = lambda: admin
    app.dependency_overrides[get_db_context] = override_get_db

    res = client.get("/analytics/sla")
    assert res.status_code == 200
    data = res.json()
    assert "breached" in data
    assert "compliance_pct" in data


def test_analytics_approvals_endpoint(db_session):
    """Verify GET /analytics/approvals returns approval metrics."""
    admin = User(username="admin_sprint6", email="admin6@bridgestone.com", role="ADMIN", hashed_password="pw", is_active=True)
    db_session.add(admin)

    t1 = Ticket(ticket_id="INC6006", category="Software", description="Approval test", status="WAITING_MANAGER", approval_status="PENDING", request_type="SERVICE_REQUEST", created_by="emp1")
    db_session.add(t1)
    db_session.commit()

    app.dependency_overrides[get_current_user] = lambda: admin
    app.dependency_overrides[get_db_context] = override_get_db

    res = client.get("/analytics/approvals")
    assert res.status_code == 200
    data = res.json()
    assert "pending_approvals" in data
    assert "approval_rate_pct" in data


def test_analytics_assignment_groups_endpoint(db_session):
    """Verify GET /analytics/assignment-groups returns workload metrics."""
    mgr = User(username="mgr_sprint6", email="mgr6@bridgestone.com", role="MANAGER", hashed_password="pw", is_active=True)
    db_session.add(mgr)

    t1 = Ticket(ticket_id="INC6007", category="Network", description="Router issue", assigned_team="Network", status="ASSIGNED", created_by="emp1")
    db_session.add(t1)
    db_session.commit()

    app.dependency_overrides[get_current_user] = lambda: mgr
    app.dependency_overrides[get_db_context] = override_get_db

    res = client.get("/analytics/assignment-groups")
    assert res.status_code == 200
    groups = res.json()
    assert isinstance(groups, list)
    assert any(g["group_name"] == "Network" for g in groups)


def test_analytics_users_endpoint(db_session):
    """Verify GET /analytics/users returns user metrics."""
    admin = User(username="admin_sprint6", email="admin6@bridgestone.com", role="ADMIN", hashed_password="pw", is_active=True)
    db_session.add(admin)

    app.dependency_overrides[get_current_user] = lambda: admin
    app.dependency_overrides[get_db_context] = override_get_db

    res = client.get("/analytics/users")
    assert res.status_code == 200
