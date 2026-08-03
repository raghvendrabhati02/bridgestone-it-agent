"""
test_auto_seed.py
──────────────────────────────────────────────────────────────────────────────
Tests automatic user database seeding on startup and authentication.
"""

import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.database.connection import SessionLocal
from app.database.models.user import User


def test_auto_seed_fresh_db_and_skip_existing():
    # 1. Clear main User table to simulate fresh database deployment
    db = SessionLocal()
    db.query(User).delete()
    db.commit()
    db.close()

    # 2. Trigger lifespan startup context on fresh database (auto-seeding)
    with TestClient(app) as client:
        # Verify authentication for admin / manager / employee
        credentials = [
            ("admin", "adminpassword"),
            ("manager", "managerpassword"),
            ("employee", "employeepassword"),
        ]

        for username, password in credentials:
            resp = client.post(
                "/auth/login",
                json={"username": username, "password": password}
            )
            assert resp.status_code == 200, f"Login failed for {username}: {resp.text}"
            data = resp.json()
            assert "access_token" in data
            assert data["token_type"] == "bearer"
            assert data["user"]["username"] == username

    # 3. Trigger startup context when users exist (must skip seeding without duplicates)
    with TestClient(app) as client2:
        db = SessionLocal()
        users_after = db.query(User).all()
        db.close()
        assert len(users_after) == 3
