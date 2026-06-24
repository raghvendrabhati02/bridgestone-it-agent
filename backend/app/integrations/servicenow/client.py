import os
import requests
from requests.auth import HTTPBasicAuth
import logging

from .servicenow_client import ServiceNowClientInterface, ServiceNowMockClient

logger = logging.getLogger("it-agent-backend")

class ServiceNowRealClient(ServiceNowClientInterface):
    is_mock = False
    
    def __init__(self, instance_url: str = None, username: str = None, password: str = None, client_id: str = None, client_secret: str = None):
        self.instance_url = (instance_url or "").rstrip("/")
        self.username = username
        self.password = password
        self.client_id = client_id
        self.client_secret = client_secret
        self._cached_token = None

    def _get_headers(self) -> dict:
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json"
        }
        if self.client_id and self.client_secret:
            token = self._get_oauth_token()
            if token:
                headers["Authorization"] = f"Bearer {token}"
                return headers
        return headers

    def _get_oauth_token(self) -> str | None:
        if self._cached_token:
            return self._cached_token
            
        try:
            url = f"{self.instance_url}/oauth_token.do"
            payload = {
                "grant_type": "password",
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "username": self.username,
                "password": self.password
            }
            response = requests.post(url, data=payload, timeout=5.0)
            if response.status_code == 200:
                data = response.json()
                self._cached_token = data.get("access_token")
                logger.info("ServiceNow OAuth: Retrieved OAuth access token successfully")
                return self._cached_token
            else:
                logger.warning("ServiceNow OAuth: Failed status %d, falling back to Basic Auth", response.status_code)
        except Exception as e:
            logger.error("ServiceNow OAuth: Exception during OAuth token acquisition: %s", e)
            
        return None

    def _request(self, method: str, url: str, **kwargs) -> requests.Response:
        headers = kwargs.get("headers", {})
        if "Authorization" not in headers and self.username and self.password:
            kwargs["auth"] = HTTPBasicAuth(self.username, self.password)
        kwargs["timeout"] = kwargs.get("timeout", 10.0)
        return requests.request(method, url, **kwargs)

    def check_connectivity(self) -> dict:
        """
        Runs API connection health verification test.
        """
        import time
        url = f"{self.instance_url}/api/now/table/incident?sysparm_limit=1"
        headers = self._get_headers()
        start_time = time.time()
        try:
            response = self._request("GET", url, headers=headers, timeout=5.0)
            duration = time.time() - start_time
            if response.status_code == 200:
                return {
                    "status": "healthy",
                    "latency": duration,
                    "details": "Authentication and API connectivity verified."
                }
            else:
                return {
                    "status": "unhealthy",
                    "latency": duration,
                    "details": f"API error response {response.status_code}"
                }
        except Exception as e:
            duration = time.time() - start_time
            return {
                "status": "unhealthy",
                "latency": duration,
                "details": f"Network exception: {str(e)}"
            }

    # Incident API delegations
    def create_incident(self, category: str, description: str, assignment_group: str) -> dict:
        from .incidents import create_incident as _create
        return _create(self, category, description, assignment_group)

    def get_incident(self, sys_id: str) -> dict:
        from .incidents import get_incident as _get
        return _get(self, sys_id)

    def update_incident(self, sys_id: str, updates: dict) -> dict:
        from .incidents import update_incident as _update
        return _update(self, sys_id, updates)

    def close_incident(self, sys_id: str) -> dict:
        from .incidents import close_incident as _close
        return _close(self, sys_id)

    # Request API delegations
    def create_request(self, category: str, description: str, action_type: str) -> dict:
        from .requests import create_service_request as _create_req
        return _create_req(self, category, description, action_type)

    def get_request(self, sys_id: str) -> dict:
        from .requests import get_request_status as _get_req
        return _get_req(self, sys_id)

    def update_request(self, sys_id: str, updates: dict) -> dict:
        from .requests import update_request as _update_req
        return _update_req(self, sys_id, updates)

    def get_all_incidents(self) -> list:
        from .incidents import get_all_incidents as _get_all
        return _get_all(self)

    def get_all_requests(self) -> list:
        from .requests import get_all_requests as _get_all_req
        return _get_all_req(self)
