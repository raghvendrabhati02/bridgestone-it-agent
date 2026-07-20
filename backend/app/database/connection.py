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
    else:
        engine = create_engine(DATABASE_URL)
    
    with engine.connect() as conn:
        pass
    logger.info("PostgreSQL database connection established successfully.")
except Exception as e:
    logger.error("Failed to connect to configured database (%s): %s", DATABASE_URL, e)
    raise RuntimeError(f"Database connection failed: {e}")

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

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

