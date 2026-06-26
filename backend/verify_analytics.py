"""
verify_analytics.py
===================
Unit verification for the Enterprise Analytics & Reporting Service Layer.
Seeds an in-memory SQLite database and checks dynamic query aggregates.
"""

import sys
import os
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

# Import Models
from app.database.models.ticket import Ticket
from app.database.models.session import SessionModel
from app.database.models.rbac_audit_log import RbacAuditLog
from app.database.models.security_event import SecurityEvent
from app.database.models.approval_history import ApprovalHistory
from app.database.models.agent_trace import AgentTrace
from app.database.models.user import User

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

print("\n=== Enterprise Analytics Service Layer Verification ===\n")

# ── 1. Seed Database with Test Data ──────────────────────────────────────────
print("Seeding test database...")

now = datetime.utcnow()

# Seed Users
u1 = User(id=1, username="employee1", email="e1@company.com", hashed_password="pw", role="EMPLOYEE", is_active=True)
u2 = User(id=2, username="manager1", email="m1@company.com", hashed_password="pw", role="MANAGER", is_active=True)
u3 = User(id=3, username="admin1", email="a1@company.com", hashed_password="pw", role="ADMIN", is_active=True)
db.add_all([u1, u2, u3])

# Seed Sessions
s1 = SessionModel(session_id="sess-active-1", status="ACTIVE", active_ticket="INC0001", approval_required=False)
s2 = SessionModel(session_id="sess-active-2", status="ACTIVE", active_ticket="", approval_required=True)
s3 = SessionModel(session_id="sess-resolved-1", status="RESOLVED", active_ticket="", approval_required=False) # Auto-resolved
s4 = SessionModel(session_id="sess-resolved-2", status="RESOLVED", active_ticket="INC0002", approval_required=False)
db.add_all([s1, s2, s3, s4])

# Seed Tickets
# SLA State options: HEALTHY, WARNING_75, WARNING_90, BREACHED, ESCALATED_LEVEL_1, ESCALATED_LEVEL_2, ESCALATED_LEVEL_3
t1 = Ticket(
    ticket_id="INC0001",
    category="VPN connection issue",
    issue_description="VPN keeps disconnecting",
    description="VPN keeps disconnecting",
    assigned_team="Network Team",
    status="OPEN",
    priority="CRITICAL",
    sla_hours=4,
    sla_state="HEALTHY",
    created_at=now - timedelta(hours=1),
    created_by="employee1"
)
t2 = Ticket(
    ticket_id="INC0002",
    category="Password reset",
    issue_description="Forgot windows password",
    description="Forgot windows password",
    assigned_team="Desktop Support Team",
    status="RESOLVED",
    priority="LOW",
    sla_hours=24,
    sla_state="HEALTHY",
    created_at=now - timedelta(hours=3),
    created_by="employee1"
)
t3 = Ticket(
    ticket_id="INC0003",
    category="Software install request",
    issue_description="Need MS Visio license",
    description="Need MS Visio license",
    assigned_team="SAP Support Team", # Let's assign software to SAP Support Team
    status="IN_PROGRESS",
    priority="MEDIUM",
    sla_hours=12,
    sla_state="BREACHED",
    sla_breached=True,
    created_at=now - timedelta(hours=15),
    created_by="employee1"
)
db.add_all([t1, t2, t3])

# Seed RbacAuditLog (for resolution times and response times calculation)
# Resolution log for INC0002 (resolved after 2.5 hours)
al_res = RbacAuditLog(
    ticket_id="INC0002",
    action="update_ticket_lifecycle",
    old_state="OPEN",
    new_state="RESOLVED",
    user="admin1",
    role="ADMIN",
    timestamp=now - timedelta(hours=0.5) # Created at -3h, resolved at -0.5h => 2.5 hours resolution time
)
# First response log for INC0003 (assigned after 0.5 hours)
al_resp = RbacAuditLog(
    ticket_id="INC0003",
    action="update_ticket_lifecycle",
    old_state="OPEN",
    new_state="ASSIGNED",
    user="admin1",
    role="ADMIN",
    timestamp=now - timedelta(hours=14.5) # Created at -15h, responded at -14.5h => 0.5 hours response time
)
db.add_all([al_res, al_resp])

# Seed SecurityEvents
se1 = SecurityEvent(event_type="LOGIN", username="employee1", details="Successful login", created_at=now - timedelta(hours=2))
se2 = SecurityEvent(event_type="LOGIN", username="admin1", details="Successful login", created_at=now - timedelta(hours=1))
se3 = SecurityEvent(event_type="PERMISSION_DENIED", username="employee1", details="Access denied to admin console", created_at=now)
db.add_all([se1, se2, se3])

# Seed ApprovalHistory
ah1 = ApprovalHistory(session_id="sess-active-2", recommended_action="Reset user AD password", approval_status="PENDING")
ah2 = ApprovalHistory(session_id="sess-resolved-2", recommended_action="Approve Visio license", approval_status="APPROVED")
db.add_all([ah1, ah2])

# Seed AgentTraces
at1 = AgentTrace(
    session_id="sess-active-1",
    agent_name="Root Cause Agent",
    input_data="{}",
    output_data=json.dumps({"possible_causes": ["Expired security certificates", "Network switch packet routing loop"]}),
    created_at=now
)
at2 = AgentTrace(
    session_id="sess-active-2",
    agent_name="Knowledge Agent",
    input_data="{}",
    output_data="{}",
    created_at=now
)
db.add_all([at1, at2])

db.commit()
print("Database seeded successfully.\n")

# ── 2. Run Service Calculations ──────────────────────────────────────────────
from app.services import analytics_service

