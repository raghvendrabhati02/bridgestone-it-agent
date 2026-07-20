import os
import requests
from dotenv import load_dotenv

def test_api():
    load_dotenv()
    api_key = "AIzaSyDUMMYKEY12345"

    url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"
    payload = {
        "contents": [{"parts": [{"text": "Hello"}]}]
    }

    # Case 1: Query parameter ?key=...
    print("--- Testing Case 1: Query Parameter ?key=... ---")
    try:
        r = requests.post(f"{url}?key={api_key}", json=payload)
        print(f"Status Code: {r.status_code}")
        print(f"Response: {r.text[:300]}")
    except Exception as e:
        print(f"Error: {e}")

    # Case 2: Header x-goog-api-key
    print("\n--- Testing Case 2: Header x-goog-api-key ---")
    try:
        r = requests.post(url, json=payload, headers={"x-goog-api-key": api_key})
        print(f"Status Code: {r.status_code}")
        print(f"Response: {r.text[:300]}")
    except Exception as e:
        print(f"Error: {e}")

    # Case 3: Header Authorization: Bearer
    print("\n--- Testing Case 3: Header Authorization: Bearer ---")
    try:
        r = requests.post(url, json=payload, headers={"Authorization": f"Bearer {api_key}"})
        print(f"Status Code: {r.status_code}")
        print(f"Response: {r.text[:300]}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_api()
