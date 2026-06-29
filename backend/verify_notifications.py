# verify_notifications.py
# Verification script for notification emission, deduplication, and role filters.

import os
import sys

# Set testing environment variable
os.environ["TESTING"] = "True"
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "app")))

from fastapi.testclient import TestClient
from app.main import app
from app.database.session import get_db
from app.database.models.notification import Notification

def test_notifications():
    print("Running verify_notifications...")
    client = TestClient(app)

    # 1. Login as ADMIN and EMPLOYEE
    admin_login = client.post("/auth/login", json={"username": "admin", "password": "adminpassword"})
    admin_headers = {"Authorization": f"Bearer {admin_login.json()['access_token']}"}

    employee_login = client.post("/auth/login", json={"username": "employee", "password": "employeepassword"})
    employee_headers = {"Authorization": f"Bearer {employee_login.json()['access_token']}"}

    ticket_id = "TKT-NOTIF-TEST"

    # Setup database with isolated transaction block
    with get_db() as db:
        # Cleanup first
        db.query(Notification).filter(Notification.ticket_id == ticket_id).delete()
        db.commit()

        # Insert test notifications
        n1 = Notification(
            notification_id="NOTIF-T1",
            ticket_id=ticket_id,
            recipient="admin",
            message="Critical outage notification for Admin",
            status="SENT"
        )
        n2 = Notification(
            notification_id="NOTIF-T2",
            ticket_id=ticket_id,
            recipient="employee",
            message="Your ticket has been created",
            status="SENT"
        )
        db.add(n1)
        db.add(n2)
        db.commit()

    try:
        # 2. Get notifications as ADMIN (should see all)
        res_admin = client.get("/notifications", headers=admin_headers)
        assert res_admin.status_code == 200
        admin_list = res_admin.json()
        
        # Verify both exist
        admin_ids = [n["notification_id"] for n in admin_list]
        assert "NOTIF-T1" in admin_ids, "Admin should see NOTIF-T1"
        assert "NOTIF-T2" in admin_ids, "Admin should see NOTIF-T2"

        # 3. Get notifications as EMPLOYEE (should only see employee ones)
        res_employee = client.get("/notifications", headers=employee_headers)
        assert res_employee.status_code == 200
        emp_list = res_employee.json()
        
        emp_ids = [n["notification_id"] for n in emp_list]
        assert "NOTIF-T2" in emp_ids, "Employee should see NOTIF-T2"
        assert "NOTIF-T1" not in emp_ids, "Employee should NOT see admin notification NOTIF-T1"

        # 4. Verify no duplicates are allowed for identical notification IDs
        with get_db() as db:
            from app.services.notification_service import create_notification
            # Attempting to send a warning notification
            create_notification(ticket_id=ticket_id, recipient="employee", message="Duplicate warning message")
            
            # Retrieve notifications directly from DB
            db_notifications = db.query(Notification).filter(Notification.ticket_id == ticket_id).all()
            notif_ids = [n.notification_id for n in db_notifications]
            assert len(notif_ids) == len(set(notif_ids)), "Notification IDs must be unique (no duplicate keys)"

        print("[PASS] verify_notifications.py: Notification role filters and uniqueness verified successfully!")

    finally:
        # Cleanup
        with get_db() as db:
            db.query(Notification).filter(Notification.ticket_id == ticket_id).delete()
            db.commit()

if __name__ == "__main__":
    test_notifications()
