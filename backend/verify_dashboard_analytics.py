"""
verify_dashboard_analytics.py
=============================
Integration verification for the Enterprise Analytics FastAPI REST API layer.
Tests schema, authorization (RBAC), empty database edge cases, and performance on large data.
"""

import sys
import os
import time
import json
from datetime import datetime, timedelta

# Add backend directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Force UTF-8 output on Windows terminals
if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

import logging
logging.disable(logging.CRITICAL)  # Suppress logging noise during tests

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.database.base import Base
import app.database.models  # Ensure all models are registered with Base.metadata
from app.database.models import Ticket, SessionModel, RbacAuditLog, SecurityEvent, ApprovalHistory, AgentTrace, User

# Database setup (file-based SQLite)
db_file = "test_analytics.db"
if os.path.exists(db_file):
    try:
        os.remove(db_file)
    except Exception:
        pass

engine = create_engine(f"sqlite:///{db_file}", connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine)
Base.metadata.create_all(bind=engine)
db = SessionLocal()

# FastAPI TestClient & app import
from fastapi.testclient import TestClient
from app.main import app

# Global mock user variables
mock_user_role = "ADMIN"
mock_username = "test_user"

# Dependency overrides
def mock_get_db():
    try:
        yield db
    finally:
        pass

def mock_get_current_user():
    return User(
        id=999,
        username=mock_username,
        email="test@company.com",
        hashed_password="hashed_password",
        role=mock_user_role,
        is_active=True
    )

from app.core.security import get_db_context, get_current_user
app.dependency_overrides[get_db_context] = mock_get_db
app.dependency_overrides[get_current_user] = mock_get_current_user

client = TestClient(app)

PASS = "\033[92mPASS\033[0m"
FAIL = "\033[91mFAIL\033[0m"
results = []

def check(name: str, condition: bool) -> None:
    status = PASS if condition else FAIL
    print(f"  [{status}] {name}")
    results.append((name, condition))

print("\n=== Enterprise Analytics REST API & Performance Verification ===\n")

# ── 1. Empty Database Edge Cases ─────────────────────────────────────────────
print("1. Testing empty database scenarios (Zero Division protection)...")
try:
    endpoints = ["overview", "tickets", "sla", "teams", "categories", "security", "root-causes", "users"]
    all_ok = True
    for endpoint in endpoints:
        res = client.get(f"/api/analytics/{endpoint}")
        if res.status_code != 200:
            print(f"  Failed endpoint: /api/analytics/{endpoint} -> {res.status_code}")
            all_ok = False
        else:
            # Simple check that the overview compliance is a float
            if endpoint == "overview":
                data = res.json()
                if data.get("compliance_pct") != 100.0:
                    print(f"  Expected 100.0 compliance, got {data.get('compliance_pct')}")
                    all_ok = False
            elif endpoint == "sla":
                data = res.json()
                if data.get("compliance_pct") != 100.0:
                    print(f"  Expected 100.0 SLA compliance, got {data.get('compliance_pct')}")
                    all_ok = False

    check("All endpoints return 200 OK on empty database without division by zero errors", all_ok)
except Exception as e:
    check(f"Empty database scenario failed: {e}", False)


# ── 2. Seed Data and Schema Validation ────────────────────────────────────────
print("\n2. Seeding sample dataset for schema validation...")
now = datetime.utcnow()

# Seed 1 ticket
t1 = Ticket(
    ticket_id="INC9901", category="VPN", issue_description="test vpn", description="test vpn",
    assigned_team="Network Team", status="OPEN", priority="HIGH", sla_hours=8,
    sla_state="HEALTHY", created_at=now - timedelta(hours=1), created_by="employee_test"
)
db.add(t1)

# Seed 1 session
sess = SessionModel(session_id="sess-test", status="ACTIVE", active_ticket="INC9901")
db.add(sess)

# Seed 1 login event
ev = SecurityEvent(event_type="LOGIN", username="employee_test", details="test login", created_at=now)
db.add(ev)

db.commit()

print("Validating endpoint response schemas...")
# Validate Overview Schema
res = client.get("/api/analytics/overview")
data = res.json()
expected_overview_keys = ["total_tickets", "open_tickets", "compliance_pct", "avg_resolution_hours", "active_users", "security_events"]
check("Overview response contains all expected keys", all(k in data for k in expected_overview_keys))

