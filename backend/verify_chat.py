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
    
    test_cases = [
        ("VPN not working", "vpn_guide.txt", "VPN"),
        ("Outlook not opening", "outlook_guide.txt", "OUTLOOK"),
        ("Cannot connect to printer", "printer_guide.txt", "PRINTER"),
        ("Need password reset", "password_reset_guide.txt", "PASSWORD_RESET"),
    ]
    
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

        for i, (query, expected_source, expected_category) in enumerate(test_cases):
            if i > 0:
                print("Sleeping 15 seconds to respect Gemini API rate limits...")
                time.sleep(15)
            print(f"\nSending query: '{query}'")
            res = requests.post(
                "http://127.0.0.1:8000/chat",
                json={"message": query},
                headers=headers
            )
            if res.status_code != 200:
                print(f"FAILED: status code {res.status_code}")
                all_passed = False
                continue
            
            data = res.json()
            print("Response:", data)
            
            category = data.get("category")
            source = data.get("source")
            context_used = data.get("context_used")
            response = data.get("response")
            
            if category != expected_category:
                print(f"FAILED: Expected category '{expected_category}', got '{category}'")
                all_passed = False
            elif source != expected_source:
                print(f"FAILED: Expected source '{expected_source}', got '{source}'")
                all_passed = False
            elif not context_used:
                print("FAILED: Expected context_used to be True")
                all_passed = False
            elif not response:
                print("FAILED: Expected a non-empty response")
                all_passed = False
            else:
                print("PASSED!")
                
    except Exception as e:
        print("Error during requests:", e)
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
    main()
