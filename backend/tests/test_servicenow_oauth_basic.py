from pathlib import Path
from dotenv import load_dotenv
import os
import requests

env_path = Path(__file__).resolve().parents[1] / ".env"
load_dotenv(env_path)

TOKEN_URL = os.getenv("SERVICENOW_TOKEN_URL")
CLIENT_ID = os.getenv("SERVICENOW_CLIENT_ID")
CLIENT_SECRET = os.getenv("SERVICENOW_CLIENT_SECRET")

print("=" * 60)
print("Testing OAuth using HTTP Basic Authentication")
print("=" * 60)

print("Token URL:", TOKEN_URL)
print("Grant Type:", repr(os.getenv("SERVICENOW_GRANT_TYPE")))
print("Client ID Length:", len(CLIENT_ID))
print("Client Secret Length:", len(CLIENT_SECRET))

response = requests.post(
    TOKEN_URL,
    auth=(CLIENT_ID, CLIENT_SECRET),
    headers={
        "Accept": "application/json",
        "Content-Type": "application/x-www-form-urlencoded",
    },
    data={
        "grant_type": "client_credentials",
    },
    timeout=30,
)

print()
print("Status:", response.status_code)
print(response.text)