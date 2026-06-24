import subprocess
import time
import requests
import sys

def run_verifications():
    print("Starting FastAPI backend for ServiceNow integration verification...")
    # Start uvicorn process
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--port", "8000"],
        cwd="c:/Projects/it-agent/backend",
        stdout=sys.stdout,
        stderr=sys.stderr
    )
    
    # Wait for uvicorn to start
    time.sleep(6)
    
    all_passed = True
    try:
        # Submit a VPN query that triggers CREATE_TICKET
        print("\n--- Sending VPN query to trigger ticket creation ---")
        vpn_payload = {
            "message": "My VPN is not connecting. I tried all steps, please create a ticket.",
            "session_id": "snow-vpn-session"
        }
        res_vpn = requests.post("http://127.0.0.1:8000/chat", json=vpn_payload)
        assert res_vpn.status_code == 200, f"Failed status code: {res_vpn.status_code}"
        
        data_vpn = res_vpn.json()
        print("VPN API Response:", data_vpn)
        
        # Verify returned chat payload has ServiceNow mapping
        assert data_vpn.get("action") == "CREATE_TICKET", "Expected CREATE_TICKET action"
        assert data_vpn.get("ticket_created") is True, "Expected ticket_created to be True"
        
        servicenow_id = data_vpn.get("servicenow_id")
        assert servicenow_id is not None, "Expected a valid servicenow_id in chat response top level"
        assert servicenow_id != "N/A", "Expected servicenow_id to not be 'N/A'"
        print(f"ServiceNow ID mapping found in response: {servicenow_id}")
        
        # Verify nested ticket object also has it
        ticket_obj = data_vpn.get("ticket", {})
        assert ticket_obj.get("servicenow_id") == servicenow_id, "Expected ticket.servicenow_id to match top level"
        
        # Verify incident exists in ServiceNow Database via API GET /servicenow/incidents/{id}
        print(f"\n--- Checking GET /servicenow/incidents/{servicenow_id} endpoint ---")
        res_snow = requests.get(f"http://127.0.0.1:8000/servicenow/incidents/{servicenow_id}")
        assert res_snow.status_code == 200, f"Failed status code: {res_snow.status_code}"
        
        snow_incident = res_snow.json()
        print("ServiceNow Incident details:", snow_incident)
        assert snow_incident.get("sys_id") == servicenow_id, f"Expected sys_id {servicenow_id}, got {snow_incident.get('sys_id')}"
        assert snow_incident.get("state") == "OPEN", f"Expected state OPEN, got {snow_incident.get('state')}"
        assert snow_incident.get("assignment_group") == "Network Team", f"Expected assignment_group Network Team, got {snow_incident.get('assignment_group')}"
        print("ServiceNow Database Verification PASSED!")

        # Verify incident lists under GET /servicenow/incidents
        print("\n--- Checking GET /servicenow/incidents list endpoint ---")
        res_list = requests.get("http://127.0.0.1:8000/servicenow/incidents")
        assert res_list.status_code == 200, f"Failed status code: {res_list.status_code}"
        
        inc_list = res_list.json()
        print("ServiceNow Incidents list:", inc_list)
        assert any(inc.get("sys_id") == servicenow_id for inc in inc_list), "Expected created incident to be present in incidents list"
        print("ServiceNow Incidents List Verification PASSED!")

    except Exception as e:
        print("Verification Failed with Error:", e)
        all_passed = False
    finally:
        print("\nStopping FastAPI backend...")
        proc.terminate()
        proc.wait()

    if all_passed:
        print("\nSERVICENOW INTEGRATION VERIFICATIONS PASSED SUCCESSFULLY!")
        sys.exit(0)
    else:
        print("\nSERVICENOW INTEGRATION VERIFICATIONS FAILED.")
        sys.exit(1)

if __name__ == "__main__":
    run_verifications()
