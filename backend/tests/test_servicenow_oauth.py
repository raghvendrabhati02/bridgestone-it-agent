from pathlib import Path
from dotenv import load_dotenv
import os
import requests

env_path = Path(__file__).resolve().parents[1] / ".env"
load_dotenv(env_path)

payload = {
    "grant_type": os.getenv("SERVICENOW_GRANT_TYPE"),
    "client_id": os.getenv("SERVICENOW_CLIENT_ID"),
    "client_secret": os.getenv("SERVICENOW_CLIENT_SECRET"),
}

print("=" * 60)
print("Testing OAuth...")
print("=" * 60)
print("Token URL:", os.getenv("SERVICENOW_TOKEN_URL"))
print("Payload:")
print(payload)
response = requests.post(
    os.getenv("SERVICENOW_TOKEN_URL"),
    data=payload,
)

print("Status:", response.status_code)
print()
print(response.text)