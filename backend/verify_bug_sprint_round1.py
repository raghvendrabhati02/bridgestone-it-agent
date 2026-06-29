# verify_bug_sprint_round1.py
# Master orchestrator for Phase A Bug Fix Round 1 QA.

import os
import sys

# Set testing environment variable
os.environ["TESTING"] = "True"
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "app")))

def run_round1_sprint_tests():
    print("==================================================")
    print("Executing Phase A - Enterprise Bug Fix Sprint Round 1")
    print("==================================================")
    
    # Import and run each new test suite
    from verify_database_integrity import test_database_integrity
    from verify_notifications import test_notifications
    from verify_dashboard_consistency import test_dashboard_consistency
    from verify_persistence import test_persistence_flow
    
    test_database_integrity()
    test_notifications()
    test_dashboard_consistency()
    test_persistence_flow()
    
    print("\n==================================================")
    print("[PASS] verify_bug_sprint_round1: All sprint tests succeeded!")
    print("==================================================")

if __name__ == "__main__":
    run_round1_sprint_tests()
