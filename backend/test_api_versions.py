import os
import requests
from dotenv import load_dotenv

def test():
    load_dotenv()
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("No GEMINI_API_KEY found.")
        return

    payload = {
        "contents": [{"parts": [{"text": "Hello"}]}]
    }

    # Test v1beta
    url_beta = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"
    print("--- Testing v1beta API ---")
    try:
        r = requests.post(f"{url_beta}?key={api_key}", json=payload)
        print(f"v1beta Status Code: {r.status_code}")
        print(f"v1beta Response: {r.text[:300]}")
    except Exception as e:
        print(f"v1beta Error: {e}")

    # Test v1
    url_v1 = "https://generativelanguage.googleapis.com/v1/models/gemini-2.5-flash:generateContent"
    print("\n--- Testing v1 API ---")
    try:
        r = requests.post(f"{url_v1}?key={api_key}", json=payload)
        print(f"v1 Status Code: {r.status_code}")
        print(f"v1 Response: {r.text[:300]}")
    except Exception as e:
        print(f"v1 Error: {e}")

if __name__ == "__main__":
    test()
