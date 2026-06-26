"""
verify_sla_dashboard.py
=======================
Tests:
  1. Dashboard metrics API returns expected keys
  2. Counts are consistent with DB state
  3. compliance_pct is calculated correctly
  4. get_escalation_history() returns records
  5. All PASS summary
"""

import sys
import os
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
from app.database.models.ticket import Ticket
from app.database.models.sla_escalation_history import SlaEscalationHistory

# Setup in-memory SQLite DB
engine = create_engine("sqlite:///:memory:")
SessionLocal = sessionmaker(bind=engine)
Base.metadata.create_all(bind=engine)
db = SessionLocal()

PASS = "\033[92mPASS\033[0m"
FAIL = "\033[91mFAIL\033[0m"
results = []

def check(name: str, condition: bool) -> None:
    status = PASS if condition else FAIL
    print(f"  [{status}] {name}")
    results.append((name, condition))

print("\n=== SLA Dashboard Metrics Verification ===\n")

# ── Test imports ──────────────────────────────────────────────────────────────
print("1. Importing dashboard functions...")
try:
    from app.services.sla_escalation_service import (
        get_dashboard_metrics,
        get_escalation_history,
        HEALTHY,
        WARNING_75,
        WARNING_90,
        BREACHED,
        ESCALATED_LEVEL_1,
        ESCALATED_LEVEL_2,
        ESCALATED_LEVEL_3
    )
    check("Imports succeed cleanly", True)
except Exception as e:
    check(f"Import failed: {e}", False)
    sys.exit(1)

# ── Mock database session in get_db context ──────────────────────────────────
# To test the service methods which call with get_db() internally, we need to mock
# app.database.session.get_db to return our in-memory session.
print("\n2. Mocking database get_db context...")
from contextlib import contextmanager

@contextmanager
def mock_get_db():
    yield db

import app.database.session
app.database.session.get_db = mock_get_db
check("get_db successfully mocked", True)

# ── Seed data for metrics ────────────────────────────────────────────────────
print("\n3. Seeding tickets for metrics check...")

now = datetime.utcnow()

# Active tickets
t1 = Ticket(ticket_id="INC-01", category="Software", priority="LOW", status="OPEN", created_at=now, sla_state=HEALTHY, sla_hours=24)
t2 = Ticket(ticket_id="INC-02", category="Hardware", priority="MEDIUM", status="IN_PROGRESS", created_at=now - timedelta(hours=8), sla_state=WARNING_75, sla_hours=10)
t3 = Ticket(ticket_id="INC-03", category="Network", priority="HIGH", status="ASSIGNED", created_at=now - timedelta(hours=5), sla_state=WARNING_90, sla_hours=5)
t4 = Ticket(ticket_id="INC-04", category="Access", priority="CRITICAL", status="OPEN", created_at=now - timedelta(hours=3), sla_state=BREACHED, sla_breached=True, sla_breached_at=now - timedelta(hours=1), sla_hours=2)
t5 = Ticket(ticket_id="INC-05", category="Software", priority="HIGH", status="IN_PROGRESS", created_at=now - timedelta(hours=6), sla_state=ESCALATED_LEVEL_1, sla_breached=True, sla_breached_at=now - timedelta(hours=2), sla_hours=4)

# Resolved tickets
t6 = Ticket(ticket_id="INC-06", category="Hardware", priority="LOW", status="RESOLVED", created_at=now - timedelta(hours=12), sla_state=HEALTHY, sla_hours=24)
t7 = Ticket(ticket_id="INC-07", category="Software", priority="MEDIUM", status="CLOSED", created_at=now - timedelta(hours=4), sla_state=HEALTHY, sla_hours=12)

db.add_all([t1, t2, t3, t4, t5, t6, t7])
db.commit()

# Seed escalation history
db.add_all([
    SlaEscalationHistory(ticket_id="INC-04", level=1, reason="SLA Breached L1", created_at=now - timedelta(hours=1)),
    SlaEscalationHistory(ticket_id="INC-05", level=1, reason="SLA Breached L1", created_at=now - timedelta(hours=2)),
])
db.commit()

# ── Retrieve Dashboard Metrics ───────────────────────────────────────────────
print("\n4. Evaluating dashboard metrics calculations...")
metrics = get_dashboard_metrics()

expected_keys = [
    "open", "resolved_today", "healthy", "warning_75", "warning_90",
    "breached", "escalated_l1", "escalated_l2", "escalated_l3",
    "avg_resolution_hours", "avg_sla_usage_pct", "compliance_pct"
]
check("Metrics return dictionary contains all expected keys", all(k in metrics for k in expected_keys))

# Counts check
check("Active tickets count matches open", metrics["open"] == 5)
check("Resolved tickets count matches resolved_today", metrics["resolved_today"] == 2)
check("Healthy active count is 1", metrics["healthy"] == 1)
check("Warning 75 count is 1", metrics["warning_75"] == 1)
check("Warning 90 count is 1", metrics["warning_90"] == 1)
check("Breached count is 1", metrics["breached"] == 1)
check("Escalated L1 count is 1", metrics["escalated_l1"] == 1)

# Compliance Check:
# Total active = 5
# Breached active = breached (1) + escalated_l1 (1) = 2
# Compliance % = ((5 - 2) / 5) * 100 = 60.0%
check("Compliance percentage calculated correctly (60.0%)", metrics["compliance_pct"] == 60.0)

# Averages check
check("Average resolution hours is positive (>0)", metrics["avg_resolution_hours"] > 0)
check("Average SLA usage pct is positive (>0)", metrics["avg_sla_usage_pct"] > 0)

# ── Retrieve Escalation History ──────────────────────────────────────────────
print("\n5. Testing get_escalation_history...")
history = get_escalation_history()
check("History returns a list of records", isinstance(history, list))
check("History contains 2 escalation records", len(history) == 2)
check("History records have expected ticket IDs", any(h["ticket_id"] == "INC-04" for h in history) and any(h["ticket_id"] == "INC-05" for h in history))

# Print Summary
print("\n" + "=" * 50)
all_passed = all(r[1] for r in results)
if all_passed:
    print(f"  ALL {len(results)} SLA DASHBOARD METRICS TESTS PASSED ✅")
else:
    print("  SOME TESTS FAILED ❌")
print("=" * 50 + "\n")

db.close()
sys.exit(0 if all_passed else 1)
