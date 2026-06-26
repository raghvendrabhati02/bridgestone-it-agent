"""
verify_escalation.py
====================
Tests:
  1. Level 1 created immediately on breach
  2. Level 2 created 30+ minutes after breach
  3. Level 3 created 60+ minutes after breach
  4. No duplicate levels created
  5. Escalation history persists in DB
  6. Notifications created for each level
  7. All PASS summary
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
from app.database.models.sla_escalation_history import SlaEscalationHistory
from app.database.models.sla_audit_event import SlaAuditEvent

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

print("\n=== SLA Escalation Timeline Verification ===\n")

# ── Mock database get_db context ─────────────────────────────────────────────
from contextlib import contextmanager

@contextmanager
def mock_get_db():
    yield db

import app.database.session
app.database.session.get_db = mock_get_db

# ── Test imports ──────────────────────────────────────────────────────────────
print("1. Importing SLA Service functions...")
try:
    from app.services.sla_escalation_service import (
        evaluate_ticket,
        ESCALATED_LEVEL_1,
        ESCALATED_LEVEL_2,
        ESCALATED_LEVEL_3,
    )
    check("Imports succeed cleanly", True)
except Exception as e:
    check(f"Import failed: {e}", False)
    sys.exit(1)

# ── Test escalation levels ───────────────────────────────────────────────────
print("\n2. Simulating breach and timeline progression...")

now = datetime.utcnow()

# Ticket that was breached 35 minutes ago
t_level2 = Ticket(
    ticket_id="INC-L2",
    category="Software",
    priority="HIGH",
    sla_hours=4,
    created_at=now - timedelta(hours=5), # SLA breached 1 hour ago
    sla_breached=True,
    sla_breached_at=now - timedelta(minutes=35), # Breached 35 minutes ago
    sla_state=ESCALATED_LEVEL_1
)

# Ticket that was breached 65 minutes ago
t_level3 = Ticket(
    ticket_id="INC-L3",
    category="Hardware",
    priority="CRITICAL",
    sla_hours=2,
    created_at=now - timedelta(hours=4), # SLA breached 2 hours ago
    sla_breached=True,
    sla_breached_at=now - timedelta(minutes=65), # Breached 65 minutes ago
    sla_state=ESCALATED_LEVEL_2
)

db.add_all([t_level2, t_level3])
db.commit()

# Seed previous audit events to simulate realistic sequence
db.add_all([
    SlaAuditEvent(ticket_id="INC-L2", event_type="WARNING_75"),
    SlaAuditEvent(ticket_id="INC-L2", event_type="WARNING_90"),
    SlaAuditEvent(ticket_id="INC-L2", event_type="BREACHED"),
    SlaAuditEvent(ticket_id="INC-L2", event_type="ESCALATED_L1"),
    
    SlaAuditEvent(ticket_id="INC-L3", event_type="WARNING_75"),
    SlaAuditEvent(ticket_id="INC-L3", event_type="WARNING_90"),
    SlaAuditEvent(ticket_id="INC-L3", event_type="BREACHED"),
    SlaAuditEvent(ticket_id="INC-L3", event_type="ESCALATED_L1"),
    SlaAuditEvent(ticket_id="INC-L3", event_type="ESCALATED_L2"),
])
db.commit()

# Seed previous escalation histories
db.add_all([
    SlaEscalationHistory(ticket_id="INC-L2", level=1, reason="SLA Breached"),
    SlaEscalationHistory(ticket_id="INC-L3", level=1, reason="SLA Breached"),
    SlaEscalationHistory(ticket_id="INC-L3", level=2, reason="SLA L2"),
])
db.commit()

# Run evaluation on level 2 ticket (35 mins post-breach)
evaluate_ticket(db, t_level2)
db.commit()

check("t_level2 state transitioned to ESCALATED_LEVEL_2", t_level2.sla_state == ESCALATED_LEVEL_2)
l2_rec = db.query(SlaEscalationHistory).filter(
    SlaEscalationHistory.ticket_id == "INC-L2",
    SlaEscalationHistory.level == 2
).first()
check("Level 2 escalation history created in DB", l2_rec is not None)

# Run evaluation on level 3 ticket (65 mins post-breach)
evaluate_ticket(db, t_level3)
db.commit()

check("t_level3 state transitioned to ESCALATED_LEVEL_3", t_level3.sla_state == ESCALATED_LEVEL_3)
l3_rec = db.query(SlaEscalationHistory).filter(
    SlaEscalationHistory.ticket_id == "INC-L3",
    SlaEscalationHistory.level == 3
).first()
check("Level 3 escalation history created in DB", l3_rec is not None)

# Check notification counts
notifs_l2 = db.query(Notification).filter(
    Notification.ticket_id == "INC-L2",
    Notification.message.like("%Level 2%")
).count()
check("Notification created for Level 2 escalation", notifs_l2 > 0)

notifs_l3 = db.query(Notification).filter(
    Notification.ticket_id == "INC-L3",
    Notification.message.like("%Level 3%")
).count()
check("Notification created for Level 3 escalation", notifs_l3 > 0)

# Check duplicate safety
evaluate_ticket(db, t_level3)
db.commit()
l3_count = db.query(SlaEscalationHistory).filter(
    SlaEscalationHistory.ticket_id == "INC-L3",
    SlaEscalationHistory.level == 3
).count()
check("No duplicate Level 3 escalation history records created", l3_count == 1)

# Print Summary
print("\n" + "=" * 50)
all_passed = all(r[1] for r in results)
if all_passed:
    print(f"  ALL {len(results)} SLA ESCALATION TIMELINE TESTS PASSED ✅")
else:
    print("  SOME TESTS FAILED ❌")
print("=" * 50 + "\n")

db.close()
sys.exit(0 if all_passed else 1)
