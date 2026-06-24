import os
import sys
import time
from datetime import timedelta
import logging

# Set logging level to warning to keep stdout clean during tests
logging.basicConfig(level=logging.WARNING)

# Add app directory to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "app")))

from fastapi.testclient import TestClient
from app.main import app
from app.core.security import create_access_token
from app.database.session import get_db
from app.database.repositories.security_event_repository import SecurityEventRepository
from app.database.models.user import User

client = TestClient(app)

def test_login():
    print("Testing Login Endpoints...")
    
    # 1. Test Incorrect Login
    response = client.post("/auth/login", json={"username": "employee", "password": "wrongpassword"})
    assert response.status_code == 401, f"Expected 401, got {response.status_code}"
    print("[OK] Incorrect login correctly returns 401.")

    # Verify FAILED_LOGIN security event was created
    with get_db() as db:
        repo = SecurityEventRepository(db)
        logs = repo.get_all()
        assert any(l.event_type == "FAILED_LOGIN" and l.username == "employee" for l in logs), "Expected FAILED_LOGIN event in DB"
    print("[OK] FAILED_LOGIN security event recorded in database.")

    # 2. Test Correct Login (Employee)
    response = client.post("/auth/login", json={"username": "employee", "password": "employeepassword"})
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["user"]["role"] == "EMPLOYEE"
    print("[OK] Correct login returned access token for role EMPLOYEE.")

    # Verify LOGIN security event was created
    with get_db() as db:
        repo = SecurityEventRepository(db)
        logs = repo.get_all()
        assert any(l.event_type == "LOGIN" and l.username == "employee" for l in logs), "Expected LOGIN event in DB"
    print("[OK] LOGIN security event recorded in database.")

    return data["access_token"], data["refresh_token"]

def test_authorization(employee_token):
    print("\nTesting Role-Based Access Control...")
    
    # 1. Try accessing ADMIN-only route (/audit-logs) with Employee token
    headers = {"Authorization": f"Bearer {employee_token}"}
    response = client.get("/audit-logs", headers=headers)
    assert response.status_code == 403, f"Expected 403, got {response.status_code}"
    print("[OK] Employee blocked from accessing admin audit logs (403 Forbidden).")

    # Verify PERMISSION_DENIED security event was created
    with get_db() as db:
        repo = SecurityEventRepository(db)
        logs = repo.get_all()
        assert any(l.event_type == "PERMISSION_DENIED" and l.username == "employee" for l in logs), "Expected PERMISSION_DENIED event in DB"
    print("[OK] PERMISSION_DENIED security event recorded in database.")

    # 2. Login as Manager and check traces access
    res = client.post("/auth/login", json={"username": "manager", "password": "managerpassword"})
    manager_token = res.json()["access_token"]
    
    response = client.get("/agent-traces", headers={"Authorization": f"Bearer {manager_token}"})
    assert response.status_code == 403, f"Expected 403, got {response.status_code}"
    print("[OK] Manager blocked from accessing admin traces (403 Forbidden).")

    # 3. Login as Admin and check full access
    res = client.post("/auth/login", json={"username": "admin", "password": "adminpassword"})
    admin_token = res.json()["access_token"]
    
    response = client.get("/audit-logs", headers={"Authorization": f"Bearer {admin_token}"})
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    print("[OK] Admin successfully accessed audit logs.")

    response = client.get("/agent-traces", headers={"Authorization": f"Bearer {admin_token}"})
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    print("[OK] Admin successfully accessed agent traces.")

def test_jwt_expiration():
    print("\nTesting JWT Expiration...")
    
    # Generate token with 1 second lifetime
    exp_token = create_access_token(data={"sub": "employee", "role": "EMPLOYEE"}, expires_delta=timedelta(seconds=1))
    
    # Verify immediately succeeds
    headers = {"Authorization": f"Bearer {exp_token}"}
    res_immediate = client.get("/auth/me", headers=headers)
    assert res_immediate.status_code == 200, f"Expected 200, got {res_immediate.status_code}"
    print("[OK] Fresh token validates successfully.")

    # Wait for expiration
    print("Waiting 2 seconds for token expiration...")
    time.sleep(2)

    res_expired = client.get("/auth/me", headers=headers)
    assert res_expired.status_code == 401, f"Expected 401, got {res_expired.status_code}"
    assert res_expired.json()["detail"] == "Token has expired", f"Unexpected error detail: {res_expired.json()}"
    print("[OK] Expired token correctly rejected with HTTP 401 'Token has expired'.")

def test_token_refresh(refresh_token):
    print("\nTesting Token Refresh Endpoint...")
    response = client.post("/auth/refresh", json={"refresh_token": refresh_token})
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    data = response.json()
    assert "access_token" in data
    print("[OK] Token refresh successfully returned a new access token.")

def test_health():
    print("\nTesting Health Check Endpoint...")
    response = client.get("/health")
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    data = response.json()
    assert "status" in data
    assert "database" in data
    assert "redis" in data
    assert "gemini" in data
    assert "adapters" in data
    print(f"[OK] Health endpoint returned: {data}")

def run_all_tests():
    print("=========================================")
    print("   STARTING ENTERPRISE SECURITY TESTS    ")
    print("=========================================")
    try:
        emp_token, emp_refresh = test_login()
        test_authorization(emp_token)
        test_jwt_expiration()
        test_token_refresh(emp_refresh)
        test_health()
        print("\n=========================================")
        print("   ALL SECURITY VERIFICATIONS PASSED!    ")
        print("=========================================")
    except AssertionError as e:
        print(f"\n[FAIL] Assertion error occurred: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n[ERROR] Test failed with exception: {e}")
        sys.exit(1)

if __name__ == "__main__":
    run_all_tests()
