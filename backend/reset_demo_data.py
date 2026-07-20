import os
import sys
from datetime import datetime, timedelta

# Add app directory to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "app")))

from app.database.connection import SessionLocal, engine
from app.database.base import Base

# Import all models to clear them and seed them
from app.database.models.user import User
from app.database.models.session import SessionModel
from app.database.models.conversation import Conversation
from app.database.models.audit_log import AuditLog
from app.database.models.action_history import ActionHistory
from app.database.models.approval_history import ApprovalHistory
from app.database.models.agent_trace import AgentTrace
from app.database.models.ticket import Ticket
from app.database.models.notification import Notification
from app.database.models.security_event import SecurityEvent
from app.database.models.rbac_audit_log import RbacAuditLog
from app.database.models.scheduled_job import ScheduledJob, JobExecutionHistory
from app.database.models.sla_escalation_history import SlaEscalationHistory
from app.database.models.sla_audit_event import SlaAuditEvent
from app.database.models.service_catalog import ServiceCatalogItem
from app.database.models.service_request import ServiceRequest
from app.database.models.device import Device
from app.core.security import hash_password

def clear_data(db):
    print("Purging existing development data from PostgreSQL database...")
    try:
        db.query(JobExecutionHistory).delete()
        db.query(ScheduledJob).delete()
        db.query(SlaEscalationHistory).delete()
        db.query(SlaAuditEvent).delete()
        db.query(Notification).delete()
        db.query(SecurityEvent).delete()
        db.query(RbacAuditLog).delete()
        db.query(AuditLog).delete()
        db.query(ApprovalHistory).delete()
        db.query(ActionHistory).delete()
        db.query(AgentTrace).delete()
        db.query(Ticket).delete()
        db.query(ServiceRequest).delete()
        db.query(ServiceCatalogItem).delete()
        db.query(Conversation).delete()
        db.query(SessionModel).delete()
        db.query(Device).delete()
        db.query(User).delete()
        db.commit()
        print("[OK] Purge successful. Database schema preserved.")
    except Exception as e:
        db.rollback()
        print(f"[ERROR] Failed to purge database tables: {e}")
        sys.exit(1)

def seed_users(db):
    print("Seeding standard demo users...")
    users = [
        {"username": "employee", "email": "employee@bridgestone.com", "role": "EMPLOYEE", "pw": "employeepassword"},
        {"username": "manager", "email": "manager@bridgestone.com", "role": "MANAGER", "pw": "managerpassword"},
        {"username": "admin", "email": "admin@bridgestone.com", "role": "ADMIN", "pw": "adminpassword"}
    ]
    for u in users:
        hashed = hash_password(u["pw"])
        user = User(
            username=u["username"],
            email=u["email"],
            role=u["role"],
            hashed_password=hashed,
            is_active=True
        )
        db.add(user)
    db.commit()
    print("[OK] Seeded 3 system users.")

