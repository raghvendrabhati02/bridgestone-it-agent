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

        # Step 1: Software installation
        print("\n--- STEP 1: Send 'Software installation' ---")
        res1 = requests.post(
            "http://127.0.0.1:8000/chat",
            json={"message": "Software installation"},
            headers=headers
        )
        if res1.status_code != 200:
            print(f"FAILED Step 1: status code {res1.status_code}")
            all_passed = False
            return
        data1 = res1.json()
        print("Response 1:", data1)
        session_id = data1.get("session_id")
        category = data1.get("category")
        if not session_id:
            print("FAILED Step 1: session_id is missing")
            all_passed = False
        if category != "SOFTWARE_INSTALLATION":
            print(f"FAILED Step 1: Expected category SOFTWARE_INSTALLATION, got {category}")
            all_passed = False

        if not all_passed:
            return

        # Step 2: Create ticket for Software Installation (Desktop Support Team)
        print("\n--- STEP 2: Send 'create ticket' for Software Installation ---")
        res2 = requests.post(
            "http://127.0.0.1:8000/chat",
            json={"message": "create ticket", "session_id": session_id},
            headers=headers
        )
        if res2.status_code != 200:
            print(f"FAILED Step 2: status code {res2.status_code}")
            all_passed = False
            return
        data2 = res2.json()
        print("Response 2:", data2)
        if not data2.get("ticket_created"):
            print("FAILED Step 2: ticket_created should be True")
            all_passed = False
        if data2.get("assigned_team") != "Desktop Support Team":
            print(f"FAILED Step 2: Expected assigned_team 'Desktop Support Team', got {data2.get('assigned_team')}")
            all_passed = False

        if not all_passed:
            return

        # Sleep to avoid rate limits
        print("Sleeping 10 seconds to avoid API rate limits...")
        time.sleep(10)

        # Step 3: Switch to VPN issue
        print("\n--- STEP 3: Send 'VPN not connected' ---")
        res3 = requests.post(
            "http://127.0.0.1:8000/chat",
            json={"message": "VPN not connected", "session_id": session_id},
            headers=headers
        )
        if res3.status_code != 200:
            print(f"FAILED Step 3: status code {res3.status_code}")
            all_passed = False
            return
        data3 = res3.json()
        print("Response 3:", data3)
        if data3.get("category") != "VPN":
            print(f"FAILED Step 3: Expected category VPN, got {data3.get('category')}")
            all_passed = False

        if not all_passed:
            return

        # Step 4: Create ticket for VPN (Network Team)
        print("\n--- STEP 4: Send 'create ticket' for VPN ---")
        res4 = requests.post(
            "http://127.0.0.1:8000/chat",
            json={"message": "create ticket", "session_id": session_id},
            headers=headers
        )
        if res4.status_code != 200:
            print(f"FAILED Step 4: status code {res4.status_code}")
            all_passed = False
            return
        data4 = res4.json()
        print("Response 4:", data4)
        if not data4.get("ticket_created"):
            print("FAILED Step 4: ticket_created should be True")
            all_passed = False
        if data4.get("assigned_team") != "Network Team":
            print(f"FAILED Step 4: Expected assigned_team 'Network Team', got {data4.get('assigned_team')}")
            all_passed = False

        if not all_passed:
            return

        # Sleep to avoid rate limits
        print("Sleeping 10 seconds to avoid API rate limits...")
        time.sleep(10)

        # Step 5: Switch to Outlook issue
        print("\n--- STEP 5: Send 'Outlook not opening' ---")
        res5 = requests.post(
            "http://127.0.0.1:8000/chat",
            json={"message": "Outlook not opening", "session_id": session_id},
            headers=headers
        )
        if res5.status_code != 200:
            print(f"FAILED Step 5: status code {res5.status_code}")
            all_passed = False
            return
        data5 = res5.json()
        print("Response 5:", data5)
        if data5.get("category") != "OUTLOOK":
            print(f"FAILED Step 5: Expected category OUTLOOK, got {data5.get('category')}")
            all_passed = False

        if not all_passed:
            return

        # Step 6: Create ticket for Outlook (Messaging Team)
        print("\n--- STEP 6: Send 'create ticket' for Outlook ---")
        res6 = requests.post(
            "http://127.0.0.1:8000/chat",
            json={"message": "create ticket", "session_id": session_id},
            headers=headers
        )
        if res6.status_code != 200:
            print(f"FAILED Step 6: status code {res6.status_code}")
            all_passed = False
            return
        data6 = res6.json()
        print("Response 6:", data6)
        if not data6.get("ticket_created"):
            print("FAILED Step 6: ticket_created should be True")
            all_passed = False
        if data6.get("assigned_team") != "Messaging Team":
            print(f"FAILED Step 6: Expected assigned_team 'Messaging Team', got {data6.get('assigned_team')}")
            all_passed = False

        if not all_passed:
            return

        # Sleep to avoid rate limits
        print("Sleeping 10 seconds to avoid API rate limits...")
        time.sleep(10)

        # Step 7: Switch to Network issue
        print("\n--- STEP 7: Send 'Wifi not connected' ---")
        res7 = requests.post(
            "http://127.0.0.1:8000/chat",
            json={"message": "Wifi not connected", "session_id": session_id},
            headers=headers
        )
        if res7.status_code != 200:
            print(f"FAILED Step 7: status code {res7.status_code}")
            all_passed = False
            return
        data7 = res7.json()
        print("Response 7:", data7)
        if data7.get("category") != "NETWORK":
            print(f"FAILED Step 7: Expected category NETWORK, got {data7.get('category')}")
            all_passed = False

        if not all_passed:
            return

        # Step 8: Create ticket for Network (Network Team)
        print("\n--- STEP 8: Send 'create ticket' for Network ---")
        res8 = requests.post(
            "http://127.0.0.1:8000/chat",
            json={"message": "create ticket", "session_id": session_id},
            headers=headers
        )
        if res8.status_code != 200:
            print(f"FAILED Step 8: status code {res8.status_code}")
            all_passed = False
            return
        data8 = res8.json()
        print("Response 8:", data8)
        if not data8.get("ticket_created"):
            print("FAILED Step 8: ticket_created should be True")
            all_passed = False
        if data8.get("assigned_team") != "Network Team":
            print(f"FAILED Step 8: Expected assigned_team 'Network Team', got {data8.get('assigned_team')}")
            all_passed = False

    except Exception as e:
        print("Error during category switching verification:", e)
        all_passed = False
    finally:
        print("\nStopping FastAPI backend...")
        proc.terminate()
        proc.wait()
        
    if all_passed:
        print("\nALL CATEGORY SWITCHING VERIFICATIONS PASSED SUCCESSFULLY!")
        sys.exit(0)
    else:
        print("\nSOME CATEGORY SWITCHING VERIFICATIONS FAILED.")
        sys.exit(1)

if __name__ == "__main__":
    main()
