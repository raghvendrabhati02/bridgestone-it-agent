import subprocess
import time
import requests
import sys

def main():
    print("Starting FastAPI backend...")
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

        # --- SCENARIO 1 ---
        print("\n--- SCENARIO 1: VPN query -> ASK_MORE_INFO; 'still not working' -> CREATE_TICKET ---")
        
        # Step 1.1: Initial VPN Query
        res1_1 = requests.post(
            "http://127.0.0.1:8000/chat",
            json={"message": "My VPN is not connecting"},
            headers=headers
        )
        if res1_1.status_code != 200:
            print(f"FAILED Scenario 1 Step 1: status code {res1_1.status_code}")
            all_passed = False
            return
            
        data1_1 = res1_1.json()
        print("Response 1.1 payload:", data1_1)
        
        session_id1 = data1_1.get("session_id")
        action1_1 = data1_1.get("action")
        ticket_created1_1 = data1_1.get("ticket_created")
        
        if not session_id1:
            print("FAILED Scenario 1 Step 1: No session_id returned")
            all_passed = False
        if action1_1 != "ASK_MORE_INFO":
            print(f"FAILED Scenario 1 Step 1: Expected action ASK_MORE_INFO, got {action1_1}")
            all_passed = False
        if ticket_created1_1:
            print("FAILED Scenario 1 Step 1: ticket_created should be False")
            all_passed = False
            
        if not all_passed:
            return

        # Step 1.2: Follow up with override keyword "still not working"
        # Note: Since this matches override keywords, no Gemini API call is triggered, avoiding rate limit delays.
        res1_2 = requests.post(
            "http://127.0.0.1:8000/chat",
            json={"message": "still not working", "session_id": session_id1},
            headers=headers
        )
        if res1_2.status_code != 200:
            print(f"FAILED Scenario 1 Step 2: status code {res1_2.status_code}")
            all_passed = False
            return
            
        data1_2 = res1_2.json()
        print("Response 1.2 payload:", data1_2)
        
        action1_2 = data1_2.get("action")
        ticket_created1_2 = data1_2.get("ticket_created")
        
        if action1_2 != "CREATE_TICKET":
            print(f"FAILED Scenario 1 Step 2: Expected action CREATE_TICKET, got {action1_2}")
            all_passed = False
        if not ticket_created1_2:
            print("FAILED Scenario 1 Step 2: Expected ticket_created to be True")
            all_passed = False
            
        if not all_passed:
            return
            
        print("Scenario 1 Passed!")

        # Sleep to avoid rate limits on the next scenario's initial request
        print("Sleeping 15 seconds to respect Gemini API rate limits...")
        time.sleep(15)

        # --- SCENARIO 2 ---
        print("\n--- SCENARIO 2: VPN query -> ASK_MORE_INFO; 'create a support ticket' -> CREATE_TICKET ---")
        
        # Step 2.1: Initial VPN Query
        res2_1 = requests.post(
            "http://127.0.0.1:8000/chat",
            json={"message": "I am having issues with the VPN"},
            headers=headers
        )
        if res2_1.status_code != 200:
            print(f"FAILED Scenario 2 Step 1: status code {res2_1.status_code}")
            all_passed = False
            return
            
        data2_1 = res2_1.json()
        print("Response 2.1 payload:", data2_1)
        
        session_id2 = data2_1.get("session_id")
        action2_1 = data2_1.get("action")
        ticket_created2_1 = data2_1.get("ticket_created")
        
        if not session_id2:
            print("FAILED Scenario 2 Step 1: No session_id returned")
            all_passed = False
        if action2_1 != "ASK_MORE_INFO":
            print(f"FAILED Scenario 2 Step 1: Expected action ASK_MORE_INFO, got {action2_1}")
            all_passed = False
        if ticket_created2_1:
            print("FAILED Scenario 2 Step 1: ticket_created should be False")
            all_passed = False
            
        if not all_passed:
            return

        # Step 2.2: Follow up with override keyword "create a support ticket"
        res2_2 = requests.post(
            "http://127.0.0.1:8000/chat",
            json={"message": "create a support ticket", "session_id": session_id2},
            headers=headers
        )
        if res2_2.status_code != 200:
            print(f"FAILED Scenario 2 Step 2: status code {res2_2.status_code}")
            all_passed = False
            return
            
        data2_2 = res2_2.json()
        print("Response 2.2 payload:", data2_2)
        
        action2_2 = data2_2.get("action")
        ticket_created2_2 = data2_2.get("ticket_created")
        
        if action2_2 != "CREATE_TICKET":
            print(f"FAILED Scenario 2 Step 2: Expected action CREATE_TICKET, got {action2_2}")
            all_passed = False
        if not ticket_created2_2:
            print("FAILED Scenario 2 Step 2: Expected ticket_created to be True")
            all_passed = False
            
        if not all_passed:
            return
            
        print("Scenario 2 Passed!")

        # Sleep to avoid rate limits on the next scenario's initial request
        print("Sleeping 15 seconds to respect Gemini API rate limits...")
        time.sleep(15)

        # --- SCENARIO 3 ---
        print("\n--- SCENARIO 3: VPN query -> ASK_MORE_INFO; 'resolved' -> RESOLVED ---")
        
        # Step 3.1: Initial VPN Query
        res3_1 = requests.post(
            "http://127.0.0.1:8000/chat",
            json={"message": "My VPN keeps dropping"},
            headers=headers
        )
        if res3_1.status_code != 200:
            print(f"FAILED Scenario 3 Step 1: status code {res3_1.status_code}")
            all_passed = False
            return
            
        data3_1 = res3_1.json()
        print("Response 3.1 payload:", data3_1)
        
        session_id3 = data3_1.get("session_id")
        action3_1 = data3_1.get("action")
        ticket_created3_1 = data3_1.get("ticket_created")
        
        if not session_id3:
            print("FAILED Scenario 3 Step 1: No session_id returned")
            all_passed = False
        if action3_1 != "ASK_MORE_INFO":
            print(f"FAILED Scenario 3 Step 1: Expected action ASK_MORE_INFO, got {action3_1}")
            all_passed = False
        if ticket_created3_1:
            print("FAILED Scenario 3 Step 1: ticket_created should be False")
            all_passed = False
            
        if not all_passed:
            return

        # Step 3.2: Follow up with override keyword "resolved"
        res3_2 = requests.post(
            "http://127.0.0.1:8000/chat",
            json={"message": "resolved", "session_id": session_id3},
            headers=headers
        )
        if res3_2.status_code != 200:
            print(f"FAILED Scenario 3 Step 2: status code {res3_2.status_code}")
            all_passed = False
            return
            
        data3_2 = res3_2.json()
        print("Response 3.2 payload:", data3_2)
        
        action3_2 = data3_2.get("action")
        ticket_created3_2 = data3_2.get("ticket_created")
        
        if action3_2 != "RESOLVED":
            print(f"FAILED Scenario 3 Step 2: Expected action RESOLVED, got {action3_2}")
            all_passed = False
        if ticket_created3_2:
            print("FAILED Scenario 3 Step 2: ticket_created should be False")
            all_passed = False
            
        if not all_passed:
            return
            
        print("Scenario 3 Passed!")

    except Exception as e:
        print("Error during transitions verification:", e)
        all_passed = False
    finally:
        print("\nStopping FastAPI backend...")
        proc.terminate()
        proc.wait()
        
    if all_passed:
        print("\nALL TRANSITION VERIFICATIONS PASSED SUCCESSFULLY!")
        sys.exit(0)
    else:
        print("\nSOME TRANSITION VERIFICATIONS FAILED.")
        sys.exit(1)

if __name__ == "__main__":
    main()
