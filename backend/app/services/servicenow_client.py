"""
servicenow_client.py
─────────────────────────────────────────────────────────────────────────────
ServiceNow REST Table API client. Handles authentication, retries, timeouts,
and ensures that credentials are never exposed in logs.
"""

from __future__ import annotations

import logging
import os
from typing import Optional, Dict, Any
import requests
from requests.auth import HTTPBasicAuth
from requests.adapters import HTTPAdapter
from urllib3.util import Retry

logger = logging.getLogger("it-agent-backend")


# ─────────────────────────────────────────────────────────────────────────────
# Custom ServiceNow Exception Hierarchy
# ─────────────────────────────────────────────────────────────────────────────

class ServiceNowException(Exception):
    """Base exception for ServiceNow integration."""
    pass


class ServiceNowConnectionError(ServiceNowException):
    """Raised when connection to ServiceNow fails."""
    pass


class ServiceNowTimeoutError(ServiceNowException):
    """Raised when a request to ServiceNow times out."""
    pass


class ServiceNowHTTPError(ServiceNowException):
    """Raised when ServiceNow returns a non-2xx status code."""
    def __init__(self, status_code: int, message: str) -> None:
        super().__init__(f"HTTP {status_code}: {message}")
        self.status_code = status_code
        self.message = message


class ServiceNowAuthError(ServiceNowHTTPError):
    """Raised for 401/403 authorization failures."""
    pass


# ─────────────────────────────────────────────────────────────────────────────
# ServiceNow Client Class
# ─────────────────────────────────────────────────────────────────────────────

