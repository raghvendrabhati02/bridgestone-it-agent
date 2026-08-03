"""
test_mock_itsm_platform.py
─────────────────────────────────────────────────────────────────────────────
Comprehensive unit and integration test suite for Enterprise Mock ITSM Platform (Sprint 2 & 3).
"""

import unittest
from app.mock_itsm.database import get_mock_itsm_db, init_mock_itsm_db
from app.mock_itsm.services.mock_incident_service import MockIncidentService
from app.mock_itsm.services.mock_assignment_service import MockAssignmentService
from app.mock_itsm.services.mock_approval_service import MockApprovalService
from app.mock_itsm.services.mock_sla_service import MockSLAService
from app.adapters.mock_itsm_adapter import MockITSMAdapter


class TestMockITSMPlatform(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_mock_itsm_db()

    def test_01_assignment_routing_logic(self):
        """Verify routing rules for categories."""
        self.assertEqual(MockAssignmentService.get_assignment_team("VPN"), "Network Team")
        self.assertEqual(MockAssignmentService.get_assignment_team("Outlook"), "Microsoft 365 Team")
        self.assertEqual(MockAssignmentService.get_assignment_team("Software"), "Software Support")
        self.assertEqual(MockAssignmentService.get_assignment_team("Printer"), "Hardware Support")
        self.assertEqual(MockAssignmentService.get_assignment_team("Security"), "Security Team")
        self.assertEqual(MockAssignmentService.get_assignment_team("General"), "Service Desk")

    def test_02_sla_hours_calculation(self):
        """Verify SLA priority & hours mapping."""
        self.assertEqual(MockSLAService.calculate_sla_hours("CRITICAL"), 1)
        self.assertEqual(MockSLAService.calculate_sla_hours("HIGH"), 4)
        self.assertEqual(MockSLAService.calculate_sla_hours("MEDIUM"), 8)
        self.assertEqual(MockSLAService.calculate_sla_hours("LOW"), 24)

    def test_03_create_ticket_auto_numbering(self):
        """Verify auto-generation of INC0000001, INC0000002... ticket numbers."""
        with get_mock_itsm_db() as db:
            svc = MockIncidentService(db)
            t1 = svc.create_incident(
                category="VPN",
                description="Unable to connect to VPN from home",
                created_by="johndoe"
            )
            self.assertTrue(t1.ticket_number.startswith("INC"))
            self.assertEqual(t1.assigned_group, "Network Team")
            self.assertEqual(t1.status, "Assigned")

            t2 = svc.create_incident(
                category="Outlook",
                description="Outlook crashes on startup",
                created_by="johndoe"
            )
            self.assertTrue(t2.ticket_number.startswith("INC"))
            self.assertEqual(t2.assigned_group, "Microsoft 365 Team")
            self.assertNotEqual(t1.ticket_number, t2.ticket_number)

    def test_04_ticket_lifecycle_transitions(self):
        """Verify state machine: New -> Assigned -> In Progress -> Resolved -> Closed."""
        with get_mock_itsm_db() as db:
            svc = MockIncidentService(db)
            t = svc.create_incident(category="Printer", description="Paper jam in Office Printer")
            num = t.ticket_number

            # Update status to In Progress
            t_in_progress = svc.update_incident(ticket_number=num, status="In Progress", changed_by="engineer")
            self.assertEqual(t_in_progress.status, "In Progress")

            # Resolve ticket
            t_resolved = svc.update_incident(ticket_number=num, status="Resolved", resolution_notes="Cleared paper jam", changed_by="engineer")
            self.assertEqual(t_resolved.status, "Resolved")
            self.assertIsNotNone(t_resolved.resolved_at)

            # Close ticket
            t_closed = svc.close_incident(ticket_number=num, closed_by="admin")
            self.assertEqual(t_closed.status, "Closed")
            self.assertIsNotNone(t_closed.closed_at)

    def test_05_sprint3_approval_workflow(self):
        """Verify Sprint 3 Approval Workflow requirements."""
        with get_mock_itsm_db() as db:
            svc = MockIncidentService(db)
            app_svc = MockApprovalService(db)

            # 1. Create ticket linked to approval
            t = svc.create_incident(category="Software", description="Requesting Admin Access for dev environment", created_by="employee1")
            num = t.ticket_number

            # 2. Submit approval request for 'Admin Access'
            app_req = app_svc.request_approval(
                ticket_number=num,
                requester="employee1",
                approver="manager1",
                approver_role="MANAGER",
                approval_type="Admin Access",
                comments="Required for local debugging"
            )
            self.assertEqual(app_req["status"], "PENDING")
            self.assertEqual(app_req["requester"], "employee1")
            self.assertEqual(app_req["approval_type"], "Admin Access")
            app_id = app_req["id"]

            # 3. Manager views pending approvals
            pending = app_svc.get_pending_approvals(approver_username="manager1")
            self.assertTrue(any(p["id"] == app_id for p in pending))

            # 4. Employee views their requests
            my_requests = app_svc.get_my_requests(requester_username="employee1")
            self.assertTrue(any(r["id"] == app_id for r in my_requests))

            # 5. Manager approves request
            action_res = app_svc.action_approval(
                approval_id=app_id,
                approver_username="manager1",
                decision="APPROVED",
                comments="Granted for 48 hours"
            )
            self.assertEqual(action_res["status"], "APPROVED")

            # 6. Admin views all approvals
            all_apps = app_svc.get_all_approvals()
            self.assertTrue(any(a["id"] == app_id for a in all_apps))

    def test_06_itsm_adapter_contract(self):
        """Verify MockITSMAdapter compliance with ITSMAdapter contract."""
        adapter = MockITSMAdapter()
        self.assertTrue(adapter.health_check())

        inc_res = adapter.create_incident(
            category="VPN",
            description="VPN connection dropped",
            assignment_group="Network Team",
            caller_id="testuser"
        )
        self.assertTrue(inc_res["success"])
        self.assertTrue(inc_res["number"].startswith("INC"))

        sys_id = inc_res["sys_id"]
        fetched = adapter.get_incident(sys_id)
        self.assertEqual(fetched["number"], sys_id)
        self.assertEqual(fetched["category"], "VPN")


if __name__ == "__main__":
    unittest.main()
