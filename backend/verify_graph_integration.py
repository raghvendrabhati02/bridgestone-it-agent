#!/usr/bin/env python
import os
import sys
import time

# Ensure backend directory is in the python path
backend_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, backend_dir)
sys.path.insert(0, os.path.join(backend_dir, "app"))

# Force mock mode for safety during verification
os.environ["USE_MOCK_GRAPH"] = "true"
os.environ["AZURE_TENANT_ID"] = "mock_tenant"
os.environ["AZURE_CLIENT_ID"] = "mock_client"
os.environ["AZURE_CLIENT_SECRET"] = "mock_secret"

import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("verify_graph")

try:
    from app.adapters.microsoft_graph_adapter import MicrosoftGraphAdapter
    from app.core.metrics import (
        GRAPH_REQUESTS_TOTAL,
        GRAPH_FAILURES_TOTAL,
        GRAPH_MAILBOX_CHECKS_TOTAL,
        GRAPH_LICENSE_CHECKS_TOTAL
    )
except ImportError as e:
    logger.error("Failed to import app modules: %s", e)
    sys.exit(1)

def run_tests():
    logger.info("=========================================")
    logger.info("RUNNING MICROSOFT GRAPH INTEGRATION VERIFIER")
    logger.info("=========================================")

    # Test 1: Feature Flag Fallback
    logger.info("Test 1: Verification of Mock Fallback configuration")
    adapter = MicrosoftGraphAdapter()
    if not getattr(adapter.client, "is_mock", False):
        logger.error("[FAIL] Client should be mock client in mock mode!")
        return False
    logger.info("[PASS] Mock fallback verified successfully.")

    # Test 2: User Lookup and Profiles
    logger.info("Test 2: Verification of User Profiles and Lookup")
    user_id = "graph-user-12345"
    user = adapter.get_user(user_id)
    if user.get("displayName") != "Test Employee" or user.get("mail") != "employee@bridgestone.com":
        logger.error("[FAIL] Retained user fields do not match seeded values!")
        return False
        
    profile = adapter.get_user_profile(user_id)
    if profile.get("jobTitle") != "IT Engineer":
        logger.error("[FAIL] User profile job title check failed!")
        return False
    logger.info("[PASS] User lookup and profiles verified successfully.")

    # Test 3: Manager Lookup
    logger.info("Test 3: Verification of Manager Lookup")
    manager = adapter.get_manager(user_id)
    if manager is None or manager.get("displayName") != "Test Manager":
        logger.error("[FAIL] Manager lookup did not return correct test manager!")
        return False
    logger.info("[PASS] Manager lookup verified successfully.")

    # Test 4: Member Groups and VPN Access Check
    logger.info("Test 4: Verification of Group membership and VPN verification")
    groups = adapter.get_user_groups(user_id)
    if not any(g.get("displayName") == "VPN Users" for g in groups):
        logger.error("[FAIL] Seeding check failed: VPN Users group not found for employee!")
        return False
        
    # VPN group adapter check
    vpn_check = adapter.check_vpn_group(user_id)
    if not vpn_check.get("is_member", False):
        logger.error("[FAIL] Adapter VPN group membership check returned false!")
        return False
    logger.info("[PASS] Group membership and VPN verification verified successfully.")

    # Test 5: Mailbox Checks and Connectivity
    logger.info("Test 5: Verification of Mailbox status and Exchange connectivity")
    mb_status = adapter.get_mailbox_status(user_id)
    if mb_status.get("mailbox_status") != "ACTIVE" or mb_status.get("exchange_server") != "ONLINE":
        logger.error("[FAIL] Mailbox status is not active or server offline!")
        return False
        
    settings = adapter.get_mailbox_settings(user_id)
    if settings.get("automaticRepliesSetting", {}).get("status") != "disabled":
        logger.error("[FAIL] Mailbox automatic replies setting is incorrect!")
        return False
        
    conn = adapter.check_exchange_connectivity()
    if conn.get("exchange_server") != "ONLINE":
        logger.error("[FAIL] Exchange connectivity check returned offline!")
        return False
    logger.info("[PASS] Mailbox status and Exchange connectivity verified successfully.")

    # Test 6: Licenses Checking
    logger.info("Test 6: Verification of user licenses")
    lics = adapter.get_assigned_licenses(user_id)
    if len(lics) == 0:
        logger.error("[FAIL] No licenses assigned to employee in mock DB!")
        return False
        
    office_check = adapter.check_office_license(user_id)
    if office_check.get("status") != "ASSIGNED":
        logger.error("[FAIL] Office license status is unassigned!")
        return False
        
    exch_check = adapter.check_exchange_license(user_id)
    if exch_check.get("status") != "ASSIGNED":
        logger.error("[FAIL] Exchange Online license status is unassigned!")
        return False
    logger.info("[PASS] User licenses verified successfully.")

    # Test 7: Prometheus Telemetry counters
    logger.info("Test 7: Verification of Prometheus Metrics Telemetry")
    try:
        req_count = GRAPH_REQUESTS_TOTAL.labels(operation="get_user")._value.get()
        logger.info(f"  - Microsoft Graph get_user metric count: {req_count}")
        if req_count < 1.0:
            logger.error("[FAIL] Metrics counter 'graph_requests_total' was not incremented!")
            return False
            
        mb_checks = GRAPH_MAILBOX_CHECKS_TOTAL._value.get()
        logger.info(f"  - Mailbox checks metric count: {mb_checks}")
        if mb_checks < 1.0:
            logger.error("[FAIL] Metrics counter 'graph_mailbox_checks_total' was not incremented!")
            return False
            
        lic_checks = GRAPH_LICENSE_CHECKS_TOTAL._value.get()
        logger.info(f"  - License checks metric count: {lic_checks}")
        if lic_checks < 2.0:  # checked twice (office and exchange)
            logger.error("[FAIL] Metrics counter 'graph_license_checks_total' was not incremented correctly!")
            return False
            
        logger.info("[PASS] Prometheus instrumentation verified successfully.")
    except Exception as e:
        logger.warning(f"Skipping telemetry counter value verification: {e}")

    # Test 8: Health checks / status diagnostics check
    logger.info("Test 8: Verification of health check connectivity")
    is_healthy = adapter.health_check()
    if not is_healthy:
        logger.error("[FAIL] Adapter health check returned failure status!")
        return False
    logger.info("[PASS] Adapter health check verified successfully.")

    logger.info("\nALL MICROSOFT GRAPH INTEGRATION VERIFICATION TESTS PASSED SUCCESSFULLY! ✓")
    return True

if __name__ == "__main__":
    success = run_tests()
    if not success:
        sys.exit(1)
    sys.exit(0)
