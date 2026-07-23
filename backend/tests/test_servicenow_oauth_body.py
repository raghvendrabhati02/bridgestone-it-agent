from pathlib import Path
from dotenv import load_dotenv
import os
import requests

env_path = Path(__file__).resolve().parents[1] / ".env"
load_dotenv(env_path)

response = requests.post(
    os.getenv("SERVICENOW_TOKEN_URL"),
    headers={
        "Accept": "application/json",
        "Content-Type": "application/x-www-form-urlencoded",
    },
    data={
        "grant_type": "client_credentials",
        "client_id": os.getenv("SERVICENOW_CLIENT_ID"),
        "client_secret": os.getenv("SERVICENOW_CLIENT_SECRET"),
    },
    timeout=30,
)

print(response.status_code)
print(response.text)