# 1. Overview Metrics
print("Verifying Overview Metrics...")
overview = analytics_service.get_overview_metrics(db)
check("total_tickets is 3", overview["total_tickets"] == 3)
check("open_tickets (OPEN/IN_PROGRESS) is 2", overview["open_tickets"] == 2)
# Compliant open tickets: t1 (HEALTHY) is compliant, t3 (BREACHED) is breached.
# Compliance pct: (1 / 2) * 100 = 50.0%
check("compliance_pct is 50.0", overview["compliance_pct"] == 50.0)
# Avg resolution hours: INC0002 took 2.5 hours.
check("avg_resolution_hours is 2.5", overview["avg_resolution_hours"] == 2.5)
check("active_users count is 2", overview["active_users"] == 2)
check("security_events count is 3", overview["security_events"] == 3)

# 2. Ticket Metrics
print("\nVerifying Ticket Metrics...")
tickets_info = analytics_service.get_ticket_metrics(db)
check("total_tickets is 3", tickets_info["total_tickets"] == 3)
check("status_distribution OPEN is 1", tickets_info["status_distribution"]["OPEN"] == 1)
check("status_distribution RESOLVED is 1", tickets_info["status_distribution"]["RESOLVED"] == 1)
check("priority_distribution CRITICAL is 1", tickets_info["priority_distribution"]["CRITICAL"] == 1)

# 3. Category Metrics
print("\nVerifying Category Metrics...")
cats = analytics_service.get_category_metrics(db)
# VPN Connection issue -> VPN, Password reset -> Password, Software install request -> Software
cat_names = [c["category"] for c in cats]
check("VPN category is present", "VPN" in cat_names)
check("Password category is present", "Password" in cat_names)
check("Software category is present", "Software" in cat_names)

# 4. SLA Metrics
print("\nVerifying SLA Metrics...")
sla = analytics_service.get_sla_metrics(db)
check("SLA compliance matches overview", sla["compliance_pct"] == 50.0)
check("SLA healthy tickets count is 1", sla["healthy"] == 1)
check("SLA breached tickets count is 1", sla["breached"] == 1)
# Response time: t3 responded in 0.5 hours.
check("avg_first_response_hours is 0.5", sla["avg_first_response_hours"] == 0.5)

# 5. Team Performance Metrics
print("\nVerifying Team Performance Metrics...")
teams = analytics_service.get_team_metrics(db)
# Network Team has 1 open, 0 resolved, 0 breaches, workload = 50.0%
# Desktop Support Team has 0 open, 1 resolved, 0 breaches, workload = 0.0%
# SAP Support Team has 1 open, 0 resolved, 1 breach, workload = 50.0%
net_team = next(t for t in teams if t["team"] == "Network Team")
desktop_team = next(t for t in teams if t["team"] == "Desktop Support Team")
sap_team = next(t for t in teams if t["team"] == "SAP Support Team")

check("Network Team has 1 open ticket", net_team["open"] == 1)
check("Network Team workload_pct is 50.0", net_team["workload_pct"] == 50.0)
check("Desktop Support Team has 1 resolved ticket", desktop_team["resolved"] == 1)
check("SAP Support Team has 1 breach", sap_team["breaches"] == 1)

# 6. Agent Analytics
print("\nVerifying Agent Performance Analytics...")
agent = analytics_service.get_agent_analytics(db)
check("total_conversations is 4", agent["total_conversations"] == 4)
check("auto_resolutions is 1", agent["auto_resolutions"] == 1)
# human intervention sessions: sess-active-1 (has active ticket), sess-active-2 (approval req), sess-resolved-2 (active ticket).
# Total intervention = 3. Rate = (3 / 4) * 100 = 75.0%
check("human_intervention_rate_pct is 75.0", agent["human_intervention_rate_pct"] == 75.0)
check("knowledge_searches is 1", agent["knowledge_searches"] == 1)
check("root_cause_analyses is 1", agent["root_cause_analyses"] == 1)

# 7. User Session Metrics
print("\nVerifying User Session Metrics...")
users = analytics_service.get_user_metrics(db)
check("employee count is 1", users["employees"] == 1)
check("manager count is 1", users["managers"] == 1)
check("admin count is 1", users["admins"] == 1)
check("active_sessions count is 2", users["active_sessions"] == 2)
# Logged in last 24h: distinct usernames with login events (employee1, admin1) => 2
check("logged_in_users is 2", users["logged_in_users"] == 2)
check("avg_daily_users is 2.0", users["avg_daily_users"] == 2.0)

# 8. Security Compliance Metrics
print("\nVerifying Security Compliance Metrics...")
security = analytics_service.get_security_metrics(db)
check("rbac_violations count is 1", security["rbac_violations"] == 1)
check("approval_requests count is 2", security["approval_requests"] == 2)
check("security_events count is 3", security["security_events"] == 3)

# 9. Root Cause Diagnostics Metrics
print("\nVerifying Root Cause & Diagnosis Metrics...")
rc = analytics_service.get_root_cause_metrics(db)
check("top repeated root causes from AgentTrace are parsed", "Expired security certificates" in rc["top_repeated_root_causes"])
check("most affected support team is Network Team", rc["most_affected_support_team"] == "Network Team")
check("recommendations are returned", len(rc["recommendations"]) > 0)

# Print Summary
print("\n" + "=" * 50)
all_passed = all(r[1] for r in results)
if all_passed:
    print(f"  ALL {len(results)} SERVICE LAYER ANALYTICS TESTS PASSED ✅")
else:
    print("  SOME TESTS FAILED ❌")
print("=" * 50 + "\n")

db.close()
sys.exit(0 if all_passed else 1)