def seed_tickets_and_audit(db):
    print("Seeding realistic IT Tickets and lifecycle RBAC audit logs...")
    
    # 12 Seed tickets
    # INC000009 is breached / escalated
    # INC000002, INC000006, INC000008, INC000011 are resolved/closed
    # Active tickets: 001, 003, 004, 005, 007, 009, 010, 012 (Total: 8, Breached: 009, compliance = 87.5%)
    now = datetime.utcnow()
    
    tickets_data = [
        {
            "ticket_id": "INC000001",
            "category": "VPN",
            "description": "Employee VPN gateway timeout on login. Error 809.",
            "assigned_team": "Network",
            "priority": "CRITICAL",
            "sla_hours": 2,
            "status": "IN_PROGRESS",
            "servicenow_id": "INC1002001",
            "created_by": "employee",
            "hours_ago": 1.5,
            "sla_state": "WARNING_75",
            "sla_breached": False,
            "sla_breached_at": None
        },
        {
            "ticket_id": "INC000002",
            "category": "Password",
            "description": "AD User account locked after multiple login attempts.",
            "assigned_team": "Helpdesk",
            "priority": "LOW",
            "sla_hours": 24,
            "status": "RESOLVED",
            "servicenow_id": None,
            "created_by": "employee",
            "hours_ago": 5.0,
            "resolved_hours_ago": 4.5,
            "sla_state": "HEALTHY",
            "sla_breached": False,
            "sla_breached_at": None
        },
        {
            "ticket_id": "INC000003",
            "category": "Software",
            "description": "Requesting install of MS Visio license.",
            "assigned_team": "Sysadmin",
            "priority": "MEDIUM",
            "sla_hours": 8,
            "status": "WAITING_FOR_USER",
            "servicenow_id": "REQ3004001",
            "created_by": "employee",
            "hours_ago": 7.3,
            "sla_state": "WARNING_90",
            "sla_breached": False,
            "sla_breached_at": None
        },
        {
            "ticket_id": "INC000004",
            "category": "Outlook",
            "description": "Outlook client crashes repeatedly on launch.",
            "assigned_team": "Helpdesk",
            "priority": "MEDIUM",
            "sla_hours": 8,
            "status": "ASSIGNED",
            "servicenow_id": None,
            "created_by": "employee",
            "hours_ago": 4.0,
            "sla_state": "HEALTHY",
            "sla_breached": False,
            "sla_breached_at": None
        },
        {
            "ticket_id": "INC000005",
            "category": "SAP",
            "description": "SAP ERP Production environment throwing gateway timeouts on order forms.",
            "assigned_team": "Sysadmin",
            "priority": "CRITICAL",
            "sla_hours": 2,
            "status": "OPEN",
            "servicenow_id": "INC2003001",
            "created_by": "employee",
            "hours_ago": 0.75,
            "sla_state": "HEALTHY",
            "sla_breached": False,
            "sla_breached_at": None
        },
        {
            "ticket_id": "INC000006",
            "category": "Network",
            "description": "Bridgestone Warehouse Switch #3 offline. Several machines lost connection.",
            "assigned_team": "Network",
            "priority": "HIGH",
            "sla_hours": 4,
            "status": "CLOSED",
            "servicenow_id": "INC1002002",
            "created_by": "employee",
            "hours_ago": 12.0,
            "resolved_hours_ago": 10.0,
            "sla_state": "HEALTHY",
            "sla_breached": False,
            "sla_breached_at": None
        },
        {
            "ticket_id": "INC000007",
            "category": "Hardware",
            "description": "Laptop monitor flicks black intermittently when opening hinges.",
            "assigned_team": "Hardware",
            "priority": "LOW",
            "sla_hours": 24,
            "status": "OPEN",
            "servicenow_id": None,
            "created_by": "employee",
            "hours_ago": 3.0,
            "sla_state": "HEALTHY",
            "sla_breached": False,
            "sla_breached_at": None
        },
        {
            "ticket_id": "INC000008",
            "category": "Outlook",
            "description": "Need access permissions to public folder hr-info.",
            "assigned_team": "Security",
            "priority": "LOW",
            "sla_hours": 24,
            "status": "RESOLVED",
            "servicenow_id": "REQ3004002",
            "created_by": "employee",
            "hours_ago": 10.0,
            "resolved_hours_ago": 8.0,
            "sla_state": "HEALTHY",
            "sla_breached": False,
            "sla_breached_at": None
        },
        {
            "ticket_id": "INC000009",
            "category": "General",
            "description": "Security Alert: Unauthorized USB device connected on Workstation-44.",
            "assigned_team": "Security",
            "priority": "CRITICAL",
            "sla_hours": 2,
            "status": "IN_PROGRESS",
            "servicenow_id": None,
            "created_by": "admin",
            "hours_ago": 3.5,
            "sla_state": "ESCALATED_LEVEL_3",
            "sla_breached": True,
            "sla_breached_at": now - timedelta(hours=1.5)
        },
        {
            "ticket_id": "INC000010",
            "category": "SAP",
            "description": "SAP GUI client throws licensing error upon connection attempts.",
            "assigned_team": "Sysadmin",
            "priority": "MEDIUM",
            "sla_hours": 8,
            "status": "OPEN",
            "servicenow_id": "INC2003002",
            "created_by": "employee",
            "hours_ago": 1.5,
            "sla_state": "HEALTHY",
            "sla_breached": False,
            "sla_breached_at": None
        },
        {
            "ticket_id": "INC000011",
            "category": "VPN",
            "description": "Requesting Cisco AnyConnect client download link and setup documentation.",
            "assigned_team": "Helpdesk",
            "priority": "LOW",
            "sla_hours": 24,
            "status": "CLOSED",
            "servicenow_id": None,
            "created_by": "employee",
            "hours_ago": 6.0,
            "resolved_hours_ago": 5.0,
            "sla_state": "HEALTHY",
            "sla_breached": False,
            "sla_breached_at": None
        },
        {
            "ticket_id": "INC000012",
            "category": "Hardware",
            "description": "Printer on floor 2 is out of black toner cartridge.",
            "assigned_team": "Hardware",
            "priority": "LOW",
            "sla_hours": 24,
            "status": "OPEN",
            "servicenow_id": None,
            "created_by": "employee",
            "hours_ago": 1.0,
            "sla_state": "HEALTHY",
            "sla_breached": False,
            "sla_breached_at": None
        }
    ]

    for t in tickets_data:
        c_time = now - timedelta(hours=t["hours_ago"])
        
        from app.services.itsm_classifier import classify_request
        classification = classify_request(t["category"], t["description"])
        app_status = classification.approval_status
        if t["status"] in ("ASSIGNED", "IN_PROGRESS", "RESOLVED", "CLOSED") and classification.requires_approval:
            app_status = "APPROVED"

        ticket = Ticket(
            ticket_id=t["ticket_id"],
            category=t["category"],
            description=t["description"],
            issue_description=t["description"],
            assigned_team=t["assigned_team"],
            priority=t["priority"],
            sla_hours=t["sla_hours"],
            status=t["status"],
            servicenow_id=t["servicenow_id"],
            created_by=t["created_by"],
            created_at=c_time,
            sla_state=t["sla_state"],
            sla_breached=t["sla_breached"],
            sla_breached_at=t["sla_breached_at"],
            request_type=classification.request_type,
            approval_status=app_status,
            manager=classification.manager,
            assignment_group=t["assigned_team"]
        )
        db.add(ticket)
        
        # 1. Seed Ticket Creation Audit Log
        db.add(RbacAuditLog(
            timestamp=c_time,
            user=t["created_by"],
            role="EMPLOYEE" if t["created_by"] == "employee" else "ADMIN",
            action="create_ticket",
            ticket_id=t["ticket_id"],
            new_state="OPEN",
            details="Ticket created automatically by portal session request."
        ))

        # 2. Seed First Response Audit Log (exactly 12 minutes after creation -> 0.2 hours)
        resp_time = c_time + timedelta(minutes=12)
        db.add(RbacAuditLog(
            timestamp=resp_time,
            user="manager",
            role="MANAGER",
            action="update_ticket_lifecycle",
            ticket_id=t["ticket_id"],
            old_state="OPEN",
            new_state="ASSIGNED" if t["status"] == "ASSIGNED" else "IN_PROGRESS",
            details="Ticket assigned to support team and technician allocated."
        ))

        # 3. Seed Resolution Audit Log for Resolved/Closed tickets
        if "resolved_hours_ago" in t:
            r_time = now - timedelta(hours=t["resolved_hours_ago"])
            db.add(RbacAuditLog(
                timestamp=r_time,
                user="manager",
                role="MANAGER",
                action="update_ticket_lifecycle",
                ticket_id=t["ticket_id"],
                old_state="IN_PROGRESS",
                new_state=t["status"],
                details=f"Ticket set to {t['status']} after completing diagnosis checks."
            ))

    db.commit()
    print("[OK] Seeded 12 operational tickets and 20 RBAC lifecycle transition events.")

