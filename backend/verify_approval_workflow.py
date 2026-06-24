import sys
import os
import json
import urllib.request
import urllib.error

# Add backend directory to path if running directly
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "app")))

BASE_URL = "http://localhost:8000"

TOKEN = None

def get_token() -> str:
    global TOKEN
    if TOKEN is None:
        login_url = f"{BASE_URL}/auth/login"
        login_data = json.dumps({"username": "admin", "password": "adminpassword"}).encode("utf-8")
        login_req = urllib.request.Request(
            login_url,
            data=login_data,
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with urllib.request.urlopen(login_req) as res:
            TOKEN = json.loads(res.read().decode("utf-8"))["access_token"]
    return TOKEN

def post_chat(message: str, session_id: str = None) -> dict:
    url = f"{BASE_URL}/chat"
    data = json.dumps({"message": message, "session_id": session_id}).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {get_token()}"
        },
        method="POST"
    )
    try:
        with urllib.request.urlopen(req) as res:
            return json.loads(res.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        print(f"HTTP Error: {e.code} - {e.read().decode('utf-8')}")
        raise e

def get_actions() -> list:
    url = f"{BASE_URL}/actions"
    req = urllib.request.Request(
        url,
        headers={"Authorization": f"Bearer {get_token()}"},
        method="GET"
    )
    try:
        with urllib.request.urlopen(req) as res:
            return json.loads(res.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        print(f"HTTP Error: {e.code} - {e.read().decode('utf-8')}")
        raise e

def run_tests():
    print("Starting verification of the Approval/Rejection workflows...")

    # --- TEST 1: APPROVAL FLOW ---
    print("\n--- Test 1: Approval Flow ---")
    # Turn 1: Trigger VPN disabled check
    response = post_chat("VPN not working, access is disabled for me")
    session_id = response.get("session_id")
    print(f"Turn 1 Response (session_id={session_id}):")
    print(json.dumps(response, indent=2))

    assert response.get("approval_required") is True, "Expected approval_required to be True"
    assert response.get("approval_status") == "PENDING", "Expected approval_status to be PENDING"
    assert response.get("recommended_action") == "VPN_ACCESS_RESTORATION", "Expected recommended_action to be VPN_ACCESS_RESTORATION"

    # Turn 2: Approve the action
    approval_response = post_chat("yes", session_id=session_id)
    print(f"\nTurn 2 (Approval) Response:")
    print(json.dumps(approval_response, indent=2))

    assert approval_response.get("approval_status") == "APPROVED", "Expected approval_status to be APPROVED"
    action_result = approval_response.get("action_result")
    assert action_result is not None, "Expected action_result to be populated"
    assert action_result.get("status") == "OPEN", "Expected action_result status to be OPEN"
    assert action_result.get("servicenow_id").startswith("SR"), "Expected ServiceNow ID to start with SR"

    # Check action logs
    actions = get_actions()
    print(f"\nLogged actions count: {len(actions)}")
    assert any(a.get("servicenow_id") == action_result.get("servicenow_id") for a in actions), "Action not found in /actions endpoint"

    # --- TEST 2: REJECTION FLOW ---
    print("\n--- Test 2: Rejection Flow ---")
    # Turn 1: Trigger VPN disabled check in new session
    response2 = post_chat("My VPN won't connect and it says disabled")
    session_id2 = response2.get("session_id")
    print(f"Turn 1 Response (session_id={session_id2}):")
    print(json.dumps(response2, indent=2))

    assert response2.get("approval_required") is True, "Expected approval_required to be True"
    
    # Turn 2: Reject the action
    rejection_response = post_chat("no, cancel it", session_id=session_id2)
    print(f"\nTurn 2 (Rejection) Response:")
    print(json.dumps(rejection_response, indent=2))

    assert rejection_response.get("approval_status") == "REJECTED", "Expected approval_status to be REJECTED"
    assert rejection_response.get("action_result") is None, "Expected action_result to be None for rejection"

    # Confirm list actions didn't grow with a rejected record
    actions2 = get_actions()
    print(f"\nLogged actions count after rejection: {len(actions2)}")
    assert len(actions2) == len(actions), "Rejection flow should not log a completed catalog request"

    print("\nAll tests completed successfully! Approval workflow verified.")

if __name__ == "__main__":
    run_tests()
