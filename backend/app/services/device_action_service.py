import time
from datetime import datetime
from sqlalchemy.orm import Session
from app.database.models.execution_history import ExecutionHistory
from app.database.models.rbac_audit_log import RbacAuditLog
from app.database.models.ticket import Ticket, TicketState
from app.database.models.user import User

# List of actions and their approval requirements
ACTIONS_METADATA = {
    "Restart Computer": {"approval": "NONE", "desc": "Reboots the device operating system gracefully."},
    "Restart Outlook": {"approval": "NONE", "desc": "Restarts Microsoft Outlook app process."},
    "Restart Teams": {"approval": "NONE", "desc": "Restarts Microsoft Teams app process."},
    "Flush DNS": {"approval": "NONE", "desc": "Clears the local DNS resolver cache."},
    "Renew IP": {"approval": "NONE", "desc": "Requests a new DHCP lease for network interface cards."},
    "Clear Print Queue": {"approval": "NONE", "desc": "Clears all cached and pending print jobs."},
    "Restart Print Spooler": {"approval": "NONE", "desc": "Restarts print spooler local service daemon."},
    "Connect VPN": {"approval": "NONE", "desc": "Establishes corporate VPN tunnel session."},
    "Disconnect VPN": {"approval": "NONE", "desc": "Tears down the active VPN tunnel session."},
    "Network Diagnostics": {"approval": "NONE", "desc": "Runs ping, traceroute, and packet diagnostic checks."},
    "BitLocker Recovery": {"approval": "ADMIN", "desc": "Retrieves local drive BitLocker recovery keys."},
    "Install Approved Software": {"approval": "MANAGER", "desc": "Downloads and installs white-listed software catalog apps."},
    "Update Approved Software": {"approval": "NONE", "desc": "Checks and updates installed approved packages."},
    "Restart Windows Explorer": {"approval": "NONE", "desc": "Restarts explorer.exe desktop shell process."},
    "Sync OneDrive": {"approval": "NONE", "desc": "Triggers OneDrive cloud synchronization."},
    "Open Software Center": {"approval": "NONE", "desc": "Launches the Microsoft Software Center console."},
    "Map Network Drive": {"approval": "NONE", "desc": "Maps corporate shared volumes to drive letters."},
    "Clear Temp Files": {"approval": "NONE", "desc": "Clears system and local user cache temp folders."},
    "System Information": {"approval": "NONE", "desc": "Retrieves detailed CPU, RAM, and hardware configuration info."},
    "SAP Installation": {"approval": "MANAGER", "desc": "Downloads and installs SAP GUI suite."}
}

class DeviceActionService:

    @staticmethod
    def get_actions(username: str, db: Session):
        """
        Get all action cards and check if user has approved tickets to execute restricted actions.
        """
        # Fetch approved/resolved/fulfilled tickets for this user
        approved_tickets = db.query(Ticket).filter(
            Ticket.created_by == username,
            Ticket.status.in_([TicketState.APPROVED.value, TicketState.RESOLVED.value, TicketState.CLOSED.value])
        ).all()

        approved_categories = {t.category.upper() for t in approved_tickets}

        results = []
        for name, meta in ACTIONS_METADATA.items():
            req_approval = meta["approval"]
            is_approved = True

            # If action requires manager or admin approval, check tickets
            if req_approval == "MANAGER":
                # Check for Software Installation or SAP category approvals
                category_match = "SOFTWARE" in name.upper() or "SAP" in name.upper()
                is_approved = any("SOFTWARE" in cat or "SAP" in cat for cat in approved_categories)
            elif req_approval == "ADMIN":
                is_approved = any("BITLOCKER" in cat or "SECURITY" in cat for cat in approved_categories)

            results.append({
                "action_name": name,
                "description": meta["desc"],
                "approval_required": req_approval,
                "approved_for_user": is_approved
            })
        return results

    @staticmethod
    def execute_action(username: str, device_id: str, action_name: str, db: Session):
        """
        Validates permissions, performs execution simulation, logs history, and records audit trail.
        """
        start_time = time.time()
        
        # 1. Fetch user role
        user = db.query(User).filter(User.username == username).first()
        role = user.role if user else "EMPLOYEE"

        # 2. Check action metadata
        if action_name not in ACTIONS_METADATA:
            raise ValueError(f"Action '{action_name}' is not recognized.")

        meta = ACTIONS_METADATA[action_name]
        req_approval = meta["approval"]

        # 3. Validate Permission and Approval Integration
        is_authorized = True
        reason = None

        if req_approval == "MANAGER" and role != "MANAGER" and role != "ADMIN":
            # Check if user has an approved service request ticket for Software or SAP
            approved_tickets = db.query(Ticket).filter(
                Ticket.created_by == username,
                Ticket.status.in_([TicketState.APPROVED.value, TicketState.RESOLVED.value, TicketState.CLOSED.value])
            ).all()
            approved_categories = {t.category.upper() for t in approved_tickets}
            category_match = any("SOFTWARE" in cat or "SAP" in cat for cat in approved_categories)
            if not category_match:
                is_authorized = False
                reason = "Manager approval is required. Please submit a Service Request ticket in the support portal."

        elif req_approval == "ADMIN" and role != "ADMIN":
            # Check if user has an approved ticket for BitLocker
            approved_tickets = db.query(Ticket).filter(
                Ticket.created_by == username,
                Ticket.status.in_([TicketState.APPROVED.value, TicketState.RESOLVED.value, TicketState.CLOSED.value])
            ).all()
            approved_categories = {t.category.upper() for t in approved_tickets}
            category_match = any("BITLOCKER" in cat or "SECURITY" in cat for cat in approved_categories)
            if not category_match:
                is_authorized = False
                reason = "Admin approval is required. Please submit an Incident ticket to the Network/Security group."

        # Simulate execution duration
        time.sleep(1.0) # simulate process delay
        duration = round(time.time() - start_time, 2)

        # 4. Determine result and generate logs
        if not is_authorized:
            result = "FAILED"
            logs = f"Validation failed: {reason}"
        else:
            result = "SUCCESS"
            logs = (
                f"[INFO] Initializing Enterprise Device Agent connection...\n"
                f"[INFO] Running validation parameters for action '{action_name}'\n"
                f"[SUCCESS] Privilege check passed.\n"
                f"[INFO] Executing target command on host device {device_id}...\n"
                f"[SUCCESS] Command execution completed successfully."
            )

        # 5. Store execution history
        history_entry = ExecutionHistory(
            timestamp=datetime.utcnow(),
            username=username,
            device_id=device_id,
            action_name=action_name,
            result=result,
            duration=duration,
            logs=logs
        )
        db.add(history_entry)

        # 6. Audit Log
        audit_log = RbacAuditLog(
            timestamp=datetime.utcnow(),
            user=username,
            role=role,
            action=f"execute_device_action: {action_name}",
            details=f"Device: {device_id} | Result: {result} | Duration: {duration}s"
        )
        db.add(audit_log)

        db.commit()

        return {
            "action_name": action_name,
            "device_id": device_id,
            "result": result,
            "duration": duration,
            "logs": logs
        }

    @staticmethod
    def get_execution_history(db: Session, username: str = None):
        """
        Retrieves action execution history. If user is employee, returns only theirs.
        If user is manager/admin, returns all history.
        """
        query = db.query(ExecutionHistory)
        if username:
            query = query.filter(ExecutionHistory.username == username)
        return query.order_by(ExecutionHistory.timestamp.desc()).all()