def seed_escalations(db):
    print("Seeding persistent SLA escalation events...")
    # Seed warning and escalation audit/history matching INC000009 (Unauthorized USB, CRITICAL, target 2h, created 3.5h ago)
    # Target breach time = 1.5h ago
    ticket_id = "INC000009"
    now = datetime.utcnow()
    breach_time = now - timedelta(hours=1.5)

    # 1. SLA Audit Events (warnings and breaches)
    events = [
        {"event_type": "WARNING_75", "offset_min": -30}, # 30 min before breach (1.5h in)
        {"event_type": "WARNING_90", "offset_min": -12}, # 12 min before breach
        {"event_type": "BREACHED", "offset_min": 0},
        {"event_type": "ESCALATED_L1", "offset_min": 0},
        {"event_type": "ESCALATED_L2", "offset_min": 30},
        {"event_type": "ESCALATED_L3", "offset_min": 60}
    ]
    for e in events:
        evt_time = breach_time + timedelta(minutes=e["offset_min"])
        db.add(SlaAuditEvent(
            ticket_id=ticket_id,
            event_type=e["event_type"],
            created_at=evt_time
        ))

    # 2. SLA Escalation History
    escalations = [
        {"level": 1, "offset_min": 0, "reason": "SLA targets (2.0 hours) breached for critical priority issue."},
        {"level": 2, "offset_min": 30, "reason": "No response on critical ticket 30 minutes post-breach."},
        {"level": 3, "offset_min": 60, "reason": "Severe breach: ticket unassigned 60 minutes post-breach. Notification dispatched to Director of SecOps."}
    ]
    for esc in escalations:
        esc_time = breach_time + timedelta(minutes=esc["offset_min"])
        db.add(SlaEscalationHistory(
            ticket_id=ticket_id,
            level=esc["level"],
            reason=esc["reason"],
            triggered_by="sla_monitor_job",
            notification_sent=True,
            audit_logged=True,
            created_at=esc_time
        ))

    db.commit()
    print("[OK] Seeded SLA escalation histories for INC000009.")

def seed_notifications(db):
    print("Seeding notifications...")
    notifications = [
        {
            "notification_id": "NTF000001",
            "ticket_id": "INC000001",
            "recipient": "network-support@bridgestone.com",
            "message": "Critical ticket INC000001 has been assigned to the Network team.",
            "status": "SENT"
        },
        {
            "notification_id": "NTF000002",
            "ticket_id": "INC000009",
            "recipient": "security-leads@bridgestone.com",
            "message": "SLA WARNING: INC000009 has consumed 90% of SLA time.",
            "status": "SENT"
        },
        {
            "notification_id": "NTF000003",
            "ticket_id": "INC000009",
            "recipient": "secops-director@bridgestone.com",
            "message": "ALERT: SLA Breach level 3 escalation triggered for INC000009.",
            "status": "SENT"
        },
        {
            "notification_id": "NTF000004",
            "ticket_id": "INC000003",
            "recipient": "employee@bridgestone.com",
            "message": "Update request: Ticket INC000003 is awaiting input from you.",
            "status": "SENT"
        }
    ]
    for n in notifications:
        db.add(Notification(
            notification_id=n["notification_id"],
            ticket_id=n["ticket_id"],
            recipient=n["recipient"],
            message=n["message"],
            status=n["status"],
            created_at=datetime.utcnow() - timedelta(minutes=10)
        ))
    db.commit()
    print("[OK] Seeded 4 notifications.")

def seed_approvals(db):
    print("Seeding approval request histories...")
    # Approvals list
    approvals = [
        {"session_id": "sess-visio-01", "recommended_action": "install_software Visio", "approval_status": "PENDING"},
        {"session_id": "sess-adunlock-02", "recommended_action": "unlock_ad_user employee", "approval_status": "APPROVED"},
        {"session_id": "sess-reset-03", "recommended_action": "reset_user_password employee", "approval_status": "APPROVED"},
        {"session_id": "sess-usblock-04", "recommended_action": "block_usb_port Workstation-44", "approval_status": "APPROVED"}
    ]
    for idx, a in enumerate(approvals):
        db.add(ApprovalHistory(
            session_id=a["session_id"],
            recommended_action=a["recommended_action"],
            approval_status=a["approval_status"],
            created_at=datetime.utcnow() - timedelta(hours=2)
        ))
        
        # Seed corresponding action execution logs
        if a["approval_status"] == "APPROVED":
            db.add(ActionHistory(
                request_id=f"REQ0001{idx:02d}",
                action_type=a["recommended_action"].split()[0],
                status="SUCCESS",
                servicenow_id=f"SR0000{random_id()}",
                created_at=datetime.utcnow() - timedelta(hours=1.8)
            ))
            
    db.commit()
    print("[OK] Seeded approvals history and execution logs.")

