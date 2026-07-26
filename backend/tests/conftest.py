"""
conftest.py — backend/tests/conftest.py
────────────────────────────────────────
Sets DATABASE_URL to an in-memory SQLite database BEFORE any app module is
imported. This prevents app.database.connection from trying to reach a real
PostgreSQL server during unit/integration tests.
"""

import os
import pytest

os.environ["DATABASE_URL"] = "sqlite:///:memory:"

from app.database.connection import engine
from app.database.base import Base
import app.database.models.ticket
import app.database.models.notification
import app.database.models.conversation
import app.database.models.user

@pytest.fixture(autouse=True)
def setup_db_tables():
    """Automatically create all tables in SQLite memory DB for every test."""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)
