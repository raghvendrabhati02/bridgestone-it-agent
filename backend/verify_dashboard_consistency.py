# verify_dashboard_consistency.py
# Verification script for SLA and workload metric consistency between DB and API.

import os
import sys

# Set testing environment variable
os.environ["TESTING"] = "True"
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "app")))

from fastapi.testclient import TestClient
from app.main import app
from app.database.session import get_db
from app.database.models.ticket import Ticket

def test_dashboard_consistency():
    print("Running verify_dashboard_consistency...")
    client = TestClient(app)

    # 1. Login to get token for ADMIN role
    login_response = client.post("/auth/login", json={"username": "admin", "password": "adminpassword"})
    assert login_response.status_code == 200, "Admin login failed"
    token = login_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 2. Query Dashboard API metrics
    response = client.get("/admin/dashboard/executive-metrics", headers=headers)
    assert response.status_code == 200, f"Failed to get executive dashboard metrics: {response.text}"
    metrics = response.json()

    # 3. Query Database directly to compare counts
    with get_db() as db:
        tickets = db.query(Ticket).all()
        
        db_total_count = len(tickets)
        db_resolved_count = sum(1 for t in tickets if t.status in ("RESOLVED", "CLOSED"))
        db_open_count = db_total_count - db_resolved_count
        db_sla_breaches = sum(1 for t in tickets if t.sla_breached)
        db_sla_compliance_rate = round(((db_total_count - db_sla_breaches) / db_total_count * 100.0) if db_total_count else 100.0, 2)

    # Verify keys exist in response
    assert "total_breached_slas" in metrics, "total_breached_slas missing from API response"
    assert "sla_compliance_rate" in metrics, "sla_compliance_rate missing from API response"
    assert "aging_buckets" in metrics, "aging_buckets missing from API response"

    # Print DB vs API comparison
    api_sla_breaches = metrics.get("total_breached_slas")
    api_sla_compliance = metrics.get("sla_compliance_rate")
    api_aging_total = sum(metrics.get("aging_buckets", {}).values())

    print(f"  SLA Breaches      - API: {api_sla_breaches} | DB: {db_sla_breaches}")
    print(f"  SLA Compliance %  - API: {api_sla_compliance} | DB: {db_sla_compliance_rate}")
    print(f"  Open Tickets Age  - API Total: {api_aging_total} | DB Open: {db_open_count}")

    # Assert counts align exactly
    assert api_sla_breaches == db_sla_breaches, f"Mismatch on SLA breaches: API={api_sla_breaches}, DB={db_sla_breaches}"
    assert api_sla_compliance == db_sla_compliance_rate, f"Mismatch on SLA compliance rate: API={api_sla_compliance}, DB={db_sla_compliance_rate}"
    assert api_aging_total == db_open_count, f"Mismatch on open ticket aging total: API={api_aging_total}, DB={db_open_count}"

    print("[PASS] verify_dashboard_consistency.py: Executive metrics and DB counts align completely!")

if __name__ == "__main__":
    test_dashboard_consistency()
