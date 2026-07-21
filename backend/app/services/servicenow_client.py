"""
servicenow_client.py
─────────────────────────────────────────────────────────────────────────────
ServiceNow REST Table API client. Handles authentication, retries, timeouts,
assignment group payload modes, and ensures credentials are never exposed in logs.
"""

from __future__ import annotations

import logging
import os
import traceback
from typing import Optional, Dict, Any
import requests
from requests.auth import HTTPBasicAuth
from requests.adapters import HTTPAdapter
from urllib3.util import Retry

from app.services.servicenow_exceptions import (
    ServiceNowException,
    ServiceNowConnectionError,
    ServiceNowTimeoutError,
    ServiceNowHTTPError,
    ServiceNowAuthError,
    ServiceNowAPIError,
)
from app.models.servicenow_models import extract_sn_field

logger = logging.getLogger("it-agent-backend")


class ServiceNowClient:
    """REST API client for ServiceNow Table API."""

    def __init__(
        self,
        instance: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        table: Optional[str] = None,
        timeout: Optional[float] = None,
        auth_type: Optional[str] = None,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        assignment_group_mode: Optional[str] = None,
    ) -> None:
        self.instance = instance or os.getenv("SERVICENOW_INSTANCE_URL") or os.getenv("SERVICENOW_INSTANCE", "")
        self.username = username or os.getenv("SERVICENOW_USERNAME", "")
        self.password = password or os.getenv("SERVICENOW_PASSWORD", "")
        self.auth_type = (auth_type or os.getenv("SERVICENOW_AUTH_TYPE", "basic")).strip().lower()
        self.client_id = client_id or os.getenv("SERVICENOW_CLIENT_ID", "")
        self.client_secret = client_secret or os.getenv("SERVICENOW_CLIENT_SECRET", "")
        self.table = table or os.getenv("SERVICENOW_TABLE", "incident")
        self.assignment_group_mode = (
            assignment_group_mode
            or os.getenv("SERVICENOW_ASSIGNMENT_GROUP_MODE", "name")
        ).strip().lower()

        # Read mock mode configuration
        self.use_mock = os.getenv("USE_MOCK_SERVICENOW", "false").lower() == "true"
        if self.use_mock:
            logger.info("ServiceNowClient: Mock mode enabled (USE_MOCK_SERVICENOW=true)")
        else:
            logger.info("ServiceNowClient: Real API mode enabled (auth_type=%s, assignment_group_mode=%s)", self.auth_type, self.assignment_group_mode)

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
        if self.auth_type == "basic" and self.username and self.password:
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

    def is_configured(self) -> bool:
        """Return True if required configuration fields are set."""
        if not self.base_url:
            return False
        if self.auth_type == "basic":
            return bool(self.username and self.password)
        elif self.auth_type == "oauth":
            return bool(self.client_id and self.client_secret) or bool(self.username and self.password)
        return False

    def _get_auth_headers(self) -> dict:
        """
        Construct authentication headers.
        Clean extension point for OAuth Bearer token injection in future implementations.
        """
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        if self.auth_type == "oauth":
            # Extension point for OAuth Bearer token header injection
            token = os.getenv("SERVICENOW_OAUTH_TOKEN", "")
            if token:
                headers["Authorization"] = f"Bearer {token}"
        return headers

    def _format_assignment_group(self, group_identifier: str) -> Any:
        """Format assignment group according to configured mode (name vs sys_id)."""
        if self.assignment_group_mode == "sys_id":
            return group_identifier
        return group_identifier

    def _execute_request(self, method: str, url: str, **kwargs) -> requests.Response:
        """Perform request with support for GET, POST, PUT, PATCH and mapped HTTP status exceptions."""
        if "timeout" not in kwargs:
            kwargs["timeout"] = self.default_timeout
        if "headers" not in kwargs:
            kwargs["headers"] = self._get_auth_headers()

        # Log method + URL + payload (mask password in URL if present)
        safe_url = url
        if self.password and self.password in safe_url:
            safe_url = safe_url.replace(self.password, "********")

        logger.info(
            ">>> ENTRY [ServiceNowClient._execute_request]: %s %s (timeout=%.1fs)",
            method.upper(),
            safe_url,
            kwargs.get("timeout", self.default_timeout),
        )

        # Log the JSON payload if present (mask nothing — passwords are in headers, not body)
        if "json" in kwargs:
            payload_preview = kwargs["json"]
            logger.info(
                "[ServiceNowClient._execute_request]: Request JSON payload: %s",
                payload_preview,
            )

        try:
            method_lower = method.lower()
            if method_lower == "get":
                response = self.session.get(url, **kwargs)
            elif method_lower == "post":
                response = self.session.post(url, **kwargs)
            elif method_lower == "put":
                response = self.session.put(url, **kwargs)
            elif method_lower == "patch":
                response = self.session.patch(url, **kwargs)
            else:
                response = self.session.request(method, url, **kwargs)

            status_code = response.status_code
            # Always log HTTP status + first 2000 chars of response body
            try:
                body_preview = response.text[:2000]
            except Exception:
                body_preview = "<unreadable>"
            logger.info(
                "[ServiceNowClient._execute_request]: HTTP %d response from %s \n  Body: %s",
                status_code,
                safe_url,
                body_preview,
            )

            if status_code not in (200, 201):
                msg = f"HTTP Error {status_code}"
                try:
                    err_json = response.json()
                    if "error" in err_json:
                        err_detail = err_json['error']
                        if isinstance(err_detail, dict):
                            msg += f" - {err_detail.get('message', '')}"
                        elif isinstance(err_detail, str):
                            msg += f" - {err_detail}"
                except Exception:
                    pass

                # Status code mapping
                if status_code in (401, 403):
                    logger.error("[ServiceNowClient._execute_request]: Authentication failure (HTTP %d) — URL: %s", status_code, safe_url)
                    raise ServiceNowAuthError(status_code, msg)
                elif status_code == 400:
                    logger.error("[ServiceNowClient._execute_request]: Bad Request (HTTP 400) — %s", msg)
                    raise ServiceNowHTTPError(400, f"Bad Request: {msg}")
                elif status_code == 404:
                    logger.error("[ServiceNowClient._execute_request]: Resource Not Found (HTTP 404) — %s", msg)
                    raise ServiceNowHTTPError(404, f"Resource Not Found: {msg}")
                elif status_code == 409:
                    logger.error("[ServiceNowClient._execute_request]: Conflict (HTTP 409) — %s", msg)
                    raise ServiceNowHTTPError(409, f"Conflict: {msg}")
                elif status_code == 429:
                    logger.error("[ServiceNowClient._execute_request]: Rate limit exceeded (HTTP 429) — %s", msg)
                    raise ServiceNowHTTPError(429, f"Rate limit exceeded: {msg}")
                elif status_code in (500, 502, 503):
                    logger.error("[ServiceNowClient._execute_request]: Server Error (HTTP %d) — %s", status_code, msg)
                    raise ServiceNowHTTPError(status_code, f"Server Error: {msg}")
                else:
                    logger.error("[ServiceNowClient._execute_request]: HTTP Error %d — %s", status_code, msg)
                    raise ServiceNowHTTPError(status_code, msg)

            return response

        except requests.exceptions.Timeout as e:
            logger.error(
                "!!! TIMEOUT [ServiceNowClient._execute_request]: Request to '%s' timed out (timeout=%.1fs)\n%s",
                safe_url,
                kwargs.get("timeout", self.default_timeout),
                traceback.format_exc(),
            )
            raise ServiceNowTimeoutError("Request timed out") from e
        except requests.exceptions.ConnectionError as e:
            err_msg = str(e)
            if self.password and self.password in err_msg:
                err_msg = err_msg.replace(self.password, "********")
            logger.error(
                "!!! CONNECTION ERROR [ServiceNowClient._execute_request]: Cannot reach '%s'\n  Error: %s\n%s",
                safe_url,
                err_msg,
                traceback.format_exc(),
            )
            raise ServiceNowConnectionError(f"Connection failed: {err_msg}") from e
        except requests.exceptions.RequestException as e:
            err_msg = str(e)
            if self.password and self.password in err_msg:
                err_msg = err_msg.replace(self.password, "********")
            logger.error(
                "!!! REQUEST EXCEPTION [ServiceNowClient._execute_request]: %s\n%s",
                err_msg,
                traceback.format_exc(),
            )
            raise ServiceNowConnectionError(f"Connection failed: {err_msg}") from e

    def _safe_request(self, method: str, url: str, **kwargs) -> Dict[str, Any]:
        """Perform request safely returning structured result dictionary."""
        logger.info(
            ">>> ENTRY [ServiceNowClient._safe_request]: %s %s",
            method.upper(),
            url,
        )
        try:
            response = self._execute_request(method, url, **kwargs)
            data = response.json()
            result = data.get("result", {})

            logger.info(
                "[ServiceNowClient._safe_request]: Parsed result keys: %s",
                list(result.keys()) if isinstance(result, dict) else type(result).__name__,
            )

            sys_id = ""
            number = ""
            state = ""

            if isinstance(result, dict):
                # Use extract_sn_field() rather than str() so that reference
                # fields returned as link-value objects
                # (e.g. {"value": "INC001", "display_value": "INC001"})
                # are unwrapped correctly instead of producing a Python repr
                # string that would fail downstream INC-number checks.
                sys_id = extract_sn_field(result, "sys_id")
                number = extract_sn_field(result, "number")
                state  = extract_sn_field(result, "state")

            ret = {
                "success": True,
                "ticket_id": number,
                "number": number,
                "sys_id": sys_id,
                "state": state,
                "message": "Request completed successfully",
                "result": result
            }
            logger.info(
                "<<< EXIT [ServiceNowClient._safe_request]: success=True, number=%s, sys_id=%s",
                number,
                sys_id,
            )
            return ret
        except ValueError as e:
            logger.error(
                "!!! EXCEPTION [ServiceNowClient._safe_request]: Invalid JSON response from %s\n%s",
                url,
                traceback.format_exc(),
            )
            return {
                "success": False,
                "ticket_id": "",
                "number": "",
                "sys_id": "",
                "state": "",
                "message": "Invalid JSON response from ServiceNow"
            }
        except ServiceNowAuthError as e:
            logger.error(
                "!!! AUTH ERROR [ServiceNowClient._safe_request]: %s\n%s",
                e.message,
                traceback.format_exc(),
            )
            return {
                "success": False,
                "ticket_id": "",
                "number": "",
                "sys_id": "",
                "state": "",
                "message": f"Authentication failed: {e.message}"
            }
        except ServiceNowHTTPError as e:
            logger.error(
                "!!! HTTP ERROR [ServiceNowClient._safe_request]: %s\n%s",
                e.message,
                traceback.format_exc(),
            )
            return {
                "success": False,
                "ticket_id": "",
                "number": "",
                "sys_id": "",
                "state": "",
                "message": f"API request failed: {e.message}"
            }
        except ServiceNowTimeoutError as e:
            logger.error(
                "!!! TIMEOUT [ServiceNowClient._safe_request]: Request to %s timed out\n%s",
                url,
                traceback.format_exc(),
            )
            return {
                "success": False,
                "ticket_id": "",
                "number": "",
                "sys_id": "",
                "state": "",
                "message": "Request timed out"
            }
        except ServiceNowException as e:
            logger.error(
                "!!! SERVICENOW EXCEPTION [ServiceNowClient._safe_request]: %s\n%s",
                e,
                traceback.format_exc(),
            )
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
        caller_id: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Create a new incident in ServiceNow including caller_id when provided."""
        logger.info(">>> ENTRY [ServiceNowClient.create_incident]")

        desc = description or kwargs.get("description", "")
        cat = category or kwargs.get("category", "")
        short_desc = short_description or kwargs.get("short_description") or f"{cat} Issue"
        caller = caller_id or kwargs.get("caller_id")
        assignment_group = kwargs.get("assignment_group", "IT Support")

        logger.info(
            "[ServiceNowClient.create_incident]: use_mock=%s, base_url='%s', table='%s'",
            self.use_mock,
            self.base_url,
            self.table,
        )

        if self.use_mock:
            from app.integrations.servicenow.servicenow_mock import servicenow_mock_db
            mock_incident = servicenow_mock_db.create(
                category=cat,
                description=desc,
                assignment_group=assignment_group
            )
            mock_incident["short_description"] = short_desc
            mock_incident["severity"] = severity
            if caller:
                mock_incident["caller_id"] = caller
            logger.info("[ServiceNowClient.create_incident]: Mock incident created (number=%s)", mock_incident["number"])
            return {
                "success": True,
                "ticket_id": mock_incident["number"],
                "number": mock_incident["number"],
                "sys_id": mock_incident["sys_id"],
                "state": "1",
                "caller_id": caller,
                "message": "Mock incident created successfully",
                "result": mock_incident
            }

        if not self.base_url:
            logger.error(
                "!!! [ServiceNowClient.create_incident]: base_url is empty! "
                "SERVICENOW_INSTANCE_URL env var is not set or not resolved. "
                "instance='%s'",
                self.instance,
            )
            return {
                "success": False,
                "ticket_id": "",
                "number": "",
                "sys_id": "",
                "state": "",
                "message": "ServiceNow instance URL is not configured."
            }

        url = f"{self.base_url}/api/now/table/{self.table}"
        payload: Dict[str, Any] = {
            "short_description": short_desc,
            "description": desc,
            "category": cat,
            "severity": severity,
        }

        if caller:
            payload["caller_id"] = caller

        if "assignment_group" in kwargs and kwargs["assignment_group"]:
            payload["assignment_group"] = self._format_assignment_group(kwargs["assignment_group"])

        logger.info(
            "[ServiceNowClient.create_incident]: About to POST to URL: %s",
            url,
        )
        logger.info(
            "[ServiceNowClient.create_incident]: JSON payload: %s",
            payload,
        )

        res = self._safe_request("POST", url, json=payload)
        logger.info(
            "<<< EXIT [ServiceNowClient.create_incident]: success=%s, number=%s, sys_id=%s, message='%s'",
            res.get("success"),
            res.get("number"),
            res.get("sys_id"),
            res.get("message"),
        )
        return res

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
        return self._safe_request("GET", url)

    def update_incident(self, sys_id: str, data: dict, use_patch: bool = True) -> Dict[str, Any]:
        """Update incident details by sys_id using PATCH for partial updates by default."""
        logger.info("ServiceNowClient: Incident update started for sys_id=%s", sys_id)
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
            logger.info("ServiceNowClient: Incident update completed (Mock sys_id=%s)", sys_id)
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
        method = "PATCH" if use_patch else "PUT"
        res = self._safe_request(method, url, json=data)
        if res.get("success"):
            logger.info("ServiceNowClient: Incident update completed for sys_id=%s", sys_id)
        return res

    def close_incident(self, sys_id: str, close_notes: str) -> Dict[str, Any]:
        """Close incident by sys_id."""
        payload = {
            "state": "7",
            "close_notes": close_notes,
            "close_code": "Closed/Resolved by IT Agent",
        }
        return self.update_incident(sys_id, payload, use_patch=True)

    def add_work_note(self, sys_id: str, work_note: str) -> Dict[str, Any]:
        """Add a work note to an incident."""
        logger.info("ServiceNowClient: Work note added to sys_id=%s", sys_id)
        payload = {
            "work_notes": work_note
        }
        return self.update_incident(sys_id, payload, use_patch=True)
