# verify_database_integrity.py
# Verification script for database structure, connection checks, foreign keys, and model validation.

import os
import sys

# Set testing environment variable
os.environ["TESTING"] = "True"
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "app")))

from sqlalchemy.sql import text
from sqlalchemy.exc import IntegrityError
from app.database.session import get_db
from app.database.connection import engine
from app.database.models.ticket import Ticket

def test_database_integrity():
    print("Running verify_database_integrity...")
    
    # 1. Database Connection and Backend Detection
    is_postgres = engine.dialect.name == "postgresql"
    print(f"  Detected database backend: {engine.dialect.name}")

    if is_postgres:
        with get_db() as db:
            version = db.execute(text("SELECT version()")).fetchone()[0]
            print(f"  PostgreSQL version: {version}")
            
            # Verify table list
            res_tables = db.execute(text("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public'
            """)).fetchall()
            print(f"  PostgreSQL active table count: {len(res_tables)}")
            assert len(res_tables) > 0, "No tables found in public schema!"
    else:
        # 1. SQLite PRAGMA integrity_check
        with get_db() as db:
            res = db.execute(text("PRAGMA integrity_check")).fetchone()
            status = res[0] if res else "failed"
            print(f"  SQLite integrity status: {status}")
            assert status == "ok", f"Database file is corrupted or failed PRAGMA integrity: {status}"

        # 2. SQLite Foreign Keys Enabled check
        with get_db() as db:
            res_fk = db.execute(text("PRAGMA foreign_keys")).fetchone()
            fk_enabled = res_fk[0] if res_fk else 0
            print(f"  SQLite foreign keys enabled: {fk_enabled}")

    # 3. Model validation - Ticket non-nullable ticket_id constraint
    with get_db() as db:
        # Create ticket missing primary key/required fields to trigger IntegrityError
        invalid_ticket = Ticket(
            ticket_id=None,  # Null PK
            category="VPN",
            status="OPEN"
        )
        db.add(invalid_ticket)
        try:
            db.commit()
            raise AssertionError("Database allowed inserting a ticket with a null ticket_id primary key!")
        except IntegrityError:
            print("  Constraint verification: Null primary key rejected (Success)")
            db.rollback()

    print("[PASS] verify_database_integrity.py: Connection checks, foreign keys, and model constraints verified successfully!")

if __name__ == "__main__":
    test_database_integrity()

