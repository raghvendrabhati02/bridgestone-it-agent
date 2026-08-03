import os
import logging
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

# Load env vars from .env if present
load_dotenv()

logger = logging.getLogger("it-agent-backend")

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    DATABASE_URL = "postgresql://postgres:password@localhost:5432/bridgestone_it_agent"
    logger.warning("DATABASE_URL not found in env, defaulting to: %s", DATABASE_URL)

is_sqlite = False

try:
    logger.info("Initializing database engine for: %s", DATABASE_URL)
    if DATABASE_URL.startswith("postgresql"):
        engine = create_engine(
            DATABASE_URL,
            pool_size=20,
            max_overflow=10,
            pool_timeout=30,
            pool_recycle=1800,
            pool_pre_ping=True
        )
    elif DATABASE_URL.startswith("sqlite"):
        from sqlalchemy.pool import StaticPool
        engine = create_engine(
            DATABASE_URL,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool if ":memory:" in DATABASE_URL else None
        )
    else:
        engine = create_engine(DATABASE_URL)
    
    with engine.connect() as conn:
        pass
    logger.info("Database connection established successfully.")

except Exception as e:
    logger.warning("Failed to connect to configured database (%s): %s — Falling back to SQLite file database.", DATABASE_URL, e)
    DATABASE_URL = "sqlite:///./bridgestone_it_agent.db"
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
    from app.database.base import Base
    import app.database.models.ticket
    import app.database.models.notification
    import app.database.models.conversation
    import app.database.models.user
    Base.metadata.create_all(bind=engine)
    logger.info("SQLite fallback database initialized at bridgestone_it_agent.db")

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Automatic lightweight schema migration check for tickets and notifications table columns
try:
    with engine.begin() as conn:
        from sqlalchemy import text
        required_cols = {
            "servicenow_number": "VARCHAR(100)",
            "approved_by": "VARCHAR(100)",
            "approval_notes": "TEXT",
            "approved_at": "DATETIME",
            "laps_password": "VARCHAR(100)",
            "laps_expiration": "DATETIME",
            "laps_active": "BOOLEAN DEFAULT 0",
            "laps_audit_id": "VARCHAR(50)",
            "request_type": "VARCHAR(50)",
            "manager": "VARCHAR(100)",
            "approval_status": "VARCHAR(50)",
            "assignment_group": "VARCHAR(100)"
        }
        notif_required_cols = {
            "user_id": "VARCHAR(100)",
            "type": "VARCHAR(50)",
            "title": "VARCHAR(255)",
            "is_read": "BOOLEAN DEFAULT 0",
            "read_at": "DATETIME"
        }
        if "sqlite" in DATABASE_URL:
            cursor = conn.execute(text("PRAGMA table_info(tickets)"))
            existing_cols = [row[1] for row in cursor.fetchall()]
            if existing_cols:
                for col_name, col_type in required_cols.items():
                    if col_name not in existing_cols:
                        logger.info("Migrating SQLite DB: Adding column '%s' (%s) to 'tickets' table.", col_name, col_type)
                        try:
                            conn.execute(text(f"ALTER TABLE tickets ADD COLUMN {col_name} {col_type}"))
                        except Exception as col_err:
                            logger.warning("Failed to add column %s: %s", col_name, col_err)
            
            cursor_n = conn.execute(text("PRAGMA table_info(notifications)"))
            existing_n_cols = [row[1] for row in cursor_n.fetchall()]
            if existing_n_cols:
                for col_name, col_type in notif_required_cols.items():
                    if col_name not in existing_n_cols:
                        logger.info("Migrating SQLite DB: Adding column '%s' (%s) to 'notifications' table.", col_name, col_type)
                        try:
                            conn.execute(text(f"ALTER TABLE notifications ADD COLUMN {col_name} {col_type}"))
                        except Exception as col_err:
                            logger.warning("Failed to add column %s to notifications: %s", col_name, col_err)
        elif "postgresql" in DATABASE_URL:
            for col_name, col_type in required_cols.items():
                try:
                    conn.execute(text(f"ALTER TABLE tickets ADD COLUMN IF NOT EXISTS {col_name} {col_type}"))
                except Exception:
                    pass
            for col_name, col_type in notif_required_cols.items():
                try:
                    conn.execute(text(f"ALTER TABLE notifications ADD COLUMN IF NOT EXISTS {col_name} {col_type}"))
                except Exception:
                    pass
except Exception as exc:
    logger.debug("Database column migration check skipped: %s", exc)

# ==============================================================================
# Database Observability Hooks (SQLAlchemy event listeners)
# ==============================================================================
import time
from sqlalchemy import event

@event.listens_for(engine, "before_cursor_execute")
def before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    context._query_start_time = time.time()

@event.listens_for(engine, "after_cursor_execute")
def after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    if hasattr(context, "_query_start_time"):
        total_time = time.time() - context._query_start_time
        try:
            from app.core.metrics import DB_QUERY_DURATION_SECONDS, DB_TRANSACTIONS_TOTAL
            DB_QUERY_DURATION_SECONDS.observe(total_time)
            DB_TRANSACTIONS_TOTAL.inc()
        except Exception:
            pass

@event.listens_for(engine, "handle_error")
def handle_error(exception_context):
    try:
        from app.core.metrics import DB_FAILURES_TOTAL
        DB_FAILURES_TOTAL.inc()
    except Exception:
        pass