def random_id():
    import random
    return random.randint(1000, 9999)

def seed_audits_and_security(db):
    print("Seeding audit decisions and security alerts...")
    # General audit logs
    audits = [
        {"sess": "sess-gen-01", "msg": "How can I download the Cisco AnyConnect client?", "cat": "VPN", "dec": "ALLOW", "stat": "APPROVED", "act": "provide_download_link", "t_id": "INC000011"},
        {"sess": "sess-gen-02", "msg": "My screen is flickering when I hinge open the laptop", "cat": "Hardware", "dec": "ALLOW", "stat": "APPROVED", "act": "create_ticket", "t_id": "INC000007"},
        {"sess": "sess-gen-03", "msg": "Read HR public folder", "cat": "General", "dec": "DENY", "stat": "ACCESS_DENIED", "act": "block_request", "t_id": None}
    ]
    for au in audits:
        db.add(AuditLog(
            session_id=au["sess"],
            user_message=au["msg"],
            category=au["cat"],
            decision=au["dec"],
            approval_status=au["stat"],
            recommended_action=au["act"],
            ticket_id=au["t_id"],
            created_at=datetime.utcnow() - timedelta(hours=3)
        ))

    # Security events
    events = [
        {"type": "LOGIN", "username": "admin", "details": "Successful admin authentication from portal browser client."},
        {"type": "LOGIN", "username": "manager", "details": "Successful manager authentication from portal browser client."},
        {"type": "FAILED_LOGIN", "username": "intruder", "details": "Alert: Failed login attempts threshold exceeded from IP 192.168.10.45."},
        {"type": "PERMISSION_DENIED", "username": "employee", "details": "Access Blocked: Employee attempted to access endpoint /api/analytics/security."}
    ]
    for ev in events:
        db.add(SecurityEvent(
            event_type=ev["type"],
            username=ev["username"],
            details=ev["details"],
            created_at=datetime.utcnow() - timedelta(hours=1.2)
        ))
    db.commit()
    print("[OK] Seeded audit decisions and security events.")

def seed_scheduler_history(db):
    print("Seeding scheduled background jobs states...")
    # Seed Scheduled Jobs
    jobs = [
        {"name": "sla_monitor", "type": "interval", "sec": 1800, "cron": None},
        {"name": "notification_job", "type": "interval", "sec": 300, "cron": None},
        {"name": "cleanup_job", "type": "cron", "sec": None, "cron": "0 2 * * *"}
    ]
    for j in jobs:
        db.add(ScheduledJob(
            job_name=j["name"],
            job_type=j["type"],
            interval_seconds=j["sec"],
            cron_expression=j["cron"],
            is_enabled=True,
            last_run_time=datetime.utcnow() - timedelta(minutes=10),
            next_run_time=datetime.utcnow() + timedelta(minutes=20)
        ))

    # Seed execution history
    executions = [
        {"name": "sla_monitor", "status": "SUCCESS", "offset": 10},
        {"name": "notification_job", "status": "SUCCESS", "offset": 5},
        {"name": "cleanup_job", "status": "SUCCESS", "offset": 1440}
    ]
    for e in executions:
        start_time = datetime.utcnow() - timedelta(minutes=e["offset"])
        db.add(JobExecutionHistory(
            job_name=e["name"],
            status=e["status"],
            started_at=start_time,
            completed_at=start_time + timedelta(seconds=2)
        ))
    db.commit()
    print("[OK] Seeded APScheduler logs.")

