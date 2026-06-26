import os
import sys
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("it-agent-backend")

# Ensure app is in path
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from app.graph.graph import app_graph

def run_tests():
    logger.info("=== Starting E2E AI Copilot Graph Verification ===")

    tests_run = 0
    tests_passed = 0

    # 1. Turn 1: User says VPN is down, but doesn't give enough context
    tests_run += 1
    state_1 = {
        "session_id": "test_e2e_copilot_123",
        "user_message": "My VPN is down",
        "category": "VPN",
        "active_issue": "",
        "active_ticket": "",
        "active_request": "",
        "conversation_goal": "",
        "last_action": "",
        "knowledge_context": "",
        "tool_result": {},
        "plan": {},
        "root_cause_analysis": None,
        "reflection": None,
        "memory": None,
        "decision": "",
        "decision_response": "",
        "route": "intent",  # Route directly to troubleshoot pipeline
        "ticket": {},
        "assigned_team": "",
        "notifications": [],
        "sla": {},
        "approval_required": False,
        "approval_status": "PENDING",
        "recommended_action": "",
        "action_result": None,
        "username": "employee_username",
        "user_role": "EMPLOYEE",
        "diagnostic_interview": None,
        "tool_chain": [],
        "hypothesis_tracker": [],
        "engineer_summary": None,
        "troubleshooting_iterations": 0,
        "troubleshooting_complete": False,
        "next_tool": None
    }

    logger.info("Invoking graph for Turn 1: 'My VPN is down'...")
    res_1 = app_graph.invoke(state_1)

    interview = res_1.get("diagnostic_interview")
    response_text = res_1.get("decision_response")
    
    if interview and interview.get("status") == "pending" and len(interview.get("questions", [])) > 0 and response_text:
        logger.info("[PASS] Turn 1 successfully triggered diagnostic interview")
        tests_passed += 1
    else:
        logger.error("[FAIL] Turn 1 failed. Interview state: %s, Response: %s", interview, response_text)

    # 2. Turn 2: User answers the interview questions with details suggesting reset/disabled account
    tests_run += 1
    state_2 = {
        **res_1,
        "user_message": "I get a VPN authentication error after my password reset. Connected to home Wi-Fi."
    }

    logger.info("Invoking graph for Turn 2: answering the questions...")
    res_2 = app_graph.invoke(state_2)

    tool_chain = res_2.get("tool_chain", [])
    hypotheses = res_2.get("hypothesis_tracker", [])
    complete = res_2.get("troubleshooting_complete", False)
    summary = res_2.get("engineer_summary")

    logger.info("Turn 2 outputs:")
    logger.info(" - Troubleshooting complete: %s", complete)
    logger.info(" - Tool chain length: %d", len(tool_chain))
    logger.info(" - Hypotheses count: %d", len(hypotheses))
    logger.info(" - Engineer summary: %s", summary[:100].replace('\n', ' ') if summary else None)

    # Check that VPN tools executed, hypotheses tracked, summary generated
    has_vpn_tool = any(t.get("tool_name") == "vpn_tools" for t in tool_chain)
    has_confirmed_hyp = any(h.get("status") == "CONFIRMED" for h in hypotheses)

    if complete and has_vpn_tool and has_confirmed_hyp and summary:
        logger.info("[PASS] Turn 2 successfully completed troubleshooting with vpn_tools, hypothesis tracking, and engineer summary")
        tests_passed += 1
    else:
        logger.error("[FAIL] Turn 2 failed. Complete: %s, Has VPN Tool: %s, Has Confirmed Hyp: %s, Summary Present: %s",
                     complete, has_vpn_tool, has_confirmed_hyp, bool(summary))

    logger.info("=== E2E AI Copilot Graph Verification Complete ===")
    logger.info("Passed %d/%d tests.", tests_passed, tests_run)
    sys.exit(0 if tests_passed == tests_run else 1)

if __name__ == "__main__":
    run_tests()
