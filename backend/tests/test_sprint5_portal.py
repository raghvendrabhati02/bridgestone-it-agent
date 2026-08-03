"""
Unit & Integration Tests for Sprint 5: Enterprise ITSM Dashboards & Ticket Management Portal
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
from app.database.models.workflow_models import TicketComment, TicketTimeline
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


def test_employee_creates_ticket_and_queries_my_tickets(db_session):
    """Verify employee can create a ticket and retrieve it from /my-tickets."""
    user = User(username="emp_sprint5", email="emp5@bridgestone.com", role="EMPLOYEE", hashed_password="pw", is_active=True)
    db_session.add(user)
    ticket = Ticket(
        ticket_id="INC000500",
        category="Software",
        description="Request license for Photoshop",
        issue_description="Request license for Photoshop",
        assigned_team="Helpdesk",
        status="NEW",
        created_by="emp_sprint5"
    )
    db_session.add(ticket)
    db_session.commit()

    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db_context] = override_get_db

    # Fetch /my-tickets
    res_my = client.get("/my-tickets")
    assert res_my.status_code == 200
    my_tickets = res_my.json()
    assert any(t["ticket_id"] == "INC000500" for t in my_tickets)


def test_manager_sees_and_approves_ticket(db_session):
    """Verify manager sees pending ticket and can approve it."""
    emp = User(username="emp_john", email="john@bridgestone.com", role="EMPLOYEE", hashed_password="pw", is_active=True)
    mgr = User(username="mgr_sarah", email="sarah@bridgestone.com", role="MANAGER", hashed_password="pw", is_active=True)
    db_session.add_all([emp, mgr])
    db_session.commit()

    # Create a service request ticket requiring approval
    ticket = Ticket(
        ticket_id="INC000501",
        category="Software",
        description="Need Visio license",
        issue_description="Need Visio license",
        assigned_team="Helpdesk",
        status="WAITING_MANAGER",
        created_by="emp_john",
        request_type="SERVICE_REQUEST",
        approval_status="PENDING",
        manager="mgr_sarah"
    )
    db_session.add(ticket)
    db_session.commit()

    # Override current user as manager
    app.dependency_overrides[get_current_user] = lambda: mgr
    app.dependency_overrides[get_db_context] = override_get_db

    # Query manager tickets
    res_mgr = client.get("/api/itsm/manager-tickets")
    assert res_mgr.status_code == 200
    data = res_mgr.json()
    assert data["count"] >= 1

    # Manager approves ticket
    res_app = client.post(
        f"/api/itsm/manager-tickets/{ticket.ticket_id}/approve",
        json={"reason": "Approved for business use."}
    )
    assert res_app.status_code == 200
    assert res_app.json()["status"] in ("APPROVED", "READY_FOR_ADMIN", "COMPLETED")


def test_admin_portal_users_and_assignment_groups(db_session):
    """Verify Admin can query users, assignment groups, and delete a ticket."""
    admin = User(username="admin_alex", email="alex@bridgestone.com", role="ADMIN", hashed_password="pw", is_active=True)
    db_session.add(admin)

    ticket = Ticket(
        ticket_id="INC000502",
        category="Hardware",
        description="Monitor flickers",
        issue_description="Monitor flickers",
        assigned_team="Hardware",
        status="NEW",
        created_by="admin_alex"
    )
    db_session.add(ticket)
    db_session.commit()

    app.dependency_overrides[get_current_user] = lambda: admin
    app.dependency_overrides[get_db_context] = override_get_db

    # GET /api/itsm/users
    res_users = client.get("/api/itsm/users")
    assert res_users.status_code == 200
    users_list = res_users.json()
    assert any(u["username"] == "admin_alex" for u in users_list)

    # GET /api/itsm/assignment-groups
    res_groups = client.get("/api/itsm/assignment-groups")
    assert res_groups.status_code == 200
    groups_data = res_groups.json()
    assert "assignment_groups" in groups_data
    assert len(groups_data["assignment_groups"]) >= 5

    # Admin updates ticket
    res_update = client.post(
        f"/tickets/{ticket.ticket_id}/update",
        json={"priority": "HIGH", "assigned_team": "Hardware"}
    )
    assert res_update.status_code == 200

    # Admin deletes ticket
    res_del = client.delete(f"/tickets/{ticket.ticket_id}")
    assert res_del.status_code == 200
    assert res_del.json()["ticket_id"] == ticket.ticket_id


def test_ticket_details_timeline_and_comments(db_session):
    """Verify ticket details, timeline, and posting comments."""
    user = User(username="emp_john", email="john@bridgestone.com", role="EMPLOYEE", hashed_password="pw", is_active=True)
    db_session.add(user)

    ticket = Ticket(
        ticket_id="INC000503",
        category="VPN",
        description="Cannot connect to VPN",
        issue_description="Cannot connect to VPN",
        assigned_team="Network",
        status="IN_PROGRESS",
        created_by="emp_john"
    )
    db_session.add(ticket)
    db_session.commit()

    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db_context] = override_get_db

    # Post comment
    res_comm = client.post(
        f"/tickets/{ticket.ticket_id}/comments",
        json={"text": "Tried restarting Cisco AnyConnect client.", "is_internal": False}
    )
    assert res_comm.status_code == 200

    # GET /tickets/{id}/details
    res_det = client.get(f"/tickets/{ticket.ticket_id}/details")
    assert res_det.status_code == 200
    details = res_det.json()
    assert details["ticket"]["ticket_id"] == ticket.ticket_id
    assert len(details["comments"]) >= 1
    assert details["comments"][0]["text"] == "Tried restarting Cisco AnyConnect client."
