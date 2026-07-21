from contextlib import contextmanager
from app.database.connection import SessionLocal

@contextmanager
def get_db():
    """
    Context manager yielding a transactional database session.
    Rolls back on any exception so that broken transactions are never
    returned to the connection pool; re-raises so callers still see the error.
    Commits are the responsibility of each caller (e.g. TicketRepository.save_ticket).
    """
    try:
        from app.core.metrics import DB_CONNECTIONS_ACTIVE
        DB_CONNECTIONS_ACTIVE.inc()
    except Exception:
        pass

    db = SessionLocal()
    try:
        yield db
    except Exception:
        # Rollback any in-flight transaction before closing so the underlying
        # connection is returned to the pool in a clean state.
        db.rollback()
        raise
    finally:
        db.close()
        try:
            from app.core.metrics import DB_CONNECTIONS_ACTIVE
            DB_CONNECTIONS_ACTIVE.dec()
        except Exception:
            pass