# Validate Tickets Schema
res = client.get("/api/analytics/tickets")
data = res.json()
expected_ticket_keys = ["total_tickets", "created_today", "created_this_week", "created_this_month", "status_distribution", "priority_distribution"]
check("Tickets response contains all expected keys", all(k in data for k in expected_ticket_keys))

# Validate SLA Schema
res = client.get("/api/analytics/sla")
data = res.json()
expected_sla_keys = ["healthy", "warning_75", "warning_90", "breached", "escalated_l1", "escalated_l2", "escalated_l3", "avg_sla_usage_pct", "compliance_pct", "avg_resolution_hours", "avg_first_response_hours"]
check("SLA response contains all expected keys", all(k in data for k in expected_sla_keys))

# Validate Root Cause Schema
res = client.get("/api/analytics/root-causes")
data = res.json()
expected_rc_keys = ["top_recurring_categories", "most_common_vpn_issue", "most_common_software_issue", "most_common_network_issue", "top_repeated_root_causes", "most_affected_support_team", "recommendations"]
check("Root Causes response contains all expected keys", all(k in data for k in expected_rc_keys))


# ── 3. Authorization (RBAC) Controls ──────────────────────────────────────────
print("\n3. Testing Role-Based Access Controls...")
# Change role to EMPLOYEE
mock_user_role = "EMPLOYEE"
res = client.get("/api/analytics/overview")
check("EMPLOYEE role is forbidden (403)", res.status_code == 403)

# Change role to MANAGER
mock_user_role = "MANAGER"
res = client.get("/api/analytics/overview")
check("MANAGER role is permitted (200)", res.status_code == 200)

# Change role to ADMIN
mock_user_role = "ADMIN"
res = client.get("/api/analytics/overview")
check("ADMIN role is permitted (200)", res.status_code == 200)


# ── 4. Large Dataset Performance Test ─────────────────────────────────────────
print("\n4. Testing calculations on a large dataset (Performance check)...")
print("Seeding 500 additional tickets, sessions, and events...")

large_tickets = []
large_sessions = []
large_events = []

for i in range(1, 501):
    large_tickets.append(Ticket(
        ticket_id=f"INC_PERF_{i}",
        category="VPN" if i % 2 == 0 else "Password reset",
        issue_description="Performance test issue description",
        description="Performance test issue description",
        assigned_team="Network Team" if i % 2 == 0 else "IT Support Team",
        status="OPEN" if i % 3 != 0 else "RESOLVED",
        priority="LOW" if i % 4 != 0 else "CRITICAL",
        sla_hours=24,
        sla_state="HEALTHY" if i % 3 != 0 else "BREACHED",
        created_at=now - timedelta(hours=i),
        created_by="perf_user"
    ))
    
    large_sessions.append(SessionModel(
        session_id=f"sess-perf-{i}",
        status="ACTIVE" if i % 2 == 0 else "CLOSED",
        active_ticket=f"INC_PERF_{i}" if i % 2 == 0 else ""
    ))
    
    large_events.append(SecurityEvent(
        event_type="LOGIN" if i % 2 == 0 else "PERMISSION_DENIED",
        username="perf_user",
        details="Perf logging details",
        created_at=now - timedelta(minutes=i)
    ))

db.add_all(large_tickets)
db.add_all(large_sessions)
db.add_all(large_events)
db.commit()

# Measure response latency
start_time = time.time()
res_overview = client.get("/api/analytics/overview")
overview_duration = time.time() - start_time

start_time = time.time()
res_rc = client.get("/api/analytics/root-causes")
rc_duration = time.time() - start_time

check(f"Overview query latency on large dataset is fast ({overview_duration:.4f}s)", overview_duration < 1.0)
check(f"Root Causes query latency on large dataset is fast ({rc_duration:.4f}s)", rc_duration < 1.0)
check("Overview response is successful", res_overview.status_code == 200)
check("Root Causes response is successful", res_rc.status_code == 200)

# Print Summary
print("\n" + "=" * 50)
all_passed = all(r[1] for r in results)
if all_passed:
    print(f"  ALL {len(results)} REST API & PERFORMANCE TESTS PASSED ✅")
else:
    print("  SOME TESTS FAILED ❌")
print("=" * 50 + "\n")

db.close()
engine.dispose()
if os.path.exists("test_analytics.db"):
    try:
        os.remove("test_analytics.db")
    except Exception:
        pass
sys.exit(0 if all_passed else 1)
