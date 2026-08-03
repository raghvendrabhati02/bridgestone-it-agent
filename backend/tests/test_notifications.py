import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.database.base import Base
from app.database.models.user import User
from app.database.models.ticket import Ticket
from app.database.models.notification import Notification
from app.services.notification_service import NotificationService
from app.core.security import get_current_user, get_db_context

# Use SQLite with StaticPool so all connections share the same in-memory DB
TEST_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db_session(setup_db):
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


client = TestClient(app)


def test_notification_service_direct_events(db_session):
    """Verify all required NotificationService methods create audit-logged notifications."""
    ticket = {
        "ticket_id": "INC9901",
        "category": "VPN Access",
        "created_by": "emp_john",
        "manager": "mgr_sarah",
        "assigned_engineer": "eng_mike",
        "status": "NEW"
    }

    # 1. Ticket Created
    notifs_created = NotificationService.notify_ticket_created(ticket, db=db_session)
    assert len(notifs_created) > 0
    assert any(n["user_id"] == "emp_john" for n in notifs_created)

    # 2. Assignment
    notifs_assign = NotificationService.notify_assignment(ticket, db=db_session)
    assert len(notifs_assign) > 0
    assert any(n["type"] in ("TICKET_ASSIGNED", "ASSIGNMENT_CHANGED") for n in notifs_assign)

    # 3. Status Change
    notifs_status = NotificationService.notify_status_change(ticket, previous_status="NEW", db=db_session)
    assert len(notifs_status) > 0

    # 4. Approval Requested & Approved
    notifs_appr_req = NotificationService.notify_approval(ticket, approval_type="VPN", status="PENDING", db=db_session)
    assert any(n["type"] == "APPROVAL_REQUESTED" for n in notifs_appr_req)

    notifs_appr_grant = NotificationService.notify_approval(ticket, approval_type="VPN", status="APPROVED", approver="mgr_sarah", db=db_session)
    assert any(n["type"] == "APPROVAL_APPROVED" for n in notifs_appr_grant)

    # 5. Resolution
    notifs_res = NotificationService.notify_resolution(ticket, db=db_session)
    assert any(n["type"] == "TICKET_RESOLVED" for n in notifs_res)

    # 6. SLA
    notifs_sla = NotificationService.notify_sla(ticket, event_type="SLA Breach", db=db_session)
    assert any(n["type"] == "SLA_BREACH" for n in notifs_sla)

    # 7. Comment Added
    notifs_comment = NotificationService.notify_comment_added(ticket, comment_author="mgr_sarah", comment_text="Please verify IP.", db=db_session)
    assert any(n["type"] == "COMMENT_ADDED" for n in notifs_comment)


def test_create_ticket_flow_generates_notification(db_session):
    """Verify Create Ticket -> Notification appears."""
    user = User(username="emp_john", email="john@bridgestone.com", role="EMPLOYEE", hashed_password="pw", is_active=True)
    db_session.add(user)
    db_session.commit()

    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db_context] = override_get_db

    try:
        res = client.post(
            "/ticket",
            json={"category": "Software", "issue_description": "Photoshop request"}
        )
        assert res.status_code == 200
        ticket_id = res.json().get("ticket_id")

        res_notif = client.get("/notifications")
        assert res_notif.status_code == 200
        notifs = res_notif.json()
        assert len(notifs) >= 1
        assert any(n.get("ticket_id") == ticket_id or ticket_id in n.get("message", "") for n in notifs)
    finally:
        app.dependency_overrides.clear()


def test_approval_request_flow_generates_notification(db_session):
    """Verify Approve Request -> Notification appears."""
    employee = User(username="emp_john", email="john@bridgestone.com", role="EMPLOYEE", hashed_password="pw", is_active=True)
    manager = User(username="mgr_sarah", email="sarah@bridgestone.com", role="MANAGER", hashed_password="pw", is_active=True)
    db_session.add_all([employee, manager])

    t = Ticket(
        ticket_id="INC8808",
        category="Privileged Access",
        issue_description="Admin access",
        created_by="emp_john",
        manager="mgr_sarah",
        request_type="PRIVILEGED_ACTION",
        status="WAITING_MANAGER",
        approval_status="PENDING"
    )
    db_session.add(t)
    db_session.commit()

    app.dependency_overrides[get_current_user] = lambda: manager
    app.dependency_overrides[get_db_context] = override_get_db

    try:
        res_appr = client.post(
            "/tickets/INC8808/action",
            json={"action": "manager_approve", "note": "Approved"}
        )
        assert res_appr.status_code == 200

        # Check notifications for employee
        app.dependency_overrides[get_current_user] = lambda: employee
        res_notif = client.get("/notifications")
        assert res_notif.status_code == 200
        notifs = res_notif.json()
        assert any(n.get("ticket_id") == "INC8808" and n.get("type") in ("APPROVAL_APPROVED", "TICKET_CREATED", "GENERAL") for n in notifs)
    finally:
        app.dependency_overrides.clear()


