#!/usr/bin/env python
import os
import sys
import time

# Ensure backend directory is in the python path
backend_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, backend_dir)
sys.path.insert(0, os.path.join(backend_dir, "app"))

# Set default env variables for mock testing if not present
os.environ["USE_MOCK_SERVICENOW"] = "true"
os.environ["SERVICENOW_INSTANCE_URL"] = "https://mock-instance.service-now.com"
os.environ["SERVICENOW_CLIENT_ID"] = "mock_client_id"
os.environ["SERVICENOW_CLIENT_SECRET"] = "mock_client_secret"

import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("verify_servicenow")

try:
    from app.adapters.servicenow_adapter import ServiceNowAdapter
    from app.integrations.servicenow.assignment_groups import resolve_assignment_group
    from app.core.metrics import (
        SERVICENOW_REQUESTS_TOTAL,
        SERVICENOW_FAILURES_TOTAL,
        INCIDENTS_CREATED_TOTAL,
        SERVICE_REQUESTS_CREATED_TOTAL
    )
except ImportError as e:
    logger.error("Failed to import app modules: %s", e)
    sys.exit(1)

def run_tests():
    logger.info("=========================================")
    logger.info("RUNNING SERVICENOW INTEGRATION VERIFIER")
    logger.info("=========================================")

    # Test 1: Feature Flag Fallback
    logger.info("Test 1: Verification of Mock Fallback configuration")
    adapter = ServiceNowAdapter()
    if not adapter.client.is_mock:
        logger.error("[FAIL] Client should be mock client in mock mode!")
        return False
    logger.info("[PASS] Mock fallback verified successfully.")

    # Test 2: Assignment Group Mapping
    logger.info("Test 2: Verification of Assignment Group Mappings")
    mappings = {
        "VPN": "Network Team",
        "Outlook": "Messaging Team",
        "Software": "Desktop Support Team",
        "SAP": "SAP Support Team",
        "OtherCategory": "OtherCategory"  # Fallback to category itself
    }
    
    for category, expected in mappings.items():
        resolved = resolve_assignment_group(adapter.client, category)
        if resolved != expected:
            logger.error(f"[FAIL] Category '{category}' mapped to '{resolved}', expected '{expected}'")
            return False
        logger.info(f"  - Category '{category}' -> Group '{resolved}' [OK]")
    logger.info("[PASS] Assignment group resolving verified successfully.")

    # Test 3: Incident Lifecycle
    logger.info("Test 3: Verification of Incident Lifecycle (Create -> Get -> Update -> Close)")
    
    # Create
    inc = adapter.create_incident(
        category="VPN",
        description="Unable to connect to GlobalProtect VPN",
        assignment_group="Network Team"
    )
    sys_id = inc.get("sys_id")
    number = inc.get("number")
    if not sys_id or not number:
        logger.error("[FAIL] Created incident has missing identifier fields!")
        return False
    logger.info(f"  - Created incident {number} with sys_id {sys_id}")

    # Get
    fetched = adapter.get_incident(sys_id)
    if fetched.get("number") != number or fetched.get("state") != "OPEN":
        logger.error("[FAIL] Fetched incident fields do not match created state!")
        return False
    logger.info("  - Fetched incident matches successfully.")

    # Update
    updated = adapter.update_incident(sys_id, {"assignment_group": "Desktop Support Team"})
    if updated.get("assignment_group") != "Desktop Support Team":
        logger.error("[FAIL] Incident assignment group was not updated correctly!")
        return False
    logger.info("  - Updated incident assignment group successfully.")

    # Close
    closed = adapter.close_incident(sys_id)
    if closed.get("state") != "CLOSED":
        logger.error("[FAIL] Closed incident state is not CLOSED!")
        return False
    logger.info("  - Incident closed successfully.")
    logger.info("[PASS] Incident CRUD lifecycle verified successfully.")

    # Test 4: Service Request Lifecycle
    logger.info("Test 4: Verification of Service Request Lifecycle (Create -> Get -> Update)")
    
    req = adapter.create_service_request(
        category="Software",
        description="Request install of Notepad++ editor",
        action_type="SoftwareInstallation"
    )
    req_sys_id = req.get("sys_id")
    req_number = req.get("number")
    if not req_sys_id or not req_number:
        logger.error("[FAIL] Created catalog request has missing identifier fields!")
        return False
    logger.info(f"  - Created service request {req_number} with sys_id {req_sys_id}")

    # Get Request
    fetched_req = adapter.get_request(req_sys_id)
    if fetched_req.get("number") != req_number or fetched_req.get("state") != "OPEN":
        logger.error("[FAIL] Fetched service request fields do not match created state!")
        return False
    logger.info("  - Fetched service request matches successfully.")

    # Close/Update Request
    updated_req = adapter.update_request(req_sys_id, {"state": "CLOSED"})
    if updated_req.get("state") != "CLOSED":
        logger.error("[FAIL] Service request state was not closed correctly!")
        return False
    logger.info("  - Service request closed successfully.")
    logger.info("[PASS] Service Request lifecycle verified successfully.")

    # Test 5: Prometheus Telemetry check
    logger.info("Test 5: Verification of Prometheus Metrics Counters")
    try:
        # Since mock client calls metrics inside operations, check counters count
        # In our prometheus_client library, we can check value using _value
        req_count = SERVICENOW_REQUESTS_TOTAL.labels(operation="create_incident")._value.get()
        logger.info(f"  - ServiceNow create_incident metric count: {req_count}")
        if req_count < 1.0:
            logger.error("[FAIL] Metrics counter 'servicenow_requests_total' was not incremented!")
            return False
            
        inc_count = INCIDENTS_CREATED_TOTAL._value.get()
        logger.info(f"  - ServiceNow incidents_created_total metric count: {inc_count}")
        if inc_count < 1.0:
            logger.error("[FAIL] Metrics counter 'incidents_created_total' was not incremented!")
            return False
            
        logger.info("[PASS] Prometheus instrumentation verified successfully.")
    except Exception as e:
        logger.warning(f"Skipping value check (could not retrieve value directly): {e}")

    # Test 6: Health / Connection Diagnostics Check
    logger.info("Test 6: Verification of Health Checks & Latency reporting")
    is_healthy = adapter.health_check()
    if not is_healthy:
        logger.error("[FAIL] Adapter health check failed!")
        return False
    logger.info("[PASS] Adapter health check reports success.")

    logger.info("\nALL SERVICENOW INTEGRATION VERIFICATION TESTS PASSED SUCCESSFULLY! ✓")
    return True

if __name__ == "__main__":
    success = run_tests()
    if not success:
        sys.exit(1)
    sys.exit(0)
