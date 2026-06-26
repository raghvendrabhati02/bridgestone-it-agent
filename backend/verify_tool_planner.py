import os
import sys
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("it-agent-backend")

# Ensure app is in path
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from app.agents.multi_step_planner_agent import MultiStepPlannerAgent

def run_tests():
    logger.info("=== Starting MultiStepPlannerAgent Verification ===")
    planner = MultiStepPlannerAgent()

    tests_run = 0
    tests_passed = 0

    # Test 1: Category VPN, empty tool chain -> Should plan "VPN"
    tests_run += 1
    next_step = planner.plan_next_step("VPN", [], [], "My VPN is not connecting")
    if next_step == "VPN":
        logger.info("[PASS] Test 1: Empty chain VPN category -> VPN")
        tests_passed += 1
    else:
        logger.error("[FAIL] Test 1: Expected VPN, got %s", next_step)

    # Test 2: Category VPN, VPN tools ran and gateway online + access active -> Should plan "NETWORK"
    tests_run += 1
    chain_active = [
        {
            "tool_name": "vpn_tools",
            "status": "SUCCESS",
            "data": {
                "vpn_gateway": "ONLINE",
                "user_access": "ACTIVE",
                "latency_ms": 25,
                "status": "ONLINE"
            }
        }
    ]
    next_step = planner.plan_next_step("VPN", chain_active, [], "VPN is not working")
    if next_step == "NETWORK":
        logger.info("[PASS] Test 2: VPN healthy -> NETWORK")
        tests_passed += 1
    else:
        logger.error("[FAIL] Test 2: Expected NETWORK, got %s", next_step)

    # Test 3: Category VPN, VPN tools ran and user access is DISABLED -> Should plan None (stop)
    tests_run += 1
    chain_disabled = [
        {
            "tool_name": "vpn_tools",
            "status": "SUCCESS",
            "data": {
                "vpn_gateway": "ONLINE",
                "user_access": "DISABLED",
                "latency_ms": 25,
                "status": "ONLINE"
            }
        }
    ]
    next_step = planner.plan_next_step("VPN", chain_disabled, [], "VPN reset please")
    if next_step is None:
        logger.info("[PASS] Test 3: VPN disabled -> stop (None)")
        tests_passed += 1
    else:
        logger.error("[FAIL] Test 3: Expected None, got %s", next_step)

    # Test 4: Category OUTLOOK, Outlook tools ran, exchange ONLINE, mailbox ACTIVE -> Should plan "NETWORK"
    tests_run += 1
    chain_outlook = [
        {
            "tool_name": "outlook_tools",
            "status": "SUCCESS",
            "data": {
                "mailbox_status": "ACTIVE",
                "exchange_server": "ONLINE",
                "exchange_latency": 15
            }
        }
    ]
    next_step = planner.plan_next_step("OUTLOOK", chain_outlook, [], "Outlook is not loading")
    if next_step == "NETWORK":
        logger.info("[PASS] Test 4: Outlook healthy -> NETWORK")
        tests_passed += 1
    else:
        logger.error("[FAIL] Test 4: Expected NETWORK, got %s", next_step)

    # Test 5: Category OUTLOOK, Outlook + Network tools ran -> Should plan None (stop)
    tests_run += 1
    chain_outlook_net = [
        {
            "tool_name": "outlook_tools",
            "status": "SUCCESS",
            "data": {
                "mailbox_status": "ACTIVE",
                "exchange_server": "ONLINE",
                "exchange_latency": 15
            }
        },
        {
            "tool_name": "network_tools",
            "status": "SUCCESS",
            "data": {
                "network_status": "ONLINE",
                "wifi_status": "ONLINE",
                "packet_loss": 0
            }
        }
    ]
    next_step = planner.plan_next_step("OUTLOOK", chain_outlook_net, [], "Outlook is failing")
    if next_step is None:
        logger.info("[PASS] Test 5: Outlook + Network ran -> stop (None)")
        tests_passed += 1
    else:
        logger.error("[FAIL] Test 5: Expected None, got %s", next_step)

    logger.info("=== MultiStepPlannerAgent Verification Complete ===")
    logger.info("Passed %d/%d tests.", tests_passed, tests_run)
    sys.exit(0 if tests_passed == tests_run else 1)

if __name__ == "__main__":
    run_tests()
