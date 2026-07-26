"""
servicenow_client.py
─────────────────────────────────────────────────────────────────────────────
ServiceNow REST Table API client. Handles OAuth Password Grant & Refresh Token
authentication with thread-safe locking, token rotation, pre-request pipeline
checks, sanitized 401 retries, and masked credential logging.
"""

from __future__ import annotations

import logging
import os
import time
import traceback
from threading import RLock
from typing import Optional, Dict, Any
import requests
from requests.auth import HTTPBasicAuth
from requests.adapters import HTTPAdapter
from urllib3.util import Retry

from app.services.servicenow_exceptions import (
    ServiceNowException,
    ServiceNowConfigurationError,
    ServiceNowConnectionError,
    ServiceNowTimeoutError,
    ServiceNowHTTPError,
    ServiceNowAuthError,
    ServiceNowAPIError,
)
from app.models.servicenow_models import extract_sn_field
from app.core.tracing import trace_span

logger = logging.getLogger("it-agent-backend")


def _mask_secret(secret: Optional[str], visible_chars: int = 4) -> str:
    """Helper to mask sensitive credentials in logs."""
    if not secret:
        return "********"
    if len(secret) <= visible_chars:
        return "********"
    return f"{secret[:visible_chars]}***"


class ServiceNowClient:
    """REST API client for ServiceNow Table API with OAuth Password Grant & Refresh Token support."""

    TOKEN_REFRESH_BUFFER: int = 60  # Safety buffer in seconds before token expiration

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
        token_url: Optional[str] = None,
        assignment_group_mode: Optional[str] = None,
    ) -> None:
        self.instance = (
            instance
            or os.getenv("SERVICENOW_INSTANCE_URL")
            or os.getenv("SERVICENOW_INSTANCE", "")
        ).strip()
        # Read credentials strictly from arguments or environment variables (NO fallback defaults like 'admin')
        env_user = os.getenv("SERVICENOW_USERNAME")
        env_pass = os.getenv("SERVICENOW_PASSWORD")
        self.username = (username if username is not None else (env_user or "")).strip()
        self.password = (password if password is not None else (env_pass or "")).strip()

        self.credentials_from_env = bool(env_user and env_pass)
        self.fallback_used = False  # Hardcoded defaults like "admin" or "password" are forbidden

        self.auth_type = (auth_type or os.getenv("SERVICENOW_AUTH_TYPE", "basic")).strip().lower()
        self.client_id = (client_id or os.getenv("SERVICENOW_CLIENT_ID", "")).strip()
        self.client_secret = (client_secret or os.getenv("SERVICENOW_CLIENT_SECRET", "")).strip()
        self.table = table or os.getenv("SERVICENOW_TABLE", "incident")
        self.assignment_group_mode = (
            assignment_group_mode
            or os.getenv("SERVICENOW_ASSIGNMENT_GROUP_MODE", "name")
        ).strip().lower()

        # Read mock mode configuration (defaults to True if not explicitly set to false)
        self.use_mock = os.getenv("USE_MOCK_SERVICENOW", "true").lower() == "true"

        # Log startup credential diagnostics (masking password)
        logger.info(
            "[ServiceNowClient Diagnostics]: Instance='%s' | Username='%s' | AuthMode='%s' | CredentialsFromEnv=%s | FallbackUsed=%s | MockMode=%s",
            self.instance,
            self.username or "<UNSET>",
            self.auth_type,
            self.credentials_from_env,
            self.fallback_used,
            self.use_mock,
        )

        # Fail fast in Real Mode if credentials or instance URL are missing
        if not self.use_mock:
            missing = []
            if not self.instance:
                missing.append("SERVICENOW_INSTANCE_URL")
            if self.auth_type == "basic":
                if not self.username:
                    missing.append("SERVICENOW_USERNAME")
                if not self.password:
                    missing.append("SERVICENOW_PASSWORD")
            elif self.auth_type == "oauth":
                if not self.client_id:
                    missing.append("SERVICENOW_CLIENT_ID")
                if not self.client_secret:
                    missing.append("SERVICENOW_CLIENT_SECRET")
            if missing:
                raise ServiceNowConfigurationError(
                    f"Real Production ServiceNow mode requires environment variable(s): {', '.join(missing)}. "
                    "Placeholder defaults like 'admin' or 'password' are not permitted."
                )

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

        # Determine OAuth token endpoint URL
        raw_token_url = token_url or os.getenv("SERVICENOW_TOKEN_URL", "")
        if raw_token_url.strip():
            self.token_url = raw_token_url.strip()
        elif self.base_url:
            self.token_url = f"{self.base_url}/oauth_token.do"
        else:
            self.token_url = ""

        # Thread-safety lock for authentication and token refresh
        self._token_lock = RLock()

        # OAuth token state
        self.access_token: Optional[str] = None
        self.refresh_token: Optional[str] = None
        self.token_expiry: float = 0.0

        # Validate OAuth configuration early during initialization
        if not self.use_mock and self.auth_type == "oauth":
            self._validate_oauth_config()

        # Requests session initialization
        self.session = requests.Session()
        if self.auth_type == "basic" and self.username and self.password:
            self.session.auth = HTTPBasicAuth(self.username, self.password)
        else:
            self.session.auth = None

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
            max_retries=retries,
        )
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

    def _validate_oauth_config(self) -> None:
        """Validate required OAuth parameters. Raises ServiceNowAuthError if invalid."""
        missing = []
        if not self.client_id:
            missing.append("SERVICENOW_CLIENT_ID")
        if not self.client_secret:
            missing.append("SERVICENOW_CLIENT_SECRET")
        if not self.username:
            missing.append("SERVICENOW_USERNAME")
        if not self.password:
            missing.append("SERVICENOW_PASSWORD")
        if not self.token_url:
            missing.append("SERVICENOW_TOKEN_URL / SERVICENOW_INSTANCE_URL")

        if missing:
            msg = f"OAuth configuration invalid. Missing required parameter(s): {', '.join(missing)}"
            logger.error("[ServiceNowClient._validate_oauth_config]: %s", msg)
            raise ServiceNowAuthError(400, msg)

    def is_configured(self) -> bool:
        """Return True if required configuration fields are set."""
        if not self.base_url:
            return False
        if self.auth_type == "basic":
            return bool(self.username and self.password)
        elif self.auth_type == "oauth":
            return bool(
                self.client_id
                and self.client_secret
                and self.username
                and self.password
                and self.token_url
            )
        return False

    def _is_token_expired(self) -> bool:
        """Check if access token is missing or within the refresh safety buffer."""
        if not self.access_token:
            return True
        return time.time() >= (self.token_expiry - self.TOKEN_REFRESH_BUFFER)

    def authenticate(self) -> None:
        """
        Perform initial OAuth Password Grant authentication against /oauth_token.do.
        Thread-safe under self._token_lock to prevent race conditions & double authentication.
        """
        with self._token_lock:
            # Double-check inside lock to ensure concurrent requests reuse newly acquired token
            if not self._is_token_expired():
                logger.info("[ServiceNowClient.authenticate]: Valid token already acquired by another thread.")
                return

            logger.info(">>> ENTRY [ServiceNowClient.authenticate]: Requesting OAuth password grant token")
            self._validate_oauth_config()

            payload = {
                "grant_type": "password",
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "username": self.username,
                "password": self.password,
            }

            headers = {
                "Accept": "application/json",
                "Content-Type": "application/x-www-form-urlencoded",
            }

            try:
                response = self.session.post(
                    self.token_url,
                    data=payload,
                    headers=headers,
                    timeout=self.default_timeout,
                    auth=None,
                )
                status_code = response.status_code
                logger.info("[ServiceNowClient.authenticate]: HTTP %d response from token URL", status_code)

                if status_code != 200:
                    err_text = response.text[:500]
                    msg = f"OAuth authentication failed (HTTP {status_code}): {err_text}"
                    logger.error("[ServiceNowClient.authenticate]: %s", msg)
                    raise ServiceNowAuthError(status_code, msg)

                data = response.json()
                access_token = data.get("access_token")
                if not access_token:
                    msg = "OAuth response missing access_token"
                    logger.error("[ServiceNowClient.authenticate]: %s", msg)
                    raise ServiceNowAuthError(status_code, msg)

                self.access_token = access_token
                if data.get("refresh_token"):
                    self.refresh_token = data.get("refresh_token")

                expires_in = float(data.get("expires_in", 1800))
                self.token_expiry = time.time() + expires_in

                logger.info(
                    "<<< EXIT [ServiceNowClient.authenticate]: OAuth authentication successful (access_token=%s, expires in %ss)",
                    _mask_secret(self.access_token),
                    expires_in,
                )
            except ServiceNowAuthError:
                raise
            except requests.exceptions.Timeout as e:
                logger.error(
                    "!!! TIMEOUT [ServiceNowClient.authenticate]: Token request timed out\n%s",
                    traceback.format_exc(),
                )
                raise ServiceNowTimeoutError("OAuth token request timed out") from e
            except requests.exceptions.ConnectionError as e:
                logger.error(
                    "!!! CONNECTION ERROR [ServiceNowClient.authenticate]: Cannot reach token URL\n%s",
                    traceback.format_exc(),
                )
                raise ServiceNowConnectionError("OAuth token connection failed") from e
            except Exception as e:
                logger.error(
                    "!!! EXCEPTION [ServiceNowClient.authenticate]: %s\n%s",
                    e,
                    traceback.format_exc(),
                )
                raise ServiceNowAuthError(500, f"OAuth authentication error: {e}") from e

    def refresh_access_token(self) -> None:
        """
        Refresh access token using stored refresh_token against /oauth_token.do.
        Thread-safe under self._token_lock.
        Falls back to authenticate() if no refresh_token exists or if refresh fails.
        """
        with self._token_lock:
            # Double-check inside lock to ensure concurrent requests reuse newly refreshed token
            if not self._is_token_expired():
                logger.info("[ServiceNowClient.refresh_access_token]: Valid token already acquired by another thread.")
                return

            logger.info(">>> ENTRY [ServiceNowClient.refresh_access_token]")
            if not self.refresh_token:
                logger.info("[ServiceNowClient.refresh_access_token]: No refresh_token available, calling authenticate()")
                self.authenticate()
                return

            self._validate_oauth_config()

            payload = {
                "grant_type": "refresh_token",
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "refresh_token": self.refresh_token,
            }

            headers = {
                "Accept": "application/json",
                "Content-Type": "application/x-www-form-urlencoded",
            }

            try:
                response = self.session.post(
                    self.token_url,
                    data=payload,
                    headers=headers,
                    timeout=self.default_timeout,
                    auth=None,
                )
                status_code = response.status_code
                logger.info("[ServiceNowClient.refresh_access_token]: HTTP %d response from token URL", status_code)

                if status_code != 200:
                    logger.warning(
                        "[ServiceNowClient.refresh_access_token]: Refresh request failed (HTTP %d). Falling back to authenticate()...",
                        status_code,
                    )
                    self.authenticate()
                    return

                data = response.json()
                access_token = data.get("access_token")
                if not access_token:
                    logger.warning("[ServiceNowClient.refresh_access_token]: Refresh response missing access_token. Falling back to authenticate()...")
                    self.authenticate()
                    return

                self.access_token = access_token
                if data.get("refresh_token"):
                    self.refresh_token = data.get("refresh_token")

                expires_in = float(data.get("expires_in", 1800))
                self.token_expiry = time.time() + expires_in

                logger.info(
                    "<<< EXIT [ServiceNowClient.refresh_access_token]: Successfully refreshed access token (access_token=%s, expires in %ss)",
                    _mask_secret(self.access_token),
                    expires_in,
                )
            except ServiceNowAuthError:
                try:
                    self.authenticate()
                except Exception:
                    raise
            except Exception as e:
                logger.warning("[ServiceNowClient.refresh_access_token]: Token refresh failed (%s). Falling back to authenticate()...", e)
                self.authenticate()

    def ensure_authenticated(self) -> None:
        """
        Verify that a valid OAuth token exists before making an API request.
        Triggers authenticate() if missing, or refresh_access_token() if expired.
        Thread-safe double-checked locking prevents concurrent authentication calls.
        """
        if self.use_mock or self.auth_type != "oauth":
            return

        if self._is_token_expired():
            with self._token_lock:
                if self._is_token_expired():
                    if self.refresh_token:
                        logger.info("[ServiceNowClient.ensure_authenticated]: Access token expired. Refreshing token...")
                        self.refresh_access_token()
                    else:
                        logger.info("[ServiceNowClient.ensure_authenticated]: No access_token found. Authenticating...")
                        self.authenticate()

    def _get_auth_headers(self) -> dict:
        """Construct authentication headers."""
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        if self.auth_type == "oauth" and self.access_token:
            headers["Authorization"] = f"Bearer {self.access_token}"
        return headers

    def _format_assignment_group(self, group_identifier: str) -> Any:
        """Format assignment group according to configured mode (name vs sys_id)."""
        if self.assignment_group_mode == "sys_id":
            return group_identifier
        return group_identifier

    def _execute_request(self, method: str, url: str, **kwargs) -> requests.Response:
        """Perform request with support for GET, POST, PUT, PATCH, DELETE and mapped HTTP status exceptions."""
        # Fix 1 & Fix 7: Extract internal retry metadata flag so it NEVER leaks into requests kwargs
        is_auth_retry = kwargs.pop("_is_auth_retry", False)

        self.ensure_authenticated()

        if "timeout" not in kwargs:
            kwargs["timeout"] = self.default_timeout

        # Ensure authorization headers are updated
        req_headers = self._get_auth_headers()
        if "headers" in kwargs and kwargs["headers"]:
            req_headers.update(kwargs["headers"])
        kwargs["headers"] = req_headers

        # Mask password or client secret if present in URL
        safe_url = url
        if self.password and self.password in safe_url:
            safe_url = safe_url.replace(self.password, "********")
        if self.client_secret and self.client_secret in safe_url:
            safe_url = safe_url.replace(self.client_secret, "********")

        import time, json
        from app.core.logging_context import correlation_id_ctx
        t_exec_start = time.monotonic()
        corr_id = correlation_id_ctx.get() or "<none>"

        headers_to_log = dict(kwargs.get("headers") or {})
        if "Authorization" in headers_to_log:
            auth_val = str(headers_to_log["Authorization"])
            headers_to_log["Authorization"] = "Bearer ********" if auth_val.startswith("Bearer") else "Basic ********"

        json_payload_str = "<none>"
        if "json" in kwargs and kwargs["json"] is not None:
            try:
                json_payload_str = json.dumps(kwargs["json"], indent=2)
            except Exception:
                json_payload_str = str(kwargs["json"])

        logger.info(
            "\n========== SERVICENOW REQUEST ==========\n"
            "Correlation ID: %s\n"
            "Method: %s\n"
            "Complete URL: %s\n"
            "Base URL: %s\n"
            "Table: %s\n"
            "Auth Type: %s\n"
            "Use Mock: %s\n"
            "Headers: %s\n"
            "Payload:\n%s\n"
            "=======================================",
            corr_id,
            method.upper(),
            safe_url,
            self.base_url,
            self.table,
            self.auth_type,
            self.use_mock,
            headers_to_log,
            json_payload_str,
        )

        logger.info(
            ">>> ENTRY [ServiceNowClient._execute_request] | Correlation ID: %s | %s %s (timeout=%.1fs, retry=%s)",
            corr_id,
            method.upper(),
            safe_url,
            kwargs.get("timeout", self.default_timeout),
            is_auth_retry,
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
            elif method_lower == "delete":
                response = self.session.delete(url, **kwargs)
            else:
                response = self.session.request(method, url, **kwargs)

            status_code = response.status_code
            raw_body = response.text

            try:
                parsed_json = response.json()
                parsed_json_str = json.dumps(parsed_json, indent=2)
            except Exception:
                parsed_json_str = "<failed to parse JSON>"

            logger.info(
                "\n========== SERVICENOW RESPONSE ==========\n"
                "Correlation ID: %s\n"
                "HTTP Status: %d\n\n"
                "Raw Body:\n%s\n\n"
                "Parsed JSON:\n%s\n"
                "========================================",
                corr_id,
                status_code,
                raw_body,
                parsed_json_str,
            )

            exec_elapsed_ms = int((time.monotonic() - t_exec_start) * 1000)
            logger.info(
                "<<< EXIT [ServiceNowClient._execute_request] | Correlation ID: %s | Elapsed: %dms | Status: %d",
                corr_id,
                exec_elapsed_ms,
                status_code,
            )

            # Retry on 401 Unauthorized for OAuth mode (exactly once, sanitized kwargs)
            if status_code == 401 and self.auth_type == "oauth" and not is_auth_retry:
                logger.warning(
                    "[ServiceNowClient._execute_request]: Received HTTP 401 Unauthorized in OAuth mode. "
                    "Refreshing token and retrying request once..."
                )
                try:
                    # Invalidate existing token and refresh
                    self.access_token = None
                    self.refresh_access_token()
                    kwargs["headers"] = self._get_auth_headers()
                    kwargs["_is_auth_retry"] = True
                    return self._execute_request(method, url, **kwargs)
                except ServiceNowAuthError:
                    raise
                except Exception as refresh_err:
                    logger.error("!!! REFRESH ERROR [ServiceNowClient._execute_request]: Token refresh failed during 401 retry: %s", refresh_err)
                    raise ServiceNowAuthError(401, f"Authentication failed (HTTP 401): {refresh_err}") from refresh_err

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
            if self.client_secret and self.client_secret in err_msg:
                err_msg = err_msg.replace(self.client_secret, "********")
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
            if self.client_secret and self.client_secret in err_msg:
                err_msg = err_msg.replace(self.client_secret, "********")
            logger.error(
                "!!! REQUEST EXCEPTION [ServiceNowClient._execute_request]: %s\n%s",
                err_msg,
                traceback.format_exc(),
            )
            raise ServiceNowConnectionError(f"Connection failed: {err_msg}") from e

    def _safe_request(self, method: str, url: str, **kwargs) -> Dict[str, Any]:
        """Perform request safely returning structured result dictionary."""
        import time
        from app.core.logging_context import correlation_id_ctx
        t_safe_start = time.monotonic()
        corr_id = correlation_id_ctx.get() or "<none>"

        logger.info(
            ">>> ENTRY [ServiceNowClient._safe_request] | Correlation ID: %s | %s %s",
            corr_id,
            method.upper(),
            url,
        )
        try:
            response = self._execute_request(method, url, **kwargs)
            data = response.json()
            result = data.get("result", {})

            logger.info(
                "[ServiceNowClient._safe_request]: Parsed result keys: %s | Correlation ID: %s",
                list(result.keys()) if isinstance(result, dict) else type(result).__name__,
                corr_id,
            )

            sys_id = ""
            number = ""
            state = ""

            if isinstance(result, dict):
                sys_id = extract_sn_field(result, "sys_id")
                number = extract_sn_field(result, "number")
                state = extract_sn_field(result, "state")

            ret = {
                "success": True,
                "ticket_id": number,
                "number": number,
                "sys_id": sys_id,
                "state": state,
                "message": "Request completed successfully",
                "result": result,
            }
            safe_elapsed_ms = int((time.monotonic() - t_safe_start) * 1000)
            logger.info(
                "<<< EXIT [ServiceNowClient._safe_request] | Correlation ID: %s | Elapsed: %dms | success=True, number=%s, sys_id=%s",
                corr_id,
                safe_elapsed_ms,
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
                "message": "Invalid JSON response from ServiceNow",
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
                "message": f"Authentication failed: {e.message}",
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
                "message": f"API request failed: {e.message}",
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
                "message": "Request timed out",
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
                "message": str(e),
            }

    def resolve_reference(self, table_name: str, display_value: str) -> str:
        """
        Resolve a human-readable display name to a 32-character ServiceNow sys_id.
        If display_value is already a 32-char sys_id, or if resolution fails/mock mode,
        returns display_value as fallback.
        """
        if not display_value or not isinstance(display_value, str):
            return display_value
        val = display_value.strip()
        if len(val) == 32 and all(c in "0123456789abcdefABCDEF" for c in val):
            return val
        if self.use_mock or not self.base_url:
            return val
        try:
            import urllib.parse
            url = f"{self.base_url}/api/now/table/{table_name}?sysparm_query=name={urllib.parse.quote(val)}&sysparm_limit=1"
            res = self._safe_request("GET", url)
            if res.get("success"):
                result = res.get("result")
                if isinstance(result, list) and len(result) > 0:
                    found_sys_id = result[0].get("sys_id")
                    if found_sys_id:
                        logger.info("[ServiceNowClient.resolve_reference]: Resolved '%s' in %s -> %s", val, table_name, found_sys_id)
                        return found_sys_id
                elif isinstance(result, dict) and result.get("sys_id"):
                    return result.get("sys_id")
        except Exception as e:
            logger.warning("[ServiceNowClient.resolve_reference]: Reference lookup failed for '%s' in %s: %s", val, table_name, e)
        return val

    def create_incident(
        self,
        short_description: Optional[str] = None,
        description: Optional[str] = None,
        category: Optional[str] = None,
        subcategory: Optional[str] = None,
        severity: int = 3,
        caller_id: Optional[str] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """Create a new incident in ServiceNow including caller_id when provided."""
        import time
        import json
        from app.core.logging_context import correlation_id_ctx
        from app.services.servicenow_payload_inspector import ServiceNowPayloadInspector

        with trace_span(
            name="servicenow_api",
            attributes={
                "provider": "servicenow",
                "operation": "create_incident",
                "instance": getattr(self, "instance", "unknown"),
                "correlation_id": correlation_id_ctx.get() or "",
            },
        ):
            return self._create_incident_internal(
                short_description=short_description,
                description=description,
                category=category,
                subcategory=subcategory,
                severity=severity,
                caller_id=caller_id,
                **kwargs,
            )

    def _create_incident_internal(
        self,
        short_description: Optional[str] = None,
        description: Optional[str] = None,
        category: Optional[str] = None,
        subcategory: Optional[str] = None,
        severity: int = 3,
        caller_id: Optional[str] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """Internal create_incident logic extracted for trace_span wrapping."""
        import time
        import json
        from app.core.logging_context import correlation_id_ctx
        from app.services.servicenow_payload_inspector import ServiceNowPayloadInspector

        t_create_start = time.monotonic()
        corr_id = correlation_id_ctx.get() or "<none>"

        logger.info(">>> ENTRY [ServiceNowClient.create_incident] | Correlation ID: %s", corr_id)

        desc = description or kwargs.get("description", "")
        short_desc = short_description or kwargs.get("short_description") or "IT Agent Incident"

        # Rule 3 mapping keys
        raw_caller = kwargs.get("caller") or caller_id or kwargs.get("caller_id")
        raw_channel = kwargs.get("channel") or kwargs.get("contact_type") or "virtual_agent"
        raw_type = kwargs.get("type") or kwargs.get("u_type")
        raw_cat = category or kwargs.get("category", "")
        raw_subcat = subcategory or kwargs.get("subcategory")
        raw_assignment_group = kwargs.get("assignment_group") or "IT Support"

        # Resolve choices & group sys_id via ServiceNowChoiceResolver (Rules 1, 4, 5, 6, 7, 8)
        from app.services.servicenow_choice_resolver import ServiceNowChoiceResolver
        resolver = ServiceNowChoiceResolver.get_instance()

        resolved_type = resolver.resolve_type(raw_type) if raw_type else None
        resolved_cat = resolver.resolve_category(resolved_type, raw_cat) if raw_cat else None
        resolved_subcat = resolver.resolve_subcategory(resolved_cat, raw_subcat) if raw_subcat else None
        resolved_contact_type = resolver.resolve_contact_type(raw_channel)
        resolved_assignment_group = resolver.resolve_assignment_group(raw_assignment_group)

        # Diagnostics Required Logging
        subcat_exists = any(
            c["element"] == "subcategory" and c["value"] == resolved_subcat
            for c in resolver.choices
        ) if resolved_subcat else False

        dependent_cats = [
            c.get("dependent_value")
            for c in resolver.choices
            if c["element"] == "subcategory" and c["value"] == resolved_subcat
        ] if resolved_subcat else []

        # Rule 10: Validate hierarchy (u_type -> category -> subcategory) before POST
        is_valid_hierarchy, hierarchy_err = resolver.validate_hierarchy(
            u_type_val=resolved_type,
            category_val=resolved_cat,
            subcategory_val=resolved_subcat,
        )

        if not is_valid_hierarchy:
            logger.error(
                "!!! HIERARCHY VALIDATION FAILURE [ServiceNowClient.create_incident]: %s",
                hierarchy_err,
            )
            # Check if subcategory fails hierarchy check for given category
            if resolved_cat and resolved_subcat:
                sub_valid, sub_err = resolver.validate_hierarchy(None, resolved_cat, resolved_subcat)
                if not sub_valid:
                    raise ServiceNowAPIError(
                        message=f"Invalid subcategory '{resolved_subcat}' for category '{resolved_cat}': {sub_err}"
                    )

        payload: Dict[str, Any] = {
            "short_description": short_desc,
            "description": desc,
            "severity": severity,
            "assignment_group": resolved_assignment_group,  # Guaranteed 32-character sys_id
            "contact_type": resolved_contact_type,
        }

        if resolved_type:
            payload["u_type"] = resolved_type
        if resolved_cat:
            payload["category"] = resolved_cat
        if resolved_subcat:
            payload["subcategory"] = resolved_subcat
        if raw_caller:
            payload["caller_id"] = raw_caller

        logger.info("=" * 80)
        logger.info("[ServiceNowChoiceResolver Diagnostics]:")
        logger.info("Resolved Category: %s", repr(resolved_cat))
        logger.info("Resolved Subcategory: %s", repr(resolved_subcat))
        logger.info("Subcategory exists in sys_choice: %s", subcat_exists)
        logger.info("Dependent category: %s", dependent_cats)
        logger.info("Final payload:\n%s", json.dumps(payload, indent=2))
        logger.info("=" * 80)

        for extra_key in ("urgency", "impact", "priority"):
            if extra_key in kwargs and kwargs[extra_key] is not None:
                payload[extra_key] = kwargs[extra_key]

        # Resolve other reference fields to sys_id BEFORE POST
        for ref_key, tbl in (
            ("cmdb_ci", "cmdb_ci"),
            ("business_service", "cmdb_ci_service"),
            ("location", "cmn_location"),
        ):
            if ref_key in kwargs and kwargs[ref_key] is not None:
                ref_val = str(kwargs[ref_key])
                payload[ref_key] = self.resolve_reference(tbl, ref_val)

        inspector = ServiceNowPayloadInspector()
        req_summary = {
            "short_description": short_desc,
            "description": desc,
            "category": raw_cat,
            "subcategory": raw_subcat,
            "severity": severity,
            "assignment_group": raw_assignment_group,
            "caller_id": raw_caller,
            "contact_type": raw_channel,
            "impact": kwargs.get("impact"),
            "urgency": kwargs.get("urgency"),
            "priority": kwargs.get("priority"),
            "extra_fields": {k: v for k, v in kwargs.items() if k not in ("short_description", "description", "category", "severity", "assignment_group", "caller_id")},
        }
        inspector.inspect_pre_post(req_summary, payload)

        if self.use_mock:
            from app.integrations.servicenow.servicenow_mock import servicenow_mock_db
            mock_incident = servicenow_mock_db.create(
                category=payload.get("category", raw_cat),
                description=desc,
                assignment_group=payload.get("assignment_group", raw_assignment_group),
                **{k: v for k, v in payload.items() if k not in ("category", "description", "assignment_group")},
            )
            mock_incident["short_description"] = short_desc
            mock_incident["severity"] = severity
            if raw_caller:
                mock_incident["caller_id"] = raw_caller

            mock_res = {
                "success": True,
                "ticket_id": mock_incident["number"],
                "number": mock_incident["number"],
                "sys_id": mock_incident["sys_id"],
                "state": "1",
                "caller_id": raw_caller,
                "message": "Mock incident created successfully",
                "result": mock_incident,
            }
            inspector.inspect_post_response(mock_res)

            if inspector.enabled:
                inspector.verify_and_compare(req_summary, payload, mock_incident)

            return mock_res

        if not self.base_url:
            logger.error(
                "!!! [ServiceNowClient.create_incident]: base_url is empty! "
                "SERVICENOW_INSTANCE_URL env var is not set or not resolved. "
                "instance='%s' | Correlation ID: %s",
                self.instance,
                corr_id,
            )
            return {
                "success": False,
                "ticket_id": "",
                "number": "",
                "sys_id": "",
                "state": "",
                "message": "ServiceNow instance URL is not configured.",
            }

        url = f"{self.base_url}/api/now/table/{self.table}"

        logger.info(
            "\n========== SERVICENOW PRE-CALL PAYLOAD LOG ==========\n"
            "Correlation ID : %s\n"
            "u_type         : %s\n"
            "category       : %s\n"
            "subcategory    : %s\n"
            "assignment_grp : %s\n"
            "impact/urgency : %s / %s\n"
            "priority       : %s\n"
            "contact_type   : %s\n"
            "Final JSON     :\n%s\n"
            "=====================================================",
            corr_id,
            payload.get("u_type"),
            payload.get("category"),
            payload.get("subcategory"),
            payload.get("assignment_group"),
            payload.get("impact"),
            payload.get("urgency"),
            payload.get("priority"),
            payload.get("contact_type"),
            json.dumps(payload, indent=2),
        )

        res = self._safe_request("POST", url, json=payload)
        inspector.inspect_post_response(res)

        logger.info(
            "\n========== SERVICENOW POST-CALL RESPONSE LOG ==========\n"
            "Correlation ID   : %s\n"
            "Status Success   : %s\n"
            "Created Incident : %s\n"
            "Created Sys ID   : %s\n"
            "======================================================",
            corr_id,
            res.get("success"),
            res.get("number") or res.get("ticket_id"),
            res.get("sys_id"),
        )

        # GET retrieval & mapping diagnostic report when SERVICENOW_VALIDATE_MAPPING is enabled
        if inspector.enabled and res.get("success") and (res.get("sys_id") or res.get("number")):
            lookup_id = res.get("sys_id") or res.get("number")
            stored_res = self.get_incident(lookup_id)
            stored_data = stored_res.get("result", {}) if isinstance(stored_res, dict) else {}

            audit_results = inspector.verify_and_compare(req_summary, payload, stored_data)

            # Adaptive sys_id resolution fallback if display values were dropped for reference fields
            needs_update = {}
            for r in audit_results:
                if r.status in ("REFERENCE_LOOKUP_FAILED", "FIELD_NOT_STORED") and r.json_key_sent in ("assignment_group", "cmdb_ci", "business_service", "location"):
                    display_val = payload.get(r.json_key_sent)
                    if display_val:
                        tbl = (
                            "sys_user_group" if r.json_key_sent == "assignment_group"
                            else ("cmdb_ci" if r.json_key_sent == "cmdb_ci"
                            else ("cmdb_ci_service" if r.json_key_sent == "business_service"
                            else "cmn_location"))
                        )
                        resolved_sys_id = self.resolve_reference(tbl, display_val)
                        if resolved_sys_id and resolved_sys_id != display_val:
                            needs_update[r.servicenow_field] = resolved_sys_id

            if needs_update and res.get("sys_id"):
                logger.info("[ServiceNowClient.create_incident]: Adaptive reference fallback — updating sys_id %s with sys_ids: %s", res.get("sys_id"), needs_update)
                self.update_incident(res.get("sys_id"), needs_update)

        create_elapsed_ms = int((time.monotonic() - t_create_start) * 1000)
        logger.info(
            "<<< EXIT [ServiceNowClient.create_incident] | Correlation ID: %s | Elapsed: %dms | success=%s, number=%s, sys_id=%s, message='%s'",
            corr_id,
            create_elapsed_ms,
            res.get("success"),
            res.get("number"),
            res.get("sys_id"),
            res.get("message"),
        )
        return res

    def get_incident(self, sys_id: str) -> Dict[str, Any]:
        """Retrieve incident details by sys_id or incident number."""
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
                    "message": f"Incident {sys_id} not found.",
                }
            return {
                "success": True,
                "ticket_id": mock_incident["number"],
                "number": mock_incident["number"],
                "sys_id": mock_incident["sys_id"],
                "state": "1" if mock_incident.get("state") == "OPEN" else "7",
                "message": "Mock incident retrieved successfully",
                "result": mock_incident,
            }

        if not self.base_url:
            return {
                "success": False,
                "ticket_id": "",
                "number": "",
                "sys_id": "",
                "state": "",
                "message": "ServiceNow instance URL is not configured.",
            }

        if sys_id.startswith("INC") or (len(sys_id) != 32):
            import urllib.parse
            url = f"{self.base_url}/api/now/table/{self.table}?sysparm_query=number={urllib.parse.quote(sys_id)}&sysparm_limit=1"
        else:
            url = f"{self.base_url}/api/now/table/{self.table}/{sys_id}"

        res = self._safe_request("GET", url)
        if res.get("success") and isinstance(res.get("result"), list) and len(res["result"]) > 0:
            res["result"] = res["result"][0]
        return res

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
                    "message": f"Incident with sys_id {sys_id} not found.",
                }
            logger.info("ServiceNowClient: Incident update completed (Mock sys_id=%s)", sys_id)
            return {
                "success": True,
                "ticket_id": mock_incident["number"],
                "number": mock_incident["number"],
                "sys_id": mock_incident["sys_id"],
                "state": "1" if mock_incident.get("state") == "OPEN" else "7",
                "message": "Mock incident updated successfully",
                "result": mock_incident,
            }

        if not self.base_url:
            return {
                "success": False,
                "ticket_id": "",
                "number": "",
                "sys_id": "",
                "state": "",
                "message": "ServiceNow instance URL is not configured.",
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
            "work_notes": work_note,
        }
        return self.update_incident(sys_id, payload, use_patch=True)
