import os
import sys
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("it-agent-backend")

# Ensure app is in path
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from app.agents.hypothesis_tracker_agent import HypothesisTrackerAgent
from app.agents.engineer_summary_agent import EngineerSummaryAgent

def run_tests():
    logger.info("=== Starting HypothesisTrackerAgent & EngineerSummaryAgent Verification ===")
    
    tracker = HypothesisTrackerAgent()
    summary_agent = EngineerSummaryAgent()
    
    tests_run = 0
    tests_passed = 0

    # Test 1: Hypothesis tracking for VPN Disabled User
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
    hypotheses = tracker._update_rule_based("VPN", chain_disabled)
    
    # Check if we have a CONFIRMED user access disabled hypothesis
    confirmed_disabled = any(
        h.get("status") == "CONFIRMED" and "disabled" in h.get("hypothesis").lower()
        for h in hypotheses
    )
    if confirmed_disabled:
        logger.info("[PASS] Test 1: VPN Disabled account confirmed in hypotheses")
        tests_passed += 1
    else:
        logger.error("[FAIL] Test 1: Expected CONFIRMED disabled account hypothesis, got: %s", hypotheses)

    # Test 2: Hypothesis tracking for Network Wi-Fi offline
    tests_run += 1
    chain_net_offline = [
        {
            "tool_name": "network_tools",
            "status": "SUCCESS",
            "data": {
                "network_status": "OFFLINE",
                "wifi_status": "OFFLINE",
                "packet_loss": 100
            }
        }
    ]
    hypotheses_net = tracker._update_rule_based("NETWORK", chain_net_offline)
    confirmed_offline = any(
        h.get("status") == "CONFIRMED" and ("local network" in h.get("hypothesis").lower() or "wifi" in h.get("hypothesis").lower())
        for h in hypotheses_net
    )
    if confirmed_offline:
        logger.info("[PASS] Test 2: Local network/WiFi offline confirmed in hypotheses")
        tests_passed += 1
    else:
        logger.error("[FAIL] Test 2: Expected CONFIRMED network offline hypothesis, got: %s", hypotheses_net)

    # Test 3: Fallback Engineer Summary compilation for VPN Disabled
    tests_run += 1
    summary = summary_agent._generate_fallback("VPN", chain_disabled, hypotheses, "VPN reset please")
    
    if "## IT Diagnostic Report — VPN Issue" in summary and "VPN_ACCESS_RESTORATION" in summary and "disabled" in summary.lower():
        logger.info("[PASS] Test 3: Markdown Engineer Report formatted correctly")
        tests_passed += 1
    else:
        logger.error("[FAIL] Test 3: Markdown report check failed. Summary: %s", summary)

    logger.info("=== Hypothesis & Summary Verification Complete ===")
    logger.info("Passed %d/%d tests.", tests_passed, tests_run)
    sys.exit(0 if tests_passed == tests_run else 1)

if __name__ == "__main__":
    run_tests()