def seed_service_catalog(db):
    print("Seeding service catalog items...")
    catalog_items = [
        {
            "service_id": "SRV001",
            "name": "Software Installation",
            "category": "Software",
            "description": "Request installation or license activation of standard desktop software (e.g., Adobe Acrobat, MS Visio, Zoom Pro).",
            "business_owner": "Priya Verma",
            "fulfillment_team": "Helpdesk",
            "approval_required": True,
            "sla_hours": 24,
            "estimated_completion": "1 Business Day",
            "icon": "AppWindow"
        },
        {
            "service_id": "SRV002",
            "name": "VPN Access Request",
            "category": "Network",
            "description": "Request corporate VPN client (Cisco AnyConnect) credentials, connection profile, and multi-factor authentication setup.",
            "business_owner": "Amit Patel",
            "fulfillment_team": "Network Team",
            "approval_required": True,
            "sla_hours": 12,
            "estimated_completion": "12 Hours",
            "icon": "ShieldAlert"
        },
        {
            "service_id": "SRV003",
            "name": "Shared Folder Access",
            "category": "Identity",
            "description": "Request NTFS read/write permissions for specific department or project shared folders on local file servers.",
            "business_owner": "Rahul Sharma",
            "fulfillment_team": "Sysadmin",
            "approval_required": True,
            "sla_hours": 24,
            "estimated_completion": "1 Business Day",
            "icon": "FolderOpen"
        },
        {
            "service_id": "SRV004",
            "name": "SAP Account Access",
            "category": "ERP",
            "description": "Request new login credentials or modify transaction roles/permissions in the SAP ERP Production, Sandbox, or Development instances.",
            "business_owner": "Priya Verma",
            "fulfillment_team": "ERP Basis Support",
            "approval_required": True,
            "sla_hours": 48,
            "estimated_completion": "2 Business Days",
            "icon": "Database"
        },
        {
            "service_id": "SRV005",
            "name": "Active Directory Account Unlock",
            "category": "Identity",
            "description": "Self-service or assisted domain account unlock and credential synchronization check.",
            "business_owner": "Rahul Sharma",
            "fulfillment_team": "Helpdesk",
            "approval_required": False,
            "sla_hours": 4,
            "estimated_completion": "Immediate (Auto)",
            "icon": "UserCheck"
        },
        {
            "service_id": "SRV006",
            "name": "Email Distribution List",
            "category": "Collaboration",
            "description": "Request creation of a new corporate email distribution group, Microsoft 365 group, or modification of member lists.",
            "business_owner": "Neha Singh",
            "fulfillment_team": "Helpdesk",
            "approval_required": False,
            "sla_hours": 8,
            "estimated_completion": "4 Hours",
            "icon": "Mail"
        },
        {
            "service_id": "SRV007",
            "name": "Printer Access Setup",
            "category": "Hardware",
            "description": "Request remote driver installation and queue configuration for office network printers and high-capacity copiers.",
            "business_owner": "Rahul Sharma",
            "fulfillment_team": "Helpdesk",
            "approval_required": False,
            "sla_hours": 12,
            "estimated_completion": "1 Business Day",
            "icon": "Printer"
        },
        {
            "service_id": "SRV008",
            "name": "New Laptop Provisioning",
            "category": "Hardware",
            "description": "Request provisioning of a standard corporate laptop (Lenovo ThinkPad or Apple MacBook Pro) with standard software loadout.",
            "business_owner": "Rahul Sharma",
            "fulfillment_team": "Hardware Support",
            "approval_required": True,
            "sla_hours": 72,
            "estimated_completion": "3 Business Days",
            "icon": "Laptop"
        },
        {
            "service_id": "SRV009",
            "name": "External Monitor Request",
            "category": "Hardware",
            "description": "Request single 34-inch ultra-wide or dual 24-inch flat panel desktop monitors, display cables, and mounting stands.",
            "business_owner": "Rahul Sharma",
            "fulfillment_team": "Hardware Support",
            "approval_required": False,
            "sla_hours": 48,
            "estimated_completion": "2 Business Days",
            "icon": "Monitor"
        },
        {
            "service_id": "SRV010",
            "name": "Corporate Mobile Device",
            "category": "Hardware",
            "description": "Request corporate cell phone hardware (Apple iPhone or Samsung Galaxy) and corporate voice/data cellular plan.",
            "business_owner": "Rahul Sharma",
            "fulfillment_team": "Hardware Support",
            "approval_required": True,
            "sla_hours": 72,
            "estimated_completion": "3 Business Days",
            "icon": "Smartphone"
        },
        {
            "service_id": "SRV011",
            "name": "New Employee Onboarding",
            "category": "HR IT",
            "description": "Provision all standard IT assets for a new hire, including email inbox, Active Directory account, hardware request, and access badges.",
            "business_owner": "Neha Singh",
            "fulfillment_team": "Helpdesk",
            "approval_required": True,
            "sla_hours": 120,
            "estimated_completion": "5 Business Days",
            "icon": "UserPlus"
        },
        {
            "service_id": "SRV012",
            "name": "Database Account Access",
            "category": "ERP",
            "description": "Request login credentials and schema read/write permissions on Oracle, PostgreSQL, or MS SQL Server databases.",
            "business_owner": "Priya Verma",
            "fulfillment_team": "Database Admins",
            "approval_required": True,
            "sla_hours": 24,
            "estimated_completion": "1 Business Day",
            "icon": "HardDrive"
        },
        {
            "service_id": "SRV013",
            "name": "Cloud Sandbox Account",
            "category": "Software",
            "description": "Request a temporary sandbox account in AWS, Microsoft Azure, or GCP for development and testing purposes.",
            "business_owner": "Rahul Sharma",
            "fulfillment_team": "Cloud Operations",
            "approval_required": True,
            "sla_hours": 24,
            "estimated_completion": "1 Business Day",
            "icon": "Cloud"
        },
        {
            "service_id": "SRV014",
            "name": "Physical Access Badge",
            "category": "Security",
            "description": "Request physical smartcard badge issuance or permissions update for entry gates, server rooms, or secured parking lots.",
            "business_owner": "Amit Patel",
            "fulfillment_team": "Security & Facilities",
            "approval_required": True,
            "sla_hours": 24,
            "estimated_completion": "1 Business Day",
            "icon": "Key"
        },
        {
            "service_id": "SRV015",
            "name": "Ergonomic Desk Accessories",
            "category": "Hardware",
            "description": "Request ergonomic mouse, keyboard, desk riser, or chair evaluations to align with office wellness guidelines.",
            "business_owner": "Amit Patel",
            "fulfillment_team": "Security & Facilities",
            "approval_required": False,
            "sla_hours": 48,
            "estimated_completion": "2 Business Days",
            "icon": "Accessibility"
        }
    ]
    for item in catalog_items:
        db.add(ServiceCatalogItem(**item))
    db.commit()
    print("[OK] Seeded 15 service catalog items.")

