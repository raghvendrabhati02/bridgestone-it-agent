from contextlib import contextmanager
from app.database.connection import SessionLocal

@contextmanager
def get_db():
    """
    Context manager yielding a transactional database session.
    Automatically handles session closing.
    """
    try:
        from app.core.metrics import DB_CONNECTIONS_ACTIVE
        DB_CONNECTIONS_ACTIVE.inc()
    except Exception:
        pass

    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
        try:
            from app.core.metrics import DB_CONNECTIONS_ACTIVE
            DB_CONNECTIONS_ACTIVE.dec()
        except Exception:
            pass

