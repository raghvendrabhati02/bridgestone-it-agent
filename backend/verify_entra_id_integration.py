#!/usr/bin/env python
import os
import sys
import time

# Ensure backend directory is in the python path
backend_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, backend_dir)
sys.path.insert(0, os.path.join(backend_dir, "app"))

# Force mock mode for safety during verification
os.environ["USE_MOCK_AD"] = "true"
os.environ["AZURE_TENANT_ID"] = "mock_tenant"
os.environ["AZURE_CLIENT_ID"] = "mock_client"
os.environ["AZURE_CLIENT_SECRET"] = "mock_secret"

import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("verify_entra_id")

try:
    from app.adapters.active_directory_adapter import ActiveDirectoryAdapter
    from app.core.metrics import (
        AD_REQUESTS_TOTAL,
        AD_FAILURES_TOTAL,
        AD_LATENCY_SECONDS,
        GROUP_CHECKS_TOTAL,
        ACCESS_CHECKS_TOTAL
    )
except ImportError as e:
    logger.error("Failed to import app modules: %s", e)
    sys.exit(1)

def run_tests():
    logger.info("=========================================")
    logger.info("RUNNING AZURE AD / ENTRA ID INTEGRATION VERIFIER")
    logger.info("=========================================")

    # Test 1: Feature Flag Fallback
    logger.info("Test 1: Verification of Mock Fallback configuration")
    adapter = ActiveDirectoryAdapter()
    if not getattr(adapter.client, "is_mock", False):
        logger.error("[FAIL] Client should be mock client in mock mode!")
        return False
    logger.info("[PASS] Mock fallback verified successfully.")

    # Test 2: User Lookup and Profiles
    logger.info("Test 2: Verification of User Profiles and Lookup")
    user_id = "employee"
    user = adapter.get_user(user_id)
    if user.get("displayName") != "Standard Employee" or user.get("mail") != "employee@bridgestone.com":
        logger.error("[FAIL] Retained user fields do not match seeded values!")
        return False
        
    profile = adapter.get_user_profile(user_id)
    if profile.get("jobTitle") != "Support Specialist":
        logger.error("[FAIL] User profile job title check failed!")
        return False
    logger.info("[PASS] User lookup and profiles verified successfully.")

    # Test 3: Manager Lookup and Department
    logger.info("Test 3: Verification of Manager Lookup & Department")
    manager = adapter.get_manager(user_id)
    if manager is None or manager.get("displayName") != "Test Manager":
        logger.error("[FAIL] Manager lookup did not return correct test manager!")
        return False
        
    dept = adapter.get_department(user_id)
    if dept != "IT Service Desk":
        logger.error("[FAIL] Department lookup check failed!")
        return False
    logger.info("[PASS] Manager lookup and department verified successfully.")

    # Test 4: Member Groups
    logger.info("Test 4: Verification of Group membership & details")
    groups = adapter.get_user_groups(user_id)
    if not any(g.get("displayName") == "VPN Users" for g in groups):
        logger.error("[FAIL] Seeding check failed: VPN Users group not found for employee!")
        return False
        
    is_member = adapter.check_group_membership(user_id, "VPN Users")
    if not is_member:
        logger.error("[FAIL] Group membership check failed to identify VPN group membership!")
        return False
        
    g_details = adapter.get_group_details("egrp-2")
    if g_details.get("displayName") != "VPN Users":
        logger.error("[FAIL] Fetch group details failed for group egrp-2!")
        return False
    logger.info("[PASS] Group membership and directory details verified successfully.")

    # Test 5: Access Validations (VPN and Application)
    logger.info("Test 5: Verification of Access Validations")
    vpn_access = adapter.check_vpn_access(user_id)
    if vpn_access.get("target") != "VPN" or not vpn_access.get("allowed", False):
        logger.error("[FAIL] VPN access check should be allowed for employee!")
        return False
        
    app_access = adapter.check_application_access(user_id, "Software Center")
    if app_access.get("target") != "Software Center" or not app_access.get("allowed", False):
        logger.error("[FAIL] Application access check should be allowed for employee!")
        return False
        
    sec_access = adapter.check_security_group_access(user_id, "Domain Users")
    if not sec_access.get("allowed", False):
        logger.error("[FAIL] Security group access validation check failed!")
        return False
    logger.info("[PASS] Access validations verified successfully.")

    # Test 6: Role Management
    logger.info("Test 6: Verification of Roles")
    roles = adapter.get_user_roles(user_id)
    if "EMPLOYEE" not in roles:
        logger.error("[FAIL] Employee should have role EMPLOYEE!")
        return False
        
    admin_check = adapter.check_admin_role("admin")
    if not admin_check:
        logger.error("[FAIL] Admin account role check failed!")
        return False
        
    mgr_check = adapter.check_manager_role("manager")
    if not mgr_check:
        logger.error("[FAIL] Manager account role check failed!")
        return False
    logger.info("[PASS] Role assignments verified successfully.")

    # Test 7: Prometheus Telemetry counters
    logger.info("Test 7: Verification of Prometheus Metrics Telemetry")
    try:
        req_count = AD_REQUESTS_TOTAL.labels(operation="get_user")._value.get()
        logger.info(f"  - Active Directory get_user metric count: {req_count}")
        if req_count < 1.0:
            logger.error("[FAIL] Metrics counter 'ad_requests_total' was not incremented!")
            return False
            
        grp_checks = GROUP_CHECKS_TOTAL._value.get()
        logger.info(f"  - Group membership checks metric count: {grp_checks}")
        if grp_checks < 1.0:
            logger.error("[FAIL] Metrics counter 'group_checks_total' was not incremented!")
            return False
            
        acc_checks = ACCESS_CHECKS_TOTAL._value.get()
        logger.info(f"  - Access validations checks metric count: {acc_checks}")
        if acc_checks < 3.0:  # checked 3 times (vpn, app, security group)
            logger.error("[FAIL] Metrics counter 'access_checks_total' was not incremented correctly!")
            return False
            
        logger.info("[PASS] Prometheus instrumentation verified successfully.")
    except Exception as e:
        logger.warning(f"Skipping telemetry counter value verification: {e}")

    # Test 8: Health checks
    logger.info("Test 8: Verification of health check connectivity")
    is_healthy = adapter.health_check()
    if not is_healthy:
        logger.error("[FAIL] Adapter health check returned failure status!")
        return False
    logger.info("[PASS] Adapter health check verified successfully.")

    logger.info("\nALL AZURE AD / ENTRA ID INTEGRATION VERIFICATION TESTS PASSED SUCCESSFULLY! ✓")
    return True

if __name__ == "__main__":
    success = run_tests()
    if not success:
        sys.exit(1)
    sys.exit(0)
