"""
verify_sla_monitor.py
=====================
Tests:
  1. compute_sla_status() for HEALTHY ticket (10% used)
  2. compute_sla_status() for WARNING_75 ticket (76% used)
  3. compute_sla_status() for WARNING_90 ticket (91% used)
  4. compute_sla_status() for BREACHED ticket (105% used)
  5. evaluate_ticket() creates WARNING_75 notification (first time)
  6. evaluate_ticket() does NOT re-create WARNING_75 notification (dedup)
  7. evaluate_ticket() creates BREACHED escalation level 1
  8. Audit event created on state transition
  9. All PASS summary
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
from app.database.models.notification import Notification
from app.database.models.sla_audit_event import SlaAuditEvent
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

print("\n=== SLA Monitor Engine Verification ===\n")

# ── Mock database get_db context ─────────────────────────────────────────────
from contextlib import contextmanager

@contextmanager
def mock_get_db():
    yield db

import app.database.session
app.database.session.get_db = mock_get_db

# ── Test imports ──────────────────────────────────────────────────────────────
print("1. Importing SLA Escalation Service...")
try:
    from app.services.sla_escalation_service import (
        compute_sla_status,
        evaluate_ticket,
        HEALTHY,
        WARNING_75,
        WARNING_90,
        BREACHED,
        ESCALATED_LEVEL_1
    )
    check("Imports succeed cleanly", True)
except Exception as e:
    check(f"Import failed: {e}", False)
    sys.exit(1)

# ── Test SLA computation ──────────────────────────────────────────────────────
print("\n2. Testing SLA status calculations (compute_sla_status)...")

now = datetime.utcnow()

# HEALTHY: 10% used
t_healthy = Ticket(
    ticket_id="INC0001",
    category="Software",
    priority="LOW",
    sla_hours=20,
    created_at=now - timedelta(hours=2),
    sla_state=HEALTHY
)
info_healthy = compute_sla_status(t_healthy)
check("HEALTHY state correct", info_healthy["sla_state"] == HEALTHY)
check("HEALTHY usage percent is approx 10%", 9.9 <= info_healthy["sla_pct"] <= 10.1)

# WARNING_75: 76% used
t_w75 = Ticket(
    ticket_id="INC0002",
    category="Software",
    priority="MEDIUM",
    sla_hours=10,
    created_at=now - timedelta(hours=7.6),
    sla_state=HEALTHY
)
info_w75 = compute_sla_status(t_w75)
check("WARNING_75 state correct", info_w75["sla_state"] == WARNING_75)
check("WARNING_75 usage percent is approx 76%", 75.9 <= info_w75["sla_pct"] <= 76.1)

# WARNING_90: 91% used
t_w90 = Ticket(
    ticket_id="INC0003",
    category="Hardware",
    priority="HIGH",
    sla_hours=5,
    created_at=now - timedelta(hours=4.55),
    sla_state=HEALTHY
)
info_w90 = compute_sla_status(t_w90)
check("WARNING_90 state correct", info_w90["sla_state"] == WARNING_90)
check("WARNING_90 usage percent is approx 91%", 90.9 <= info_w90["sla_pct"] <= 91.1)

# BREACHED: 105% used
t_breached = Ticket(
    ticket_id="INC0004",
    category="Network",
    priority="CRITICAL",
    sla_hours=4,
    created_at=now - timedelta(hours=4.2),
    sla_state=HEALTHY
)
info_breached = compute_sla_status(t_breached)
check("BREACHED state correct", info_breached["sla_state"] == BREACHED)
check("BREACHED usage percent is approx 105%", 104.9 <= info_breached["sla_pct"] <= 105.1)

# ── Test ticket evaluation and side effects ────────────────────────────────────
print("\n3. Testing evaluate_ticket() side effects (notifications, deduplication)...")

# Insert tickets into DB
db.add_all([t_healthy, t_w75, t_w90, t_breached])
db.commit()

# Evaluate WARNING_75 ticket (first time)
evaluate_ticket(db, t_w75)
db.commit()

# Check that ticket model state is updated in DB
check("t_w75 sla_state updated in DB", t_w75.sla_state == WARNING_75)

# Check that warning notification was created in notifications table
notifs_w75 = db.query(Notification).filter(Notification.ticket_id == "INC0002").all()
check("Notification created for WARNING_75 ticket", len(notifs_w75) > 0)
check("Notification has expected recipient 'Manager'", any(n.recipient == "Manager" for n in notifs_w75))

# Check that warning event was recorded in audit events table
audit_event = db.query(SlaAuditEvent).filter(
    SlaAuditEvent.ticket_id == "INC0002",
    SlaAuditEvent.event_type == "WARNING_75"
).first()
check("Audit event recorded in DB", audit_event is not None)

# Evaluate WARNING_75 ticket a second time (deduplication check)
num_notifs_before = db.query(Notification).filter(Notification.ticket_id == "INC0002").count()
evaluate_ticket(db, t_w75)
db.commit()
num_notifs_after = db.query(Notification).filter(Notification.ticket_id == "INC0002").count()
check("Deduplication prevents duplicate notifications on re-evaluation", num_notifs_before == num_notifs_after)

# Evaluate BREACHED ticket
evaluate_ticket(db, t_breached)
db.commit()

check("t_breached is marked as breached", t_breached.sla_breached == True)
check("t_breached sla_breached_at is set", t_breached.sla_breached_at is not None)

# Check Level 1 escalation history created
l1_history = db.query(SlaEscalationHistory).filter(
    SlaEscalationHistory.ticket_id == "INC0004",
    SlaEscalationHistory.level == 1
).first()
check("Level 1 SLA Escalation history record created", l1_history is not None)

# Print Summary
print("\n" + "=" * 50)
all_passed = all(r[1] for r in results)
if all_passed:
    print(f"  ALL {len(results)} SLA MONITOR ENGINE TESTS PASSED ✅")
else:
    print("  SOME TESTS FAILED ❌")
print("=" * 50 + "\n")

db.close()
sys.exit(0 if all_passed else 1)
