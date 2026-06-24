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
        print("\n--- TURN 1: Initial Query ---")
        res1 = requests.post(
            "http://127.0.0.1:8000/chat",
            json={"message": "VPN not working"}
        )
        if res1.status_code != 200:
            print(f"FAILED Turn 1: status code {res1.status_code}")
            all_passed = False
            return
            
        data1 = res1.json()
        print("Response payload:", data1)
        
        session_id = data1.get("session_id")
        category = data1.get("category")
        source = data1.get("source")
        history_length = data1.get("history_length")
        question1 = data1.get("question")
        
        if not session_id:
            print("FAILED Turn 1: No session_id returned")
            all_passed = False
        if category != "VPN":
            print(f"FAILED Turn 1: Mismapped category (expected VPN, got {category})")
            all_passed = False
        if source != "vpn_guide.txt":
            print(f"FAILED Turn 1: Mismapped source (expected vpn_guide.txt, got {source})")
            all_passed = False
        if history_length != 2:
            print(f"FAILED Turn 1: Expected history_length to be 2, got {history_length}")
            all_passed = False
            
        if not all_passed:
            return

        print("Turn 1 Passed!")
        
        # Sleep to avoid hitting per-minute rate limit
        print("Sleeping 15 seconds to respect Gemini API rate limits...")
        time.sleep(15)

        print("\n--- TURN 2: Responding to Agent's question ---")
        res2 = requests.post(
            "http://127.0.0.1:8000/chat",
            json={"message": "Yes, I have a stable internet connection.", "session_id": session_id}
        )
        if res2.status_code != 200:
            print(f"FAILED Turn 2: status code {res2.status_code}")
            all_passed = False
            return
            
        data2 = res2.json()
        print("Response payload:", data2)
        
        history_length2 = data2.get("history_length")
        response2 = data2.get("response")
        
        if history_length2 != 4:
            print(f"FAILED Turn 2: Expected history_length to be 4, got {history_length2}")
            all_passed = False
        if not response2:
            print("FAILED Turn 2: No response returned")
            all_passed = False
            
        print("Turn 2 Passed!")
        
        # Sleep to avoid hitting per-minute rate limit
        print("Sleeping 15 seconds to respect Gemini API rate limits...")
        time.sleep(15)

        print("\n--- TURN 3: Continuing the conversation ---")
        res3 = requests.post(
            "http://127.0.0.1:8000/chat",
            json={"message": "I am using Cisco AnyConnect client.", "session_id": session_id}
        )
        if res3.status_code != 200:
            print(f"FAILED Turn 3: status code {res3.status_code}")
            all_passed = False
            return
            
        data3 = res3.json()
        print("Response payload:", data3)
        
        history_length3 = data3.get("history_length")
        response3 = data3.get("response")
        
        if history_length3 != 6:
            print(f"FAILED Turn 3: Expected history_length to be 6, got {history_length3}")
            all_passed = False
        if not response3:
            print("FAILED Turn 3: No response returned")
            all_passed = False
            
        print("Turn 3 Passed!")

    except Exception as e:
        print("Error during memory verification:", e)
        all_passed = False
    finally:
        print("\nStopping FastAPI backend...")
        proc.terminate()
        proc.wait()
        
    if all_passed:
        print("\nALL MEMORY VERIFICATIONS PASSED SUCCESSFULLY!")
        sys.exit(0)
    else:
        print("\nSOME MEMORY VERIFICATIONS FAILED.")
        sys.exit(1)

if __name__ == "__main__":
    main()