def test_resolve_ticket_generates_notification(db_session):
    """Verify Resolve Ticket -> Notification appears."""
    employee = User(username="emp_john", email="john@bridgestone.com", role="EMPLOYEE", hashed_password="pw", is_active=True)
    admin = User(username="admin_alex", email="alex@bridgestone.com", role="ADMIN", hashed_password="pw", is_active=True)
    db_session.add_all([employee, admin])

    t = Ticket(
        ticket_id="INC7707",
        category="Network",
        issue_description="WiFi disconnected",
        created_by="emp_john",
        status="IN_PROGRESS"
    )
    db_session.add(t)
    db_session.commit()

    app.dependency_overrides[get_current_user] = lambda: admin
    app.dependency_overrides[get_db_context] = override_get_db

    try:
        res_resolve = client.post(
            "/tickets/INC7707/action",
            json={"action": "resolve", "note": "Fixed router"}
        )
        assert res_resolve.status_code == 200

        app.dependency_overrides[get_current_user] = lambda: employee
        res_notif = client.get("/notifications")
        assert res_notif.status_code == 200
        notifs = res_notif.json()
        assert any(n.get("ticket_id") == "INC7707" for n in notifs)
    finally:
        app.dependency_overrides.clear()


def test_mark_read_decreases_unread_count(db_session):
    """Verify Mark Read -> Unread count decreases."""
    employee = User(username="emp_john", email="john@bridgestone.com", role="EMPLOYEE", hashed_password="pw", is_active=True)
    db_session.add(employee)
    db_session.commit()

    NotificationService.create_notification(user_id="emp_john", type="TICKET_CREATED", title="N1", message="M1", ticket_id="INC101", db=db_session)
    NotificationService.create_notification(user_id="emp_john", type="STATUS_CHANGED", title="N2", message="M2", ticket_id="INC102", db=db_session)
    NotificationService.create_notification(user_id="emp_john", type="SLA_WARNING", title="N3", message="M3", ticket_id="INC103", db=db_session)

    app.dependency_overrides[get_current_user] = lambda: employee
    app.dependency_overrides[get_db_context] = override_get_db

    try:
        res_unread1 = client.get("/notifications/unread")
        assert res_unread1.status_code == 200
        data1 = res_unread1.json()
        initial_count = data1["unread_count"]
        assert initial_count >= 3

        first_notif_id = data1["notifications"][0]["id"]

        # Mark read
        res_read = client.post(f"/notifications/read/{first_notif_id}")
        assert res_read.status_code == 200

        res_unread2 = client.get("/notifications/unread")
        assert res_unread2.status_code == 200
        assert res_unread2.json()["unread_count"] == initial_count - 1

        # Mark all read
        res_read_all = client.post("/notifications/read-all")
        assert res_read_all.status_code == 200

        res_unread3 = client.get("/notifications/unread")
        assert res_unread3.status_code == 200
        assert res_unread3.json()["unread_count"] == 0
    finally:
        app.dependency_overrides.clear()


def test_delete_notification(db_session):
    """Verify DELETE /notifications/{id} works."""
    employee = User(username="emp_john", email="john@bridgestone.com", role="EMPLOYEE", hashed_password="pw", is_active=True)
    db_session.add(employee)
    db_session.commit()

    notif = NotificationService.create_notification(user_id="emp_john", type="GENERAL", title="Del test", message="Del msg", ticket_id="INC999", db=db_session)
    notif_id = notif["id"]

    app.dependency_overrides[get_current_user] = lambda: employee
    app.dependency_overrides[get_db_context] = override_get_db

    try:
        res_del = client.delete(f"/notifications/{notif_id}")
        assert res_del.status_code == 200
        assert res_del.json()["message"] == "Notification deleted"

        res_list = client.get("/notifications")
        assert res_list.status_code == 200
        assert not any(n["id"] == notif_id for n in res_list.json())
    finally:
        app.dependency_overrides.clear()
