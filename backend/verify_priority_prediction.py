import os
import sys
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("it-agent-backend")

# Ensure app is in path
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from app.services.sla_service import calculate_priority, calculate_sla

def run_tests():
    logger.info("=== Starting Priority & SLA Prediction Verification ===")
    
    tests_run = 0
    tests_passed = 0

    # Test 1: Server down / Outage -> CRITICAL
    tests_run += 1
    priority = calculate_priority("GENERAL", "The corporate billing server is down, we have a total outage")
    sla = calculate_sla(priority)
    if priority == "CRITICAL" and sla == 1:
        logger.info("[PASS] Test 1: Server down is CRITICAL (1h SLA)")
        tests_passed += 1
    else:
        logger.error("[FAIL] Test 1: Expected CRITICAL/1h, got %s/%dh", priority, sla)

    # Test 2: SAP issue -> HIGH
    tests_run += 1
    priority = calculate_priority("SAP", "Cannot login to SAP ERP system")
    sla = calculate_sla(priority)
    if priority == "HIGH" and sla == 4:
        logger.info("[PASS] Test 2: SAP issue is HIGH (4h SLA)")
        tests_passed += 1
    else:
        logger.error("[FAIL] Test 2: Expected HIGH/4h, got %s/%dh", priority, sla)

    # Test 3: VPN issue -> MEDIUM
    tests_run += 1
    priority = calculate_priority("VPN", "My VPN client says disconnected")
    sla = calculate_sla(priority)
    if priority == "MEDIUM" and sla == 8:
        logger.info("[PASS] Test 3: VPN issue is MEDIUM (8h SLA)")
        tests_passed += 1
    else:
        logger.error("[FAIL] Test 3: Expected MEDIUM/8h, got %s/%dh", priority, sla)

    # Test 4: Software install -> LOW
    tests_run += 1
    priority = calculate_priority("SOFTWARE_INSTALLATION", "Need Google Chrome installed")
    sla = calculate_sla(priority)
    if priority == "LOW" and sla == 24:
        logger.info("[PASS] Test 4: Software install is LOW (24h SLA)")
        tests_passed += 1
    else:
        logger.error("[FAIL] Test 4: Expected LOW/24h, got %s/%dh", priority, sla)

    logger.info("=== Priority & SLA Verification Complete ===")
    logger.info("Passed %d/%d tests.", tests_passed, tests_run)
    sys.exit(0 if tests_passed == tests_run else 1)

if __name__ == "__main__":
    run_tests()
