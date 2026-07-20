import os
import requests
from dotenv import load_dotenv

def test_connection():
    load_dotenv()
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("Error: GEMINI_API_KEY is not defined in backend/.env.")
        return

    print(f"Loaded API key with prefix: {api_key[:6]}...")
    url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"
    
    print(f"Sending POST request to: {url}")
    payload = {
        "contents": [{"parts": [{"text": "Hello, respond with 'SUCCESS' if you hear me."}]}]
    }
    
    try:
        response = requests.post(f"{url}?key={api_key}", json=payload)
        print(f"Status Code: {response.status_code}")
        if response.status_code == 200:
            print("API Key Authentication: SUCCESS!")
            print(f"Response: {response.json()['candidates'][0]['content']['parts'][0]['text'].strip()}")
        else:
            print("API Key Authentication: FAILED.")
            print(f"Response Body: {response.text}")
    except Exception as e:
        print(f"Request failed: {e}")

if __name__ == "__main__":
    test_connection()