def seed_service_requests(db):
    print("Seeding service requests...")
    import json
    now = datetime.utcnow()
    
    requests_data = [
        {
            "request_id": "REQ0000001",
            "service_id": "SRV003",
            "service_name": "Shared Folder Access",
            "requested_by": "employee",
            "category": "Identity",
            "description": "Access to Shared folder 'Sales-2026' for department report viewing.",
            "status": "SUBMITTED",
            "stage": "Request Submitted",
            "assigned_team": "Sysadmin",
            "estimated_completion": "1 Business Day",
            "sla_hours": 24,
            "details": json.dumps({
                "Folder Path": "\\\\fileserver\\sales\\reports\\2026",
                "Access Type": "Read-Only",
                "Justification": "Need to view Q1 and Q2 sales performance figures for forecasting."
            }),
            "created_hours_ago": 6
        },
        {
            "request_id": "REQ0000002",
            "service_id": "SRV004",
            "service_name": "SAP Account Access",
            "requested_by": "employee",
            "category": "ERP",
            "description": "Requesting transaction access for SAP ERP Production FICO module.",
            "status": "PENDING_APPROVAL",
            "stage": "Pending Approval",
            "assigned_team": "ERP Basis Support",
            "estimated_completion": "2 Business Days",
            "sla_hours": 48,
            "details": json.dumps({
                "SAP System": "Production (PRD)",
                "Role Requested": "FICO Analyst",
                "Justification": "Required for monthly financial reconciliation tasks."
            }),
            "created_hours_ago": 12
        },
        {
            "request_id": "REQ0000003",
            "service_id": "SRV001",
            "service_name": "Software Installation",
            "requested_by": "employee",
            "category": "Software",
            "description": "Request installation of Microsoft Visio license.",
            "status": "COMPLETED",
            "stage": "Request Completed",
            "assigned_team": "Helpdesk",
            "estimated_completion": "1 Business Day",
            "sla_hours": 24,
            "details": json.dumps({
                "Software Name": "Microsoft Visio Professional",
                "Justification": "Need to draft updated network architecture diagrams."
            }),
            "created_hours_ago": 24,
            "resolved_hours_ago": 22
        },
        {
            "request_id": "REQ0000004",
            "service_id": "SRV008",
            "service_name": "New Laptop Provisioning",
            "requested_by": "employee",
            "category": "Hardware",
            "description": "Standard corporate laptop provisioning request.",
            "status": "APPROVED",
            "stage": "Awaiting Fulfillment",
            "assigned_team": "Hardware Support",
            "estimated_completion": "3 Business Days",
            "sla_hours": 72,
            "details": json.dumps({
                "Laptop Model": "Apple MacBook Pro 16-inch (M3 Max)",
                "Justification": "Developer workload: local virtualization and compiler execution."
            }),
            "created_hours_ago": 4
        },
        {
            "request_id": "REQ0000005",
            "service_id": "SRV002",
            "service_name": "VPN Access Request",
            "requested_by": "employee",
            "category": "Network",
            "description": "Remote working Cisco AnyConnect access request.",
            "status": "FULFILLMENT",
            "stage": "Fulfillment in Progress",
            "assigned_team": "Network Team",
            "estimated_completion": "12 Hours",
            "sla_hours": 12,
            "details": json.dumps({
                "MFA Option": "Microsoft Authenticator",
                "Connection Profile": "APAC-Gateway",
                "Justification": "Remote support shifts on-call during weekends."
            }),
            "created_hours_ago": 2
        },
        {
            "request_id": "REQ0000006",
            "service_id": "SRV010",
            "service_name": "Corporate Mobile Device",
            "requested_by": "employee",
            "category": "Hardware",
            "description": "Requesting corporate mobile phone provisioning.",
            "status": "REJECTED",
            "stage": "Request Rejected",
            "assigned_team": "Hardware Support",
            "estimated_completion": "3 Business Days",
            "sla_hours": 72,
            "details": json.dumps({
                "Device Model": "Apple iPhone 15 Pro",
                "Justification": "For testing local push notification packages."
            }),
            "created_hours_ago": 36,
            "resolved_hours_ago": 34
        }
    ]

    for req in requests_data:
        c_time = now - timedelta(hours=req["created_hours_ago"])
        u_time = now - timedelta(hours=req.get("resolved_hours_ago", 0)) if "resolved_hours_ago" in req else now
        
        request = ServiceRequest(
            request_id=req["request_id"],
            service_id=req["service_id"],
            service_name=req["service_name"],
            requested_by=req["requested_by"],
            category=req["category"],
            description=req["description"],
            status=req["status"],
            stage=req["stage"],
            assigned_team=req["assigned_team"],
            estimated_completion=req["estimated_completion"],
            sla_hours=req["sla_hours"],
            details=req["details"],
            created_at=c_time,
            updated_at=u_time
        )
        db.add(request)
        
        # 1. Seed Request Creation Audit Log
        db.add(RbacAuditLog(
            timestamp=c_time,
            user=req["requested_by"],
            role="EMPLOYEE",
            action="create_service_request",
            ticket_id=req["request_id"],
            new_state="NEW",
            details=f"Service request {req['request_id']} initialized in the catalog."
        ))

        # 2. Seed Submission/Transition Logs
        if req["status"] != "NEW":
            sub_time = c_time + timedelta(minutes=10)
            db.add(RbacAuditLog(
                timestamp=sub_time,
                user=req["requested_by"],
                role="EMPLOYEE",
                action="submit_service_request",
                ticket_id=req["request_id"],
                old_state="NEW",
                new_state="SUBMITTED",
                details=f"Service request details submitted by requester."
            ))
            
            # If status is PENDING_APPROVAL
            if req["status"] == "PENDING_APPROVAL":
                db.add(ApprovalHistory(
                    session_id=req["request_id"],
                    recommended_action=f"Approve Service Request: {req['service_name']} for {req['requested_by']}",
                    approval_status="PENDING",
                    created_at=sub_time
                ))
            
            # If status is REJECTED
            elif req["status"] == "REJECTED":
                rej_time = c_time + timedelta(hours=2)
                db.add(ApprovalHistory(
                    session_id=req["request_id"],
                    recommended_action=f"Approve Service Request: {req['service_name']} for {req['requested_by']}",
                    approval_status="REJECTED",
                    created_at=sub_time
                ))
                db.add(RbacAuditLog(
                    timestamp=rej_time,
                    user="manager",
                    role="MANAGER",
                    action="reject_service_request",
                    ticket_id=req["request_id"],
                    old_state="SUBMITTED",
                    new_state="REJECTED",
                    details="Request rejected. Mobile device tier is restricted to management only."
                ))
                
            # If APPROVED, FULFILLMENT, or COMPLETED
            elif req["status"] in ["APPROVED", "FULFILLMENT", "COMPLETED"]:
                app_time = c_time + timedelta(hours=1)
                db.add(ApprovalHistory(
                    session_id=req["request_id"],
                    recommended_action=f"Approve Service Request: {req['service_name']} for {req['requested_by']}",
                    approval_status="APPROVED",
                    created_at=sub_time
                ))
                db.add(RbacAuditLog(
                    timestamp=app_time,
                    user="manager",
                    role="MANAGER",
                    action="approve_service_request",
                    ticket_id=req["request_id"],
                    old_state="SUBMITTED",
                    new_state="APPROVED",
                    details="Request approved by manager."
                ))
                
                if req["status"] in ["FULFILLMENT", "COMPLETED"]:
                    ful_time = c_time + timedelta(hours=1.5)
                    db.add(RbacAuditLog(
                        timestamp=ful_time,
                        user="admin",
                        role="ADMIN",
                        action="start_fulfillment",
                        ticket_id=req["request_id"],
                        old_state="APPROVED",
                        new_state="FULFILLMENT",
                        details="Technician assigned. Fulfillment process started."
                    ))
                    
                    if req["status"] == "COMPLETED":
                        comp_time = c_time + timedelta(hours=2)
                        db.add(RbacAuditLog(
                            timestamp=comp_time,
                            user="admin",
                            role="ADMIN",
                            action="complete_service_request",
                            ticket_id=req["request_id"],
                            old_state="FULFILLMENT",
                            new_state="COMPLETED",
                            details="All service fulfillment tasks finished successfully."
                        ))

    db.commit()
    print("[OK] Seeded 6 service requests with full audit history.")