class ServiceNowClient:
    """REST API client for ServiceNow Table API."""

    def __init__(
        self,
        instance: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        table: Optional[str] = None,
        timeout: Optional[float] = None,
    ) -> None:
        self.instance = instance or os.getenv("SERVICENOW_INSTANCE", "")
        self.username = username or os.getenv("SERVICENOW_USERNAME", "")
        self.password = password or os.getenv("SERVICENOW_PASSWORD", "")
        self.table = table or os.getenv("SERVICENOW_TABLE", "incident")
        
        # Read mock mode configuration
        self.use_mock = os.getenv("USE_MOCK_SERVICENOW", "true").lower() == "true"

        # Determine configurable timeout
        if timeout is None:
            timeout_env = os.getenv("SERVICENOW_TIMEOUT")
            if timeout_env:
                try:
                    timeout = float(timeout_env)
                except ValueError:
                    timeout = 10.0
            else:
                timeout = 10.0
        self.default_timeout = timeout

        instance_clean = self.instance.strip()
        if not instance_clean:
            self.base_url = ""
        elif instance_clean.startswith("http://") or instance_clean.startswith("https://"):
            self.base_url = instance_clean.rstrip("/")
        else:
            self.base_url = f"https://{instance_clean}.service-now.com"

        self.session = requests.Session()
        if self.username and self.password:
            self.session.auth = HTTPBasicAuth(self.username, self.password)

        # Connection pooling and retries
        retries = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            raise_on_status=False,
        )
        adapter = HTTPAdapter(
            pool_connections=10,
            pool_maxsize=10,
            max_retries=retries
        )
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

    def _get_headers(self) -> dict:
        return {
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    def _execute_request(self, method: str, url: str, **kwargs) -> requests.Response:
        """Perform request and raise custom exception types based on outcomes."""
        if "timeout" not in kwargs:
            kwargs["timeout"] = self.default_timeout
        if "headers" not in kwargs:
            kwargs["headers"] = self._get_headers()

        try:
            method_lower = method.lower()
            if method_lower == "get":
                response = self.session.get(url, **kwargs)
            elif method_lower == "post":
                response = self.session.post(url, **kwargs)
            elif method_lower == "put":
                response = self.session.put(url, **kwargs)
            else:
                response = self.session.request(method, url, **kwargs)
            
            status_code = response.status_code
            if status_code not in (200, 201):
                msg = f"HTTP Error {status_code}"
                try:
                    err_json = response.json()
                    if "error" in err_json:
                        msg += f" - {err_json['error'].get('message', '')}"
                except Exception:
                    pass

                if status_code in (401, 403):
                    raise ServiceNowAuthError(status_code, msg)
                else:
                    raise ServiceNowHTTPError(status_code, msg)
            
            return response
        except requests.exceptions.Timeout as e:
            raise ServiceNowTimeoutError("Request timed out") from e
        except requests.exceptions.RequestException as e:
            err_msg = str(e)
            if self.password and self.password in err_msg:
                err_msg = err_msg.replace(self.password, "********")
            raise ServiceNowConnectionError(f"Connection failed: {err_msg}") from e

    def _safe_request(self, method: str, url: str, **kwargs) -> Dict[str, Any]:
        """Perform request safely returning structured error dictionary instead of crashing."""
        try:
            response = self._execute_request(method, url, **kwargs)
            data = response.json()
            result = data.get("result", {})
            
            sys_id = ""
            number = ""
            state = ""
            
            if isinstance(result, dict):
                sys_id = result.get("sys_id", "")
                number = result.get("number", "")
                state = result.get("state", "")
            
            return {
                "success": True,
                "ticket_id": number,
                "number": number,
                "sys_id": sys_id,
                "state": str(state),
                "message": "Request completed successfully",
                "result": result
            }
        except ValueError:
            return {
                "success": False,
                "ticket_id": "",
                "number": "",
                "sys_id": "",
                "state": "",
                "message": "Invalid JSON response from ServiceNow"
            }
        except ServiceNowAuthError as e:
            logger.error("ServiceNow Auth Error: %s", str(e))
            return {
                "success": False,
                "ticket_id": "",
                "number": "",
                "sys_id": "",
                "state": "",
                "message": f"Authentication failed: {e.message}"
            }
        except ServiceNowHTTPError as e:
            logger.error("ServiceNow HTTP Error: %s", str(e))
            return {
                "success": False,
                "ticket_id": "",
                "number": "",
                "sys_id": "",
                "state": "",
                "message": f"API request failed: {e.message}"
            }
        except ServiceNowTimeoutError as e:
            logger.error("ServiceNow Timeout: %s", str(e))
            return {
                "success": False,
                "ticket_id": "",
                "number": "",
                "sys_id": "",
                "state": "",
                "message": "Request timed out"
            }
        except ServiceNowException as e:
            logger.error("ServiceNow Exception: %s", str(e))
            return {
                "success": False,
                "ticket_id": "",
                "number": "",
                "sys_id": "",
                "state": "",
                "message": str(e)
            }

    def create_incident(
        self,
        short_description: Optional[str] = None,
        description: Optional[str] = None,
        category: Optional[str] = None,
        severity: int = 3,
        **kwargs
    ) -> Dict[str, Any]:
        """Create a new incident in ServiceNow."""
        desc = description or kwargs.get("description", "")
        cat = category or kwargs.get("category", "")
        short_desc = short_description or kwargs.get("short_description") or f"{cat} Issue"

        if self.use_mock:
            from app.integrations.servicenow.servicenow_mock import servicenow_mock_db
            assignment_group = kwargs.get("assignment_group", "IT Support")
            mock_incident = servicenow_mock_db.create(
                category=cat,
                description=desc,
                assignment_group=assignment_group
            )
            # Update short_description and severity in local mock store
            mock_incident["short_description"] = short_desc
            mock_incident["severity"] = severity
            return {
                "success": True,
                "ticket_id": mock_incident["number"],
                "number": mock_incident["number"],
                "sys_id": mock_incident["sys_id"],
                "state": "1",  # Open/New state code is '1'
                "message": "Mock incident created successfully",
                "result": mock_incident
            }

        if not self.base_url:
            return {
                "success": False,
                "ticket_id": "",
                "number": "",
                "sys_id": "",
                "state": "",
                "message": "ServiceNow instance URL is not configured."
            }

        url = f"{self.base_url}/api/now/table/{self.table}"
        payload = {
            "short_description": short_desc,
            "description": desc,
            "category": cat,
            "severity": severity,
        }
        
        if "assignment_group" in kwargs:
            payload["assignment_group"] = kwargs["assignment_group"]

        logger.info(
            "ServiceNowClient: Creating incident on %s table (category=%s)",
            self.table,
            cat,
        )
        return self._safe_request("POST", url, json=payload)

    def get_incident(self, sys_id: str) -> Dict[str, Any]:
        """Retrieve incident details by sys_id."""
        if self.use_mock:
            from app.integrations.servicenow.servicenow_mock import servicenow_mock_db
            mock_incident = servicenow_mock_db.get(sys_id)
            if not mock_incident:
                return {
                    "success": False,
                    "ticket_id": "",
                    "number": "",
                    "sys_id": "",
                    "state": "",
                    "message": f"Incident with sys_id {sys_id} not found."
                }
            return {
                "success": True,
                "ticket_id": mock_incident["number"],
                "number": mock_incident["number"],
                "sys_id": mock_incident["sys_id"],
                "state": "1" if mock_incident.get("state") == "OPEN" else "7",
                "message": "Mock incident retrieved successfully",
                "result": mock_incident
            }

        if not self.base_url:
            return {
                "success": False,
                "ticket_id": "",
                "number": "",
                "sys_id": "",
                "state": "",
                "message": "ServiceNow instance URL is not configured."
            }

        url = f"{self.base_url}/api/now/table/{self.table}/{sys_id}"
        logger.info(
            "ServiceNowClient: Getting incident with sys_id=%s from %s table",
            sys_id,
            self.table,
        )
        return self._safe_request("GET", url)

    def update_incident(self, sys_id: str, data: dict) -> Dict[str, Any]:
        """Update incident details by sys_id."""
        if self.use_mock:
            from app.integrations.servicenow.servicenow_mock import servicenow_mock_db
            mock_incident = servicenow_mock_db.update(sys_id, data)
            if not mock_incident:
                return {
                    "success": False,
                    "ticket_id": "",
                    "number": "",
                    "sys_id": "",
                    "state": "",
                    "message": f"Incident with sys_id {sys_id} not found."
                }
            return {
                "success": True,
                "ticket_id": mock_incident["number"],
                "number": mock_incident["number"],
                "sys_id": mock_incident["sys_id"],
                "state": "1" if mock_incident.get("state") == "OPEN" else "7",
                "message": "Mock incident updated successfully",
                "result": mock_incident
            }

        if not self.base_url:
            return {
                "success": False,
                "ticket_id": "",
                "number": "",
                "sys_id": "",
                "state": "",
                "message": "ServiceNow instance URL is not configured."
            }

        url = f"{self.base_url}/api/now/table/{self.table}/{sys_id}"
        logger.info(
            "ServiceNowClient: Updating incident with sys_id=%s on %s table",
            sys_id,
            self.table,
        )
        return self._safe_request("PUT", url, json=data)

    def close_incident(self, sys_id: str, close_notes: str) -> Dict[str, Any]:
        """Close incident by sys_id."""
        if self.use_mock:
            from app.integrations.servicenow.servicenow_mock import servicenow_mock_db
            mock_incident = servicenow_mock_db.close(sys_id)
            if not mock_incident:
                return {
                    "success": False,
                    "ticket_id": "",
                    "number": "",
                    "sys_id": "",
                    "state": "",
                    "message": f"Incident with sys_id {sys_id} not found."
                }
            mock_incident["close_notes"] = close_notes
            return {
                "success": True,
                "ticket_id": mock_incident["number"],
                "number": mock_incident["number"],
                "sys_id": mock_incident["sys_id"],
                "state": "7",  # Closed
                "message": "Mock incident closed successfully",
                "result": mock_incident
            }

        payload = {
            "state": "7",  # Closed state is typically '7'
            "close_notes": close_notes,
            "close_code": "Closed/Resolved by IT Agent",
        }
        return self.update_incident(sys_id, payload)

    def add_work_note(self, sys_id: str, work_note: str) -> Dict[str, Any]:
        """Add a work note to an incident."""
        if self.use_mock:
            from app.integrations.servicenow.servicenow_mock import servicenow_mock_db
            mock_incident = servicenow_mock_db.update(sys_id, {"work_notes": work_note})
            if not mock_incident:
                return {
                    "success": False,
                    "ticket_id": "",
                    "number": "",
                    "sys_id": "",
                    "state": "",
                    "message": f"Incident with sys_id {sys_id} not found."
                }
            return {
                "success": True,
                "ticket_id": mock_incident["number"],
                "number": mock_incident["number"],
                "sys_id": mock_incident["sys_id"],
                "state": "1" if mock_incident.get("state") == "OPEN" else "7",
                "message": "Mock incident work note added successfully",
                "result": mock_incident
            }

        payload = {
            "work_notes": work_note
        }
        return self.update_incident(sys_id, payload)
