import os
import sys

# Force UTF-8 output on Windows terminals
if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "app")))

from app.database.connection import SessionLocal
from app.database.models.ticket import Ticket
from app.database.models.notification import Notification
from app.database.models.approval_history import ApprovalHistory
from app.database.models.action_history import ActionHistory
from app.database.models.user import User

def verify_demo_cleanup():
    print("Running verify_demo_cleanup.py...")
    db = SessionLocal()
    failures = []

    def check(name, condition, msg):
        if condition:
            print(f"  [\u2705 PASS] {name}: {msg}")
        else:
            print(f"  [\u274c FAIL] {name}: {msg}")
            failures.append(name)

    try:
        # 1. Check ticket ID naming convention
        tickets = db.query(Ticket).all()
        tck_count = sum(1 for t in tickets if t.ticket_id.startswith("TCK-"))
        inc_count = sum(1 for t in tickets if t.ticket_id.startswith("INC0000"))
        check(
            "Ticket IDs Cleaned",
            tck_count == 0 and inc_count > 0,
            f"Found {tck_count} TCK- tickets, expected 0. Found {inc_count} INC0000 tickets."
        )

        # 2. Check notification ID naming convention
        notifications = db.query(Notification).all()
        not_count = sum(1 for n in notifications if n.notification_id.startswith("NOT-"))
        ntf_count = sum(1 for n in notifications if n.notification_id.startswith("NTF"))
        check(
            "Notification IDs Cleaned",
            not_count == 0 and ntf_count > 0,
            f"Found {not_count} NOT- notifications, expected 0. Found {ntf_count} NTF notifications."
        )

        # 3. Check approvals session IDs
        approvals = db.query(ApprovalHistory).all()
        seed_approvals = sum(1 for a in approvals if "seed" in a.session_id)
        check(
            "Approval Session IDs Cleaned",
            seed_approvals == 0,
            f"Found {seed_approvals} approvals containing '-seed' in their session ID."
        )

        # 4. Check action histories
        actions = db.query(ActionHistory).all()
        seed_actions = sum(1 for a in actions if "seed" in a.request_id)
        check(
            "Action History Request IDs Cleaned",
            seed_actions == 0,
            f"Found {seed_actions} actions containing '-seed' in request_id."
        )

        # 5. Check no legacy hardcoded profile names in DB
        # Users should have their correct role credentials
        db_users = db.query(User).all()
        roles_match = all(u.role in ("EMPLOYEE", "MANAGER", "ADMIN") for u in db_users)
        check(
            "User Roles Validated",
            roles_match and len(db_users) == 3,
            "User counts or roles mismatched."
        )

    finally:
        db.close()

    if failures:
        print(f"[FAIL] verify_demo_cleanup.py failed with checks: {failures}")
        sys.exit(1)
    else:
        print("[PASS] verify_demo_cleanup.py successfully passed all checks!")
        sys.exit(0)

if __name__ == "__main__":
    verify_demo_cleanup()
