import requests
import time
import sys

def run_tests():
    print("Connecting to running FastAPI backend on http://127.0.0.1:8000...")
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

        # --- SCENARIO 1: VPN Access Disabled -> RECOMMEND_ACTION ---
        print("\n--- SCENARIO 1: VPN Access Disabled ---")
        payload1 = {"message": "VPN not working, access is disabled for me"}
        print(f"Sending message: {payload1['message']}")
        res1 = requests.post("http://127.0.0.1:8000/chat", json=payload1, headers=headers)
        if res1.status_code != 200:
            print(f"FAILED: Status code {res1.status_code}")
            all_passed = False
        else:
            data1 = res1.json()
            print("Response Payload:")
            print(data1)
            
            # Validations
            category = data1.get("category")
            action = data1.get("action")
            response = data1.get("response")
            tool_result = data1.get("tool_result")
            
            if category != "VPN":
                print(f"FAILED: Expected category VPN, got {category}")
                all_passed = False
            if action != "WAIT_FOR_APPROVAL":
                print(f"FAILED: Expected action WAIT_FOR_APPROVAL, got {action}")
                all_passed = False
            if "disabled" not in response.lower() or "restoration" not in response.lower():
                print(f"FAILED: Unexpected response message (missing key info 'disabled'/'restoration'): '{response}'")
                all_passed = False
            if not tool_result or tool_result.get("tool_name") != "vpn_tools":
                print(f"FAILED: Expected tool_result for vpn_tools, got {tool_result}")
                all_passed = False
            else:
                inner_data = tool_result.get("data", {})
                if inner_data.get("user_access") != "DISABLED":
                    print(f"FAILED: Expected user_access to be DISABLED, got {inner_data.get('user_access')}")
                    all_passed = False
                    
            if all_passed:
                print("Scenario 1 PASSED!")
                
        # Sleep briefly to avoid Gemini rate limits
        print("Sleeping 10 seconds to avoid Gemini rate limits...")
        time.sleep(10)

        # --- SCENARIO 2: Outlook Not Opening ---
        print("\n--- SCENARIO 2: Outlook Not Opening ---")
        payload2 = {"message": "Outlook is not opening"}
        print(f"Sending message: {payload2['message']}")
        res2 = requests.post("http://127.0.0.1:8000/chat", json=payload2, headers=headers)
        if res2.status_code != 200:
            print(f"FAILED: Status code {res2.status_code}")
            all_passed = False
        else:
            data2 = res2.json()
            print("Response Payload:")
            print(data2)
            
            category = data2.get("category")
            tool_result = data2.get("tool_result")
            
            if category != "OUTLOOK":
                print(f"FAILED: Expected category OUTLOOK, got {category}")
                all_passed = False
            if not tool_result or tool_result.get("tool_name") != "outlook_tools":
                print(f"FAILED: Expected tool_result for outlook_tools, got {tool_result}")
                all_passed = False
            else:
                inner_data = tool_result.get("data", {})
                if inner_data.get("mailbox_status") != "ACTIVE" or inner_data.get("exchange_server") != "ONLINE":
                    print(f"FAILED: Unexpected tool data: {inner_data}")
                    all_passed = False
                    
            if all_passed:
                print("Scenario 2 PASSED!")
                
        # Sleep briefly to avoid Gemini rate limits
        print("Sleeping 10 seconds to avoid Gemini rate limits...")
        time.sleep(10)

        # --- SCENARIO 3: Cannot Install Chrome ---
        print("\n--- SCENARIO 3: Cannot Install Chrome ---")
        payload3 = {"message": "unable to install software Chrome"}
        print(f"Sending message: {payload3['message']}")
        res3 = requests.post("http://127.0.0.1:8000/chat", json=payload3, headers=headers)
        if res3.status_code != 200:
            print(f"FAILED: Status code {res3.status_code}")
            all_passed = False
        else:
            data3 = res3.json()
            print("Response Payload:")
            print(data3)
            
            category = data3.get("category")
            tool_result = data3.get("tool_result")
            
            if category != "SOFTWARE_INSTALLATION":
                print(f"FAILED: Expected category SOFTWARE_INSTALLATION, got {category}")
                all_passed = False
            if not tool_result or tool_result.get("tool_name") != "software_tools":
                print(f"FAILED: Expected tool_result for software_tools, got {tool_result}")
                all_passed = False
            else:
                inner_data = tool_result.get("data", {})
                if inner_data.get("software") != "Chrome" or inner_data.get("approved") is not True:
                    print(f"FAILED: Unexpected software status: {inner_data}")
                    all_passed = False
                    
            if all_passed:
                print("Scenario 3 PASSED!")

    except Exception as e:
        print(f"FAILED: Exception occurred: {e}")
        all_passed = False
        
    if all_passed:
        print("\nALL TOOL EXECUTION LAYER VERIFICATIONS PASSED SUCCESSFULLY!")
        sys.exit(0)
    else:
        print("\nSOME VERIFICATIONS FAILED.")
        sys.exit(1)

if __name__ == "__main__":
    run_tests()
