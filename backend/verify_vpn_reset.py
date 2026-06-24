import sys
import os
import json
import urllib.request
import urllib.error

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

def run():
    print("Testing 'Reset my VPN access'...")
    res = post_chat("Reset my VPN access")
    print("Response Turn 1:")
    print(json.dumps(res, indent=2))
    
    session_id = res.get("session_id")
    if session_id:
        print("\nTesting 'APPROVE'...")
        res2 = post_chat("APPROVE", session_id=session_id)
        print("Response Turn 2:")
        print(json.dumps(res2, indent=2))

if __name__ == "__main__":
    run()
