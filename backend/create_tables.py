import os
import sys

# Add app directory to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "app")))

from app.database.connection import engine, SessionLocal
from app.database.base import Base
import app.database.models  # Registers all models
from app.database.models.user import User
from app.core.security import hash_password

def init_db():
    print("Dropping existing tables to migrate user model schema...")
    try:
        Base.metadata.drop_all(bind=engine)
        print("[OK] Old tables dropped.")
    except Exception as e:
        print(f"Warning during drop_all: {e}")

    print("Initializing database tables...")
    Base.metadata.create_all(bind=engine)
    print("[OK] Tables created successfully!")

    print("Seeding database with default enterprise users...")
    db = SessionLocal()
    try:
        # Predefined demo accounts
        users_to_seed = [
            {
                "username": "employee",
                "email": "employee@bridgestone.com",
                "role": "EMPLOYEE",
                "password": "employeepassword"
            },
            {
                "username": "manager",
                "email": "manager@bridgestone.com",
                "role": "MANAGER",
                "password": "managerpassword"
            },
            {
                "username": "admin",
                "email": "admin@bridgestone.com",
                "role": "ADMIN",
                "password": "adminpassword"
            }
        ]

        for u_data in users_to_seed:
            existing = db.query(User).filter(User.username == u_data["username"]).first()
            if not existing:
                hashed = hash_password(u_data["password"])
                user = User(
                    username=u_data["username"],
                    email=u_data["email"],
                    role=u_data["role"],
                    hashed_password=hashed,
                    is_active=True
                )
                db.add(user)
                print(f"Seeded user: {u_data['username']} ({u_data['role']})")
        
        # Seed default devices
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
            existing_dev = db.query(Device).filter(Device.id == dev_data["id"]).first()
            if not existing_dev:
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
                print(f"Seeded device: {dev_data['hostname']}")
        
        # Seed default executions history
        from app.database.models.execution_history import ExecutionHistory
        import json
        
        executions_to_seed = [
            {
                "username": "employee",
                "device_id": "JP-TOK-EDG-001",
                "action_name": "Flush DNS",
                "result": "SUCCESS",
                "status": "Success",
                "duration": 0.85,
                "logs": "Initializing DNS cache flush...\n[SUCCESS] DNS Resolver Cache successfully flushed.",
                "parameters": "{}",
                "started_at": datetime.utcnow() - timedelta(hours=2),
                "completed_at": datetime.utcnow() - timedelta(hours=2, seconds=-1),
                "agent_version": "1.0",
                "department": "Logistics"
            },
            {
                "username": "manager",
                "device_id": "US-NSH-LPT-284",
                "action_name": "Restart Outlook",
                "result": "SUCCESS",
                "status": "Success",
                "duration": 1.2,
                "logs": "Locating outlook.exe process...\nKilling process PID 8421\nRestarting Outlook process...\n[SUCCESS] Microsoft Outlook restarted successfully.",
                "parameters": "{}",
                "started_at": datetime.utcnow() - timedelta(hours=1),
                "completed_at": datetime.utcnow() - timedelta(hours=1, seconds=-2),
                "agent_version": "1.0",
                "department": "HR"
            },
            {
                "username": "employee",
                "device_id": "EU-BRU-SRV-049",
                "action_name": "Install Approved Software",
                "result": "FAILED",
                "status": "Failed",
                "duration": 4.5,
                "logs": "Downloading VS Code installer...\nVerifying signature...\nError: Signature verification failed. Installer corrupt.\n[FAIL] Installation failed.",
                "parameters": json.dumps({"software": "VS Code"}),
                "started_at": datetime.utcnow() - timedelta(hours=4),
                "completed_at": datetime.utcnow() - timedelta(hours=4, seconds=-5),
                "agent_version": "1.0",
                "department": "IT Operations"
            },
            {
                "username": "miller.d",
                "device_id": "US-DET-LPT-901",
                "action_name": "Clear Print Queue",
                "result": "SUCCESS",
                "status": "Success",
                "duration": 0.5,
                "logs": "Stopping Print Spooler...\nDeleting temporary print files...\nStarting Print Spooler...\n[SUCCESS] Print queue cleared.",
                "parameters": "{}",
                "started_at": datetime.utcnow() - timedelta(days=1),
                "completed_at": datetime.utcnow() - timedelta(days=1, seconds=-1),
                "agent_version": "1.0",
                "department": "Engineering"
            },
            {
                "username": "tan.a",
                "device_id": "AP-SGP-LPT-105",
                "action_name": "Renew IP",
                "result": "FAILED",
                "status": "Cancelled",
                "duration": 2.1,
                "logs": "Initiating DHCP release...\nUser requested cancellation of operation.\n[CANCELLED] Operation terminated.",
                "parameters": "{}",
                "started_at": datetime.utcnow() - timedelta(days=1, hours=2),
                "completed_at": datetime.utcnow() - timedelta(days=1, hours=2, seconds=-2),
                "agent_version": "1.0",
                "department": "Finance"
            },
            {
                "username": "dupont.m",
                "device_id": "EU-BRU-LPT-012",
                "action_name": "Restart Print Spooler",
                "result": "SUCCESS",
                "status": "Running",
                "duration": 0.0,
                "logs": "Initiating spooler service restart...",
                "parameters": "{}",
                "started_at": datetime.utcnow() - timedelta(minutes=5),
                "completed_at": None,
                "agent_version": "1.0",
                "department": "Sales"
            },
            {
                "username": "employee",
                "device_id": "JP-TOK-EDG-002",
                "action_name": "Sync OneDrive",
                "result": "SUCCESS",
                "status": "Pending",
                "duration": 0.0,
                "logs": "Waiting in queue...",
                "parameters": "{}",
                "started_at": datetime.utcnow() - timedelta(minutes=1),
                "completed_at": None,
                "agent_version": "0.9",
                "department": "Logistics"
            }
        ]
        
        for exec_data in executions_to_seed:
            entry = ExecutionHistory(
                username=exec_data["username"],
                device_id=exec_data["device_id"],
                action_name=exec_data["action_name"],
                result=exec_data["result"],
                status=exec_data["status"],
                duration=exec_data["duration"],
                logs=exec_data["logs"],
                parameters=exec_data["parameters"],
                started_at=exec_data["started_at"],
                completed_at=exec_data["completed_at"],
                agent_version=exec_data["agent_version"],
                department=exec_data["department"]
            )
            db.add(entry)
            print(f"Seeded execution: {exec_data['action_name']} for {exec_data['username']}")
            
        db.commit()
        print("[OK] Database seeded successfully!")
    except Exception as e:
        db.rollback()
        print(f"Error seeding database: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    init_db()
