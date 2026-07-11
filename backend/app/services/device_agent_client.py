import os
import requests
import logging
import time

logger = logging.getLogger("it-agent-backend")

class DeviceAgentClient:
    def __init__(self):
        self.base_url = os.getenv("DEVICE_AGENT_URL", "http://localhost:8001").rstrip("/")
        self.api_key = os.getenv("DEVICE_AGENT_API_KEY", "dev_api_key_test_9083")
        self.timeout = 10.0  # 10 seconds timeout
        self.retries = 3     # 3 retries
        self.retry_delay = 2.0  # 2 second delay

    def _get_headers(self):
        return {
            "X-API-Key": self.api_key,
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

    def _request(self, method: str, path: str, json_data: dict = None) -> dict:
        url = f"{self.base_url}{path}"
        headers = self._get_headers()
        
        attempts = 1 + self.retries
        for attempt in range(attempts):
            try:
                # Log request
                logger.info("[DeviceAgentClient] Request: %s %s | Headers: %s | Body: %s", method, url, headers, json_data)
                
                if method.upper() == "GET":
                    response = requests.get(url, headers=headers, timeout=self.timeout)
                elif method.upper() == "POST":
                    response = requests.post(url, headers=headers, json=json_data, timeout=self.timeout)
                else:
                    raise ValueError(f"Unsupported method: {method}")
                
                # Log response
                logger.info("[DeviceAgentClient] Response: Status=%s | Body=%s", response.status_code, response.text)
                
                if response.status_code == 200:
                    data = response.json()
                    if isinstance(data, dict):
                        data["connected"] = True
                    return data
                else:
                    logger.warning("[DeviceAgentClient] Request failed with status code %s (Attempt %s/%s)", response.status_code, attempt + 1, attempts)
            except Exception as e:
                logger.error("[DeviceAgentClient] Request exception: %s (Attempt %s/%s)", e, attempt + 1, attempts)
            
            if attempt < self.retries:
                logger.info("[DeviceAgentClient] Waiting %s seconds before retry...", self.retry_delay)
                time.sleep(self.retry_delay)
                
        # If all retries failed, return offline response without raising exceptions
        return {
            "connected": False,
            "message": "Enterprise Device Agent Offline"
        }

    def health(self) -> dict:
        return self._request("GET", "/health")

    def system_info(self) -> dict:
        return self._request("GET", "/system-info")

    def history(self) -> dict:
        return self._request("GET", "/history")

    def execute(self, action: str, parameters: dict = None) -> dict:
        if parameters is None:
            parameters = {}
        return self._request("POST", "/action", {"action": action, "parameters": parameters})
