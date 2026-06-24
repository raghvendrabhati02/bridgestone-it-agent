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

def get_endpoint(path: str) -> list:
    url = f"{BASE_URL}{path}"
    req = urllib.request.Request(
        url,
        headers={"Authorization": f"Bearer {get_token()}"},
        method="GET"
    )
    try:
        with urllib.request.urlopen(req) as res:
            return json.loads(res.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        print(f"HTTP Error for {path}: {e.code} - {e.read().decode('utf-8')}")
        raise e

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
        print(f"HTTP Error on /chat: {e.code} - {e.read().decode('utf-8')}")
        raise e

def test_adapters():
    print("Testing Enterprise Adapter Layer...")
    from app.adapters.servicenow_adapter import ServiceNowAdapter
    from app.adapters.microsoft_graph_adapter import MicrosoftGraphAdapter
    from app.adapters.active_directory_adapter import ActiveDirectoryAdapter
    from app.adapters.vpn_adapter import VPNAdapter

    # Test ServiceNow Adapter
    sn = ServiceNowAdapter()
    assert sn.connect() is True
    assert sn.health_check() is True
    incident = sn.create_incident("VPN", "VPN is slow", "Network Team")
    assert incident["number"].startswith("INC")
    assert sn.disconnect() is True
    print("[OK] ServiceNow Adapter OK")

    # Test Microsoft Graph Adapter
    mg = MicrosoftGraphAdapter()
    assert mg.connect() is True
    assert mg.health_check() is True
    profile = mg.get_user_profile()
    assert profile["mail"] == "employee@bridgestone.com"
    assert mg.disconnect() is True
    print("[OK] Microsoft Graph Adapter OK")

    # Test Active Directory Adapter
    ad = ActiveDirectoryAdapter()
    assert ad.connect() is True
    assert ad.health_check() is True
    user_status = ad.check_user_access("disabled_user")
    assert user_status["status"] == "DISABLED"
    assert ad.disconnect() is True
    print("[OK] Active Directory Adapter OK")

    # Test VPN Adapter
    vpn = VPNAdapter()
    assert vpn.connect() is True
    assert vpn.health_check() is True
    gateway = vpn.check_gateway_status()
    assert gateway["vpn_gateway"] == "ONLINE"
    assert vpn.disconnect() is True
    print("[OK] VPN Adapter OK")

def test_audit_flow():
    print("\nTesting End-to-End Audit & Approval Workflow...")
    
    # 1. Trigger disabled VPN access path
    response = post_chat("VPN access disabled")
    session_id = response.get("session_id")
    print(f"Turn 1 Response (session_id={session_id}, action={response.get('action')}):")
    
    assert response.get("approval_required") is True, "Expected approval_required to be True"
    assert response.get("action") == "WAIT_FOR_APPROVAL", "Expected action to be WAIT_FOR_APPROVAL"
    
    # 2. Approve action proposal
    response2 = post_chat("yes, do it", session_id=session_id)
    print(f"Turn 2 Response (action_result={response2.get('action_result') is not None}):")
    
    assert response2.get("approval_status") == "APPROVED", "Expected APPROVED status"
    assert response2.get("action_result") is not None, "Expected Action result payload"

    # 3. Query audit endpoints to verify recordings
    print("\nVerifying database schemas and audit records...")
    
    # Audit Logs
    audit_logs = get_endpoint("/audit-logs")
    print(f"Audit log events count: {len(audit_logs)}")
    assert len(audit_logs) >= 2, "Expected at least 2 audit log events"
    assert audit_logs[-1]["session_id"] == session_id
    assert audit_logs[-1]["decision"] == "EXECUTE_ACTION"

    # Action History
    actions = get_endpoint("/actions")
    print(f"Action history entries count: {len(actions)}")
    assert len(actions) >= 1
    assert actions[-1]["approved_by_user"] is True
    assert actions[-1]["servicenow_id"].startswith("SR")

    # Approval History
    approvals = get_endpoint("/approvals")
    print(f"Approval history entries count: {len(approvals)}")
    assert len(approvals) >= 2
    session_approvals = [a for a in approvals if a["session_id"] == session_id]
    assert any(a["approval_status"] == "PENDING" for a in session_approvals)
    assert any(a["approval_status"] == "APPROVED" for a in session_approvals)

    # Agent Traces
    traces = get_endpoint("/agent-traces")
    print(f"Agent trace logs count: {len(traces)}")
    assert len(traces) >= 5, "Expected traces from intent, knowledge, tool, decision, and action nodes"
    session_traces = [t for t in traces if t["session_id"] == session_id]
    agents = [t["agent_name"] for t in session_traces]
    print(f"Agents traced in session: {set(agents)}")
    assert "Intent Agent" in agents
    assert "Knowledge Agent" in agents
    assert "Tool Agent" in agents
    assert "Decision Agent" in agents
    assert "Action Agent" in agents

    print("\n[OK] End-to-end Audit logging verified successfully!")

if __name__ == "__main__":
    test_adapters()
    test_audit_flow()
