import subprocess
import time
import requests
import sys

def run_verifications():
    print("Starting FastAPI backend for agent verification...")
    # Start uvicorn process
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--port", "8000"],
        cwd="c:/Projects/it-agent/backend",
        stdout=sys.stdout,
        stderr=sys.stderr
    )
    
    # Wait for uvicorn to start
    time.sleep(3)
    
    all_passed = True
    try:
        # Authenticate to get JWT token
        login_res = requests.post(
            "http://127.0.0.1:8000/auth/login",
            json={"username": "employee", "password": "employeepassword"}
        )
        if login_res.status_code != 200:
            print(f"Login failed: {login_res.status_code} - {login_res.text}")
            sys.exit(1)
        token = login_res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Scenario 1: VPN query -> asserts category VPN, action CREATE_TICKET, assigned team Network Team, priority MEDIUM, SLA 8 hours.
        print("\n--- Running Test Scenario 1: VPN Issue ---")
        vpn_payload = {
            "message": "My VPN is not connecting. I tried all steps, please create a ticket.",
            "session_id": "vpn-test-session"
        }
        res_vpn = requests.post("http://127.0.0.1:8000/chat", json=vpn_payload, headers=headers)
        assert res_vpn.status_code == 200, f"Failed status code: {res_vpn.status_code}"
        
        data_vpn = res_vpn.json()
        print("VPN API Response:", data_vpn)
        
        assert data_vpn.get("category") == "VPN", f"Expected category VPN, got {data_vpn.get('category')}"
        assert data_vpn.get("action") == "CREATE_TICKET", f"Expected action CREATE_TICKET, got {data_vpn.get('action')}"
        assert data_vpn.get("assigned_team") == "Network Team", f"Expected assigned_team 'Network Team', got {data_vpn.get('assigned_team')}"
        assert data_vpn.get("priority") == "MEDIUM", f"Expected priority MEDIUM, got {data_vpn.get('priority')}"
        assert data_vpn.get("sla_hours") == 8, f"Expected sla_hours 8, got {data_vpn.get('sla_hours')}"
        print("Scenario 1 PASSED!")

        # Sleep to respect rate limits
        print("Sleeping 30 seconds to respect Gemini API rate limits...")
        time.sleep(30)

        # Scenario 2: Outlook query -> asserts category OUTLOOK, assigned team Messaging Team.
        print("\n--- Running Test Scenario 2: Outlook Issue ---")
        outlook_payload = {
            "message": "Outlook is not opening. None of the steps worked, please create a ticket.",
            "session_id": "outlook-test-session"
        }
        res_outlook = requests.post("http://127.0.0.1:8000/chat", json=outlook_payload, headers=headers)
        assert res_outlook.status_code == 200, f"Failed status code: {res_outlook.status_code}"
        
        data_outlook = res_outlook.json()
        print("Outlook API Response:", data_outlook)
        
        assert data_outlook.get("category") == "OUTLOOK", f"Expected category OUTLOOK, got {data_outlook.get('category')}"
        assert data_outlook.get("action") == "CREATE_TICKET", f"Expected action CREATE_TICKET, got {data_outlook.get('action')}"
        assert data_outlook.get("assigned_team") == "Messaging Team", f"Expected assigned_team 'Messaging Team', got {data_outlook.get('assigned_team')}"
        print("Scenario 2 PASSED!")

        # Sleep to respect rate limits
        print("Sleeping 30 seconds to respect Gemini API rate limits...")
        time.sleep(30)

        # Scenario 3: SAP access query -> asserts category SAP, assigned team SAP Support Team.
        print("\n--- Running Test Scenario 3: SAP Issue ---")
        sap_payload = {
            "message": "I cannot connect to SAP. Critical issue, please create a ticket.",
            "session_id": "sap-test-session"
        }
        res_sap = requests.post("http://127.0.0.1:8000/chat", json=sap_payload, headers=headers)
        assert res_sap.status_code == 200, f"Failed status code: {res_sap.status_code}"
        
        data_sap = res_sap.json()
        print("SAP API Response:", data_sap)
        
        assert data_sap.get("category") == "SAP", f"Expected category SAP, got {data_sap.get('category')}"
        assert data_sap.get("action") == "CREATE_TICKET", f"Expected action CREATE_TICKET, got {data_sap.get('action')}"
        assert data_sap.get("assigned_team") == "SAP Support Team", f"Expected assigned_team 'SAP Support Team', got {data_sap.get('assigned_team')}"
        print("Scenario 3 PASSED!")

        # Verify SLA endpoint GET /sla
        print("\n--- Checking GET /sla endpoint ---")
        res_sla = requests.get("http://127.0.0.1:8000/sla", headers=headers)
        assert res_sla.status_code == 200, f"Failed status code: {res_sla.status_code}"
        sla_data = res_sla.json()
        print("SLA Metadata Response:", sla_data)
        assert len(sla_data) >= 3, f"Expected at least 3 tickets in SLA data, got {len(sla_data)}"
        print("/sla Endpoint Verification PASSED!")

        # Verify Notifications endpoint GET /notifications
        print("\n--- Checking GET /notifications endpoint ---")
        res_notif = requests.get("http://127.0.0.1:8000/notifications", headers=headers)
        assert res_notif.status_code == 200, f"Failed status code: {res_notif.status_code}"
        notif_data = res_notif.json()
        print("Notifications Response:", notif_data)
        assert len(notif_data) >= 6, f"Expected at least 6 notifications (2 per ticket), got {len(notif_data)}"
        print("/notifications Endpoint Verification PASSED!")

    except Exception as e:
        print("Verification Failed with Error:", e)
        all_passed = False
    finally:
        print("\nStopping FastAPI backend...")
        proc.terminate()
        proc.wait()

    if all_passed:
        print("\nALL VERIFICATIONS PASSED SUCCESSFULLY!")
        sys.exit(0)
    else:
        print("\nSOME VERIFICATIONS FAILED.")
        sys.exit(1)

if __name__ == "__main__":
    run_verifications()
