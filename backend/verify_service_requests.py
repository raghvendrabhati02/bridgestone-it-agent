import os
import sys

# Add app directory to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "app")))

from app.database.connection import SessionLocal
from app.database.models.service_request import ServiceRequest
from app.services.catalog_service import get_service_requests, get_service_request_details, perform_request_action
from app.services import analytics_service

def verify_requests():
    print("=== Service Request Verification ===")
    db = SessionLocal()
    failures = []
    
    def check(name, condition, message):
        if condition:
            print(f"  [PASS] {name}: {message}")
        else:
            print(f"  [FAIL] {name}: {message}")
            failures.append(name)

    try:
        # 1. Verification of Seeded Service Requests
        requests = get_service_requests()
        check("Requests Count", len(requests) == 6, f"Expected 6 service requests, got {len(requests)}.")
        
        # 2. Details retrieval
        req1_details = get_service_request_details("REQ0000001")
        check("REQ0000001 Details Retrieval", req1_details is not None, "Failed to retrieve REQ0000001 details.")
        if req1_details:
            check("REQ0000001 Category", req1_details["category"] == "Identity", f"Expected category 'Identity', got {req1_details['category']}.")
            check("REQ0000001 Status", req1_details["status"] == "SUBMITTED", f"Expected status 'SUBMITTED', got {req1_details['status']}.")
            check("REQ0000001 Timeline length", len(req1_details["timeline"]) >= 2, f"Expected at least 2 timeline events, got {len(req1_details['timeline'])}.")
            
        # 3. Test Lifecycle Actions
        # Test approval action (MANAGER role on REQ0000002)
        res = perform_request_action("REQ0000002", "approve", "manager", "MANAGER", "Approving SAP access for project requirements")
        check("REQ0000002 Approved", res["status"] == "APPROVED", f"Expected APPROVED status, got {res['status']}.")
        check("REQ0000002 Stage", res["stage"] == "Awaiting Fulfillment", f"Expected 'Awaiting Fulfillment' stage, got {res['stage']}.")
        check("REQ0000002 Approval Status", res["approval_status"] == "APPROVED", f"Expected approval_status 'APPROVED', got {res['approval_status']}.")
        
        # Test start_fulfillment action (ADMIN role on REQ0000002)
        res = perform_request_action("REQ0000002", "start_fulfillment", "admin", "ADMIN", "Fulfillment setup starting")
        check("REQ0000002 Fulfillment Status", res["status"] == "FULFILLMENT", f"Expected FULFILLMENT status, got {res['status']}.")
        check("REQ0000002 Fulfillment Stage", res["stage"] == "Fulfillment in Progress", f"Expected 'Fulfillment in Progress' stage, got {res['stage']}.")
        
        # Test complete action (ADMIN role on REQ0000002)
        res = perform_request_action("REQ0000002", "complete", "admin", "ADMIN", "SAP account created")
        check("REQ0000002 Completed Status", res["status"] == "COMPLETED", f"Expected COMPLETED status, got {res['status']}.")
        
        # Test close action (Requester role on REQ0000002)
        res = perform_request_action("REQ0000002", "close", "employee", "EMPLOYEE", "Access verified")
        check("REQ0000002 Closed Status", res["status"] == "CLOSED", f"Expected CLOSED status, got {res['status']}.")

        # 4. Test Analytics Calculations
        analytics = analytics_service.get_service_request_metrics(db)
        check("Analytics: Total Requests", analytics["total_requests"] == 6, f"Expected 6 total requests, got {analytics['total_requests']}.")
        check("Analytics: Completed/Closed Average", analytics["avg_fulfillment_hours"] > 0, f"Expected average fulfillment hours > 0, got {analytics['avg_fulfillment_hours']}.")
        
        print("\n" + "="*55)
        if len(failures) == 0:
            print("  ALL SERVICE REQUEST CHECKS PASSED [OK]")
        else:
            print(f"  VERIFICATION FAILED: {len(failures)} checks failed [ERROR]")
        print("="*55)
        
    finally:
        db.close()

if __name__ == "__main__":
    verify_requests()
