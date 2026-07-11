import subprocess
import time
import requests
import sys

def main():
    print("Starting FastAPI backend...")
    import os
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--port", "8000"],
        cwd=os.path.dirname(os.path.abspath(__file__)),
        stdout=sys.stdout,
        stderr=sys.stderr
    )
    
    # Wait for uvicorn to start
    time.sleep(3)
    
    all_passed = True
    try:
        print("\n--- SCENARIO 1: Initial VPN Troubleshooting ---")
        res1 = requests.post(
            "http://127.0.0.1:8000/chat",
            json={"message": "VPN not working"}
        )
        if res1.status_code != 200:
            print(f"FAILED Scenario 1: status code {res1.status_code}")
            all_passed = False
            return
            
        data1 = res1.json()
        print("Response payload:", data1)
        
        session_id = data1.get("session_id")
        category = data1.get("category")
        action1 = data1.get("action")
        response1 = data1.get("response")
        ticket_created1 = data1.get("ticket_created")
        
        if not session_id:
            print("FAILED Scenario 1: No session_id returned")
            all_passed = False
        if category != "VPN":
            print(f"FAILED Scenario 1: Expected VPN category, got {category}")
            all_passed = False
        if action1 != "ASK_MORE_INFO":
            print(f"FAILED Scenario 1: Expected action ASK_MORE_INFO, got {action1}")
            all_passed = False
        if ticket_created1:
            print("FAILED Scenario 1: ticket_created should be False")
            all_passed = False
            
        if not all_passed:
            return

        print("Scenario 1 Passed!")
        
        # Sleep to avoid rate limits
        print("Sleeping 15 seconds to respect Gemini API rate limits...")
        time.sleep(15)

        print("\n--- SCENARIO 2: VPN Issue Resolved ---")
        res2 = requests.post(
            "http://127.0.0.1:8000/chat",
            json={"message": "VPN issue resolved"}
        )
        if res2.status_code != 200:
            print(f"FAILED Scenario 2: status code {res2.status_code}")
            all_passed = False
            return
            
        data2 = res2.json()
        print("Response payload:", data2)
        
        action2 = data2.get("action")
        response2 = data2.get("response")
        ticket_created2 = data2.get("ticket_created")
        
        if action2 != "RESOLVED":
            print(f"FAILED Scenario 2: Expected action RESOLVED, got {action2}")
            all_passed = False
        if response2 != "Glad your issue has been resolved.":
            print(f"FAILED Scenario 2: Unexpected response message: '{response2}'")
            all_passed = False
        if ticket_created2:
            print("FAILED Scenario 2: ticket_created should be False")
            all_passed = False
            
        if not all_passed:
            return

        print("Scenario 2 Passed!")
        
        # Sleep to avoid rate limits
        print("Sleeping 15 seconds to respect Gemini API rate limits...")
        time.sleep(15)

        print("\n--- SCENARIO 3: Troubleshooting Failed / Create Ticket ---")
        res3 = requests.post(
            "http://127.0.0.1:8000/chat",
            json={"message": "Tried all steps, still not working", "session_id": session_id}
        )
        if res3.status_code != 200:
            print(f"FAILED Scenario 3: status code {res3.status_code}")
            all_passed = False
            return
            
        data3 = res3.json()
        print("Response payload:", data3)
        
        action3 = data3.get("action")
        response3 = data3.get("response")
        ticket_created3 = data3.get("ticket_created")
        ticket_id3 = data3.get("ticket_id")
        
        if action3 != "CREATE_TICKET":
            print(f"FAILED Scenario 3: Expected action CREATE_TICKET, got {action3}")
            all_passed = False
        if response3 != "Troubleshooting was unsuccessful. Creating a support ticket.":
            print(f"FAILED Scenario 3: Unexpected response message: '{response3}'")
            all_passed = False
        if not ticket_created3:
            print("FAILED Scenario 3: Expected ticket_created to be True")
            all_passed = False
        if not ticket_id3 or not ticket_id3.startswith("INC"):
            print(f"FAILED Scenario 3: Expected a valid ticket ID, got {ticket_id3}")
            all_passed = False
            
        if not all_passed:
            return

        print("Scenario 3 Passed!")

    except Exception as e:
        print("Error during decision verification:", e)
        all_passed = False
    finally:
        print("\nStopping FastAPI backend...")
        proc.terminate()
        proc.wait()
        
    if all_passed:
        print("\nALL DECISION AGENT VERIFICATIONS PASSED SUCCESSFULLY!")
        sys.exit(0)
    else:
        print("\nSOME DECISION AGENT VERIFICATIONS FAILED.")
        sys.exit(1)

if __name__ == "__main__":
    main()