def seed_devices(db):
    print("Seeding standard demo devices...")
    from app.database.models.device import Device
    from datetime import datetime, timedelta

    devices_to_seed = [
        {
            "id": "JP-TOK-EDG-001",
            "hostname": "JP-TOK-EDG-001",
            "serial_number": "BS-JP-99281",
            "manufacturer": "Lenovo",
            "model": "ThinkPad X1 Carbon Gen 11",
            "operating_system": "Windows 11 Enterprise (v23H2)",
            "ram": 16.0,
            "cpu": 45.2,
            "disk": 256.0,
            "ip_address": "10.142.34.8",
            "mac_address": "00:1A:2B:3C:4D:5E",
            "agent_version": "1.0",
            "status": "Online",
            "username": "takahashi.k",
            "department": "Logistics",
            "installed_software": ["7zip", "Chrome", "Slack", "VPN Client"],
            "running_processes": ["chrome.exe", "slack.exe", "vpn_agent.exe", "explorer.exe"],
            "network_interfaces": [{"name": "Ethernet", "ip": "10.142.34.8", "status": "up"}]
        },
        {
            "id": "US-NSH-LPT-284",
            "hostname": "US-NSH-LPT-284",
            "serial_number": "BS-US-44810",
            "manufacturer": "Dell",
            "model": "Latitude 7440",
            "operating_system": "Windows 11 Enterprise (v22H2)",
            "ram": 32.0,
            "cpu": 18.5,
            "disk": 512.0,
            "ip_address": "10.120.45.102",
            "mac_address": "1A:2B:3C:4D:5E:6F",
            "agent_version": "1.0",
            "status": "Online",
            "username": "smith.j",
            "department": "HR",
            "installed_software": ["Chrome", "Office 365", "Zoom", "7zip"],
            "running_processes": ["msedge.exe", "teams.exe", "outlook.exe"],
            "network_interfaces": [{"name": "Wi-Fi", "ip": "10.120.45.102", "status": "up"}]
        },
        {
            "id": "EU-BRU-SRV-049",
            "hostname": "EU-BRU-SRV-049",
            "serial_number": "BS-EU-00192",
            "manufacturer": "HP",
            "model": "ProLiant DL360 Gen10",
            "operating_system": "Windows Server 2022",
            "ram": 64.0,
            "cpu": 58.0,
            "disk": 1024.0,
            "ip_address": "10.88.12.3",
            "mac_address": "2B:3C:4D:5E:6F:7A",
            "agent_version": "1.0",
            "status": "Online",
            "username": "admin.bru",
            "department": "IT Operations",
            "installed_software": ["IIS", "SQL Server 2019", "7zip"],
            "running_processes": ["sqlservr.exe", "w3wp.exe"],
            "network_interfaces": [{"name": "LAN 1", "ip": "10.88.12.3", "status": "up"}]
        },
        {
            "id": "AP-SGP-LPT-105",
            "hostname": "AP-SGP-LPT-105",
            "serial_number": "BS-AP-77312",
            "manufacturer": "Apple",
            "model": "MacBook Pro 14\"",
            "operating_system": "macOS Sonoma",
            "ram": 16.0,
            "cpu": 0.0,
            "disk": 512.0,
            "ip_address": "10.200.74.52",
            "mac_address": "3C:4D:5E:6F:7A:8B",
            "agent_version": "1.0",
            "status": "Offline",
            "username": "tan.a",
            "department": "Finance",
            "installed_software": ["Excel", "Slack", "Chrome"],
            "running_processes": [],
            "network_interfaces": [{"name": "Wi-Fi", "ip": "10.200.74.52", "status": "down"}]
        },
        {
            "id": "US-DET-LPT-901",
            "hostname": "US-DET-LPT-901",
            "serial_number": "BS-US-88412",
            "manufacturer": "Dell",
            "model": "Precision 5570",
            "operating_system": "Windows 11 Enterprise (v23H2)",
            "ram": 32.0,
            "cpu": 92.0,
            "disk": 1024.0,
            "ip_address": "10.120.89.15",
            "mac_address": "4D:5E:6F:7A:8B:9C",
            "agent_version": "1.0",
            "status": "Error",
            "username": "miller.d",
            "department": "Engineering",
            "installed_software": ["Visual Studio", "Docker Desktop", "Chrome"],
            "running_processes": ["dockerd.exe", "devenv.exe"],
            "network_interfaces": [{"name": "Ethernet", "ip": "10.120.89.15", "status": "up"}]
        },
        {
            "id": "JP-TOK-EDG-002",
            "hostname": "JP-TOK-EDG-002",
            "serial_number": "BS-JP-99282",
            "manufacturer": "Lenovo",
            "model": "ThinkPad L14 Gen 4",
            "operating_system": "Windows 11 Enterprise (v23H2)",
            "ram": 16.0,
            "cpu": 12.0,
            "disk": 256.0,
            "ip_address": "10.142.34.12",
            "mac_address": "5E:6F:7A:8B:9C:0D",
            "agent_version": "0.9",
            "status": "Updating",
            "username": "sato.y",
            "department": "Logistics",
            "installed_software": ["Chrome", "VPN Client"],
            "running_processes": ["winget.exe", "chrome.exe"],
            "network_interfaces": [{"name": "Ethernet", "ip": "10.142.34.12", "status": "up"}]
        },
        {
            "id": "EU-BRU-LPT-012",
            "hostname": "EU-BRU-LPT-012",
            "serial_number": "BS-EU-44510",
            "manufacturer": "Lenovo",
            "model": "ThinkPad T14 Gen 3",
            "operating_system": "Windows 11 Enterprise (v22H2)",
            "ram": 16.0,
            "cpu": 0.0,
            "disk": 256.0,
            "ip_address": "10.88.34.90",
            "mac_address": "6F:7A:8B:9C:0D:1E",
            "agent_version": "1.0",
            "status": "Inactive",
            "username": "dupont.m",
            "department": "Sales",
            "installed_software": ["Chrome", "Office 365"],
            "running_processes": [],
            "network_interfaces": []
        }
    ]

    for dev_data in devices_to_seed:
        last_hb = datetime.utcnow() - timedelta(minutes=5) if dev_data["status"] == "Online" else datetime.utcnow() - timedelta(days=5)
        if dev_data["status"] == "Updating":
            last_hb = datetime.utcnow() - timedelta(minutes=1)

        device = Device(
            id=dev_data["id"],
            hostname=dev_data["hostname"],
            serial_number=dev_data["serial_number"],
            manufacturer=dev_data["manufacturer"],
            model=dev_data["model"],
            operating_system=dev_data["operating_system"],
            ram=dev_data["ram"],
            cpu=dev_data["cpu"],
            disk=dev_data["disk"],
            ip_address=dev_data["ip_address"],
            mac_address=dev_data["mac_address"],
            agent_version=dev_data["agent_version"],
            status=dev_data["status"],
            last_heartbeat=last_hb,
            last_seen=last_hb,
            username=dev_data["username"],
            department=dev_data["department"],
            installed_software=dev_data["installed_software"],
            running_processes=dev_data["running_processes"],
            network_interfaces=dev_data["network_interfaces"]
        )
        db.add(device)
    db.commit()
    print("[OK] Seeded 7 enterprise devices.")

def main():
    db = SessionLocal()
    try:
        clear_data(db)
        seed_users(db)
        seed_tickets_and_audit(db)
        seed_escalations(db)
        seed_notifications(db)
        seed_approvals(db)
        seed_audits_and_security(db)
        seed_scheduler_history(db)
        seed_service_catalog(db)
        seed_service_requests(db)
        seed_devices(db)
        print("="*60)
        print("DATABASE RESET AND DEMO SEED COMPLETED SUCCESSFULLY [OK]")
        print("="*60)
    finally:
        db.close()

if __name__ == "__main__":
    main()
