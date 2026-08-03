"""
database.py
─────────────────────────────────────────────────────────────────────────────
Database engine, session management, and seed data initialization for Mock ITSM.
Initially backed by SQLite (or configured DATABASE_URL), compatible with PostgreSQL.
"""

import os
import logging
from contextlib import contextmanager
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from app.database.base import Base

logger = logging.getLogger("it-agent-backend")

# Use configured DATABASE_URL or default to local SQLite database file
MOCK_ITSM_DATABASE_URL = os.getenv("MOCK_ITSM_DATABASE_URL") or os.getenv("DATABASE_URL")
if not MOCK_ITSM_DATABASE_URL or MOCK_ITSM_DATABASE_URL.startswith("postgresql"):
    # Default SQLite database path for Mock ITSM self-contained storage
    MOCK_ITSM_DATABASE_URL = "sqlite:///./bridgestone_it_agent.db"

connect_args = {"check_same_thread": False, "timeout": 60} if MOCK_ITSM_DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(MOCK_ITSM_DATABASE_URL, connect_args=connect_args)
MockITSMSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@contextmanager
def get_mock_itsm_db():
    """Provides a transactional scope around a series of operations."""
    db = MockITSMSessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def init_mock_itsm_db():
    """
    Creates all tables for the Mock ITSM module and seeds default data.
    """
    from app.mock_itsm.models.mock_ticket import MockTicket
    from app.mock_itsm.models.mock_ticket_history import MockTicketHistory
    from app.mock_itsm.models.mock_approval import MockApproval
    from app.mock_itsm.models.mock_approval_history import MockApprovalHistory
    from app.mock_itsm.models.mock_approval_comment import MockApprovalComment
    from app.mock_itsm.models.mock_notification import MockNotification
    from app.mock_itsm.models.mock_assignment_group import MockAssignmentGroup
    from app.mock_itsm.models.mock_audit_log import MockAuditLog
    from app.mock_itsm.models.mock_user import MockUser

    Base.metadata.create_all(bind=engine)
    logger.info("Mock ITSM tables verified/created successfully.")

    # Lightweight SQLite schema migration for mock_approvals
    try:
        from sqlalchemy import text
        with engine.begin() as conn:
            if "sqlite" in MOCK_ITSM_DATABASE_URL:
                cursor = conn.execute(text("PRAGMA table_info(mock_approvals)"))
                cols = [row[1] for row in cursor.fetchall()]
                new_cols = {
                    "requester": "VARCHAR(100) DEFAULT 'employee'",
                    "approver": "VARCHAR(100)",
                    "approver_username": "VARCHAR(100)",
                    "approval_type": "VARCHAR(50) DEFAULT 'Admin Access'",
                    "decision": "VARCHAR(50)",
                    "comments": "TEXT",
                    "created_at": "DATETIME",
                    "updated_at": "DATETIME",
                }
                for c_name, c_type in new_cols.items():
                    if c_name not in cols:
                        conn.execute(text(f"ALTER TABLE mock_approvals ADD COLUMN {c_name} {c_type}"))

                # Migrate mock_notifications columns
                cursor_notif = conn.execute(text("PRAGMA table_info(mock_notifications)"))
                notif_cols = [row[1] for row in cursor_notif.fetchall()]
                new_notif_cols = {
                    "user_id": "VARCHAR(100) DEFAULT 'employee'",
                    "ticket_id": "VARCHAR(50)",
                    "type": "VARCHAR(50) DEFAULT 'INFO'",
                    "title": "VARCHAR(200) DEFAULT 'Notification'",
                    "is_read": "BOOLEAN DEFAULT 0",
                    "read_at": "DATETIME",
                }
                for c_name, c_type in new_notif_cols.items():
                    if c_name not in notif_cols:
                        conn.execute(text(f"ALTER TABLE mock_notifications ADD COLUMN {c_name} {c_type}"))
    except Exception as mig_err:
        logger.debug("Mock ITSM column migration notice: %s", mig_err)

    # Seed Default Data
    seed_default_assignment_groups()
    seed_default_users()


def seed_default_assignment_groups():
    """Seeds required assignment groups if not already present."""
    from app.mock_itsm.models.mock_assignment_group import MockAssignmentGroup

    default_groups = [
        {"group_name": "Network Team", "description": "Handles VPN, Wi-Fi, routers, and connectivity issues"},
        {"group_name": "Microsoft 365 Team", "description": "Handles Outlook, Teams, Exchange, and Office suite issues"},
        {"group_name": "Software Support", "description": "Handles software installation, licensing, and application issues"},
        {"group_name": "Hardware Support", "description": "Handles laptops, printers, monitors, and physical hardware"},
        {"group_name": "Security Team", "description": "Handles security incidents, admin privileges, access requests"},
        {"group_name": "Service Desk", "description": "General IT support and initial triage team"}
    ]

    with get_mock_itsm_db() as db:
        for grp in default_groups:
            existing = db.query(MockAssignmentGroup).filter_by(group_name=grp["group_name"]).first()
            if not existing:
                db.add(MockAssignmentGroup(group_name=grp["group_name"], description=grp["description"]))
                logger.info("Mock ITSM: Seeded assignment group '%s'", grp["group_name"])


def seed_default_users():
    """Seeds test users across roles (Employee, Manager, Engineer, Admin)."""
    from app.mock_itsm.models.mock_user import MockUser

    default_users = [
        {"username": "employee", "email": "employee@example.com", "role": "EMPLOYEE", "manager_username": "manager"},
        {"username": "manager", "email": "manager@example.com", "role": "MANAGER", "manager_username": "admin"},
        {"username": "engineer", "email": "engineer@example.com", "role": "ENGINEER", "manager_username": "manager"},
        {"username": "admin", "email": "admin@example.com", "role": "ADMIN", "manager_username": None},
    ]

    with get_mock_itsm_db() as db:
        for u in default_users:
            existing = db.query(MockUser).filter_by(username=u["username"]).first()
            if not existing:
                db.add(MockUser(
                    username=u["username"],
                    email=u["email"],
                    role=u["role"],
                    manager_username=u["manager_username"]
                ))
                logger.info("Mock ITSM: Seeded user '%s' (%s)", u["username"], u["role"])
