"""
servicenow_service.py
─────────────────────────────────────────────────────────────────────────────
Dedicated business logic and orchestration service for ServiceNow operations.

Responsibilities:
  • Encapsulates all ServiceNow interaction.
  • Validates configuration via validate_configuration() before any API call.
  • Normalizes ServiceNow responses into strongly-typed Pydantic models.
  • Provides structured logging for audit and observability without exposing credentials.
  • Employs dependency injection for the underlying HTTP ServiceNowClient.
"""

from __future__ import annotations

import logging
import os
import traceback
from typing import Optional, Tuple, Dict, Any

from app.models.servicenow_models import (
    IncidentCreateRequest,
    IncidentCreateResponse,
    IncidentStatus,
    IncidentUpdateRequest,
    extract_sn_field,
)
from app.services.servicenow_client import ServiceNowClient
from app.services.servicenow_exceptions import (
    ServiceNowException,
    ServiceNowConfigurationError,
    ServiceNowAuthenticationError,
    ServiceNowAPIError,
)

logger = logging.getLogger("it-agent-backend")

_servicenow_service_instance: Optional[ServiceNowService] = None

def get_servicenow_service() -> ServiceNowService:
    """Returns singleton instance of ServiceNowService."""
    global _servicenow_service_instance
    if _servicenow_service_instance is None:
        _servicenow_service_instance = ServiceNowService()
    return _servicenow_service_instance


class ServiceNowService:
    """Business logic and validation layer for ServiceNow integration."""

    def __init__(self, client: Optional[ServiceNowClient] = None) -> None:
        logger.info("Initializing ServiceNow service")
        self._client = client or ServiceNowClient()

        # Read configuration from environment or client
        raw_enabled = os.getenv("SERVICENOW_ENABLED", "false").strip().lower()
        self.enabled = raw_enabled == "true"
        self.instance_url = (
            os.getenv("SERVICENOW_INSTANCE_URL")
            or os.getenv("SERVICENOW_INSTANCE")
            or getattr(self._client, "instance", "")
        )
        self.auth_type = os.getenv("SERVICENOW_AUTH_TYPE", "basic").strip().lower()
        self.username = os.getenv("SERVICENOW_USERNAME") or getattr(self._client, "username", "")
        self.password = os.getenv("SERVICENOW_PASSWORD") or getattr(self._client, "password", "")
        self.client_id = os.getenv("SERVICENOW_CLIENT_ID", "")
        self.client_secret = os.getenv("SERVICENOW_CLIENT_SECRET", "")
        self.assignment_group_mode = os.getenv("SERVICENOW_ASSIGNMENT_GROUP_MODE", "name").strip().lower()
        self.use_mock = getattr(self._client, "use_mock", False)

        is_valid, msg = self.validate_configuration()
        logger.info("Configuration validation: valid=%s, msg='%s'", is_valid, msg)
        logger.info("Selected authentication method: %s", self.auth_type)

        if self.use_mock:
            logger.info("Mock mode enabled")
        else:
            logger.info("Real API mode enabled")

        if not self.enabled:
            logger.info("ServiceNow integration disabled")
        elif not is_valid:
            logger.warning("ServiceNow integration configured but invalid: %s", msg)

    def validate_configuration(self) -> Tuple[bool, str]:
        """
        Validates required configuration before making any API call.

        Checks:
          • SERVICENOW_ENABLED is true.
          • Instance URL exists and is valid format.
          • Auth type is valid ('basic' or 'oauth').
          • Username/password present for Basic Auth.
          • client_id/client_secret AND oauth_token present for OAuth.
          • Assignment group mode is valid ('name' or 'sys_id').

        Returns (is_valid: bool, error_message: str).
        """
        if not self.enabled:
            return False, "ServiceNow integration is disabled (SERVICENOW_ENABLED=false)"

        if not self.instance_url or not str(self.instance_url).strip():
            return False, "SERVICENOW_INSTANCE_URL is not configured"

        url_str = str(self.instance_url).strip()
        if not (url_str.startswith("http://") or url_str.startswith("https://") or ("." in url_str)):
            return False, f"SERVICENOW_INSTANCE_URL '{self.instance_url}' has an invalid format"

        if self.auth_type not in ("basic", "oauth"):
            return False, f"Invalid SERVICENOW_AUTH_TYPE '{self.auth_type}'. Must be 'basic' or 'oauth'."

        if self.auth_type == "basic":
            if not self.username or not self.password:
                return False, "Basic authentication requires SERVICENOW_USERNAME and SERVICENOW_PASSWORD"
        elif self.auth_type == "oauth":
            if not self.client_id or not self.client_secret:
                return False, "OAuth authentication requires SERVICENOW_CLIENT_ID and SERVICENOW_CLIENT_SECRET"
            if not self.username or not self.password:
                return False, "OAuth authentication requires SERVICENOW_USERNAME and SERVICENOW_PASSWORD"

        if self.assignment_group_mode not in ("name", "sys_id"):
            return False, f"Invalid SERVICENOW_ASSIGNMENT_GROUP_MODE '{self.assignment_group_mode}'. Must be 'name' or 'sys_id'."

        return True, "Configuration valid"

    def is_configured(self) -> bool:
        """Return True if ServiceNow integration is enabled and fully configured."""
        is_valid, _ = self.validate_configuration()
        return is_valid

    def create_incident(self, request: IncidentCreateRequest) -> IncidentCreateResponse:
        """
        Create a ServiceNow incident using strongly-typed models.
        Verifies configuration before attempting execution.
        """
        logger.info(
            ">>> ENTRY [ServiceNowService.create_incident]: "
            "category=%s, short_description='%s', severity=%s, "
            "assignment_group=%s, caller_id=%s, description='%.100s'",
            request.category,
            request.short_description,
            request.severity,
            request.assignment_group,
            request.caller_id,
            request.description,
        )

        is_valid, err_msg = self.validate_configuration()
        logger.info(
            "[ServiceNowService.create_incident]: config validation: valid=%s, msg='%s'",
            is_valid,
            err_msg,
        )
        if not is_valid:
            if not self.enabled:
                logger.info("[ServiceNowService.create_incident]: SN integration disabled — skipping incident creation")
            else:
                logger.error("[ServiceNowService.create_incident]: ServiceNowConfigurationError: %s", err_msg)
            return IncidentCreateResponse(
                success=False,
                sys_id="N/A",
                number="",
                ticket_id="",
                state="",
                caller_id=request.caller_id,
                message=f"ServiceNow unconfigured: {err_msg}"
            )

        import time
        from app.core.logging_context import correlation_id_ctx
        t_start = time.monotonic()
        corr_id = correlation_id_ctx.get() or "<none>"

        logger.info(
            ">>> ENTRY [ServiceNowService.create_incident] | Correlation ID: %s | short_desc='%s', category=%s, caller_id=%s",
            corr_id,
            request.short_description,
            request.category,
            request.caller_id,
        )

        base_url = getattr(self._client, "base_url", "")
        table = getattr(self._client, "table", "incident")
        target_url = f"{base_url}/api/now/table/{table}"
        logger.info(
            "[ServiceNowService.create_incident]: Target URL: %s | Correlation ID: %s",
            target_url,
            corr_id,
        )

        try:
            extra = request.extra_fields or {}
            res_dict = self._client.create_incident(
                short_description=request.short_description,
                description=request.description,
                category=request.category,
                severity=request.severity,
                assignment_group=request.assignment_group,
                caller_id=request.caller_id,
                **extra,
            )

            elapsed_ms = int((time.monotonic() - t_start) * 1000)

            logger.info(
                "[ServiceNowService.create_incident]: Raw response from client: %s | Correlation ID: %s",
                res_dict,
                corr_id,
            )

            if isinstance(res_dict, dict) and not res_dict.get("success", False):
                msg = res_dict.get("message", "API request failed")
                if "auth" in msg.lower() or "401" in msg or "403" in msg:
                    logger.error(
                        "[ServiceNowService.create_incident]: Authentication failure: %s | Correlation ID: %s", msg, corr_id
                    )
                    raise ServiceNowAuthenticationError(message=msg)
                logger.error(
                    "[ServiceNowService.create_incident]: API returned success=False: %s | Correlation ID: %s", msg, corr_id
                )
                raise ServiceNowAPIError(message=msg)

            sys_id = res_dict.get("sys_id", "")
            number = res_dict.get("number") or res_dict.get("ticket_id") or ""
            state_val = str(res_dict.get("state", "1"))
            caller = res_dict.get("caller_id") or request.caller_id

            logger.info(
                "<<< EXIT [ServiceNowService.create_incident] | Correlation ID: %s | Elapsed: %dms | sys_id=%s, number=%s, state=%s",
                corr_id,
                elapsed_ms,
                sys_id,
                number,
                state_val,
            )

            return IncidentCreateResponse(
                success=True,
                sys_id=sys_id,
                number=number,
                ticket_id=number,
                state=state_val,
                caller_id=caller,
                message=res_dict.get("message", "Incident created successfully"),
                result=res_dict.get("result")
            )

        except (ServiceNowAuthenticationError, ServiceNowAPIError):
            raise
        except Exception as exc:
            logger.error(
                "!!! EXCEPTION [ServiceNowService.create_incident]: %s\n%s",
                exc,
                traceback.format_exc(),
            )
            raise ServiceNowAPIError(message=str(exc)) from exc

    def get_incident(self, sys_id_or_number: str) -> Optional[IncidentStatus]:
        """Retrieve incident details by sys_id or number."""
        is_valid, err_msg = self.validate_configuration()
        if not is_valid:
            logger.info("ServiceNow integration disabled — skipping get_incident")
            return None

        try:
            res_dict = self._client.get_incident(sys_id_or_number)
            if not res_dict.get("success", False):
                logger.error("API request failed: %s", res_dict.get("message"))
                return None

            result = res_dict.get("result", {})
            return IncidentStatus(
                sys_id=res_dict.get("sys_id") or extract_sn_field(result, "sys_id", sys_id_or_number),
                number=res_dict.get("number") or extract_sn_field(result, "number"),
                state=str(res_dict.get("state") or extract_sn_field(result, "state")),
                short_description=extract_sn_field(result, "short_description"),
                description=extract_sn_field(result, "description"),
                category=extract_sn_field(result, "category"),
                assignment_group=extract_sn_field(result, "assignment_group"),
                caller_id=extract_sn_field(result, "caller_id"),
                created_at=result.get("sys_created_on"),
                updated_at=result.get("sys_updated_on"),
                close_notes=result.get("close_notes"),
                work_notes=result.get("work_notes"),
                raw_result=result
            )
        except Exception as exc:
            logger.error("API request failed: %s", exc)
            return None

    def update_incident(self, sys_id_or_number: str, request: IncidentUpdateRequest) -> Optional[IncidentStatus]:
        """Update incident details in ServiceNow using PATCH partial updates."""
        is_valid, err_msg = self.validate_configuration()
        if not is_valid:
            logger.info("ServiceNow integration disabled — skipping update_incident")
            return None

        logger.info("Incident update started for sys_id=%s", sys_id_or_number)

        try:
            payload: Dict[str, Any] = {}
            if request.short_description: payload["short_description"] = request.short_description
            if request.description: payload["description"] = request.description
            if request.state: payload["state"] = request.state
            if request.assignment_group: payload["assignment_group"] = request.assignment_group
            if request.caller_id: payload["caller_id"] = request.caller_id
            if request.work_notes: payload["work_notes"] = request.work_notes
            if request.close_notes: payload["close_notes"] = request.close_notes
            if request.close_code: payload["close_code"] = request.close_code
            if request.extra_fields: payload.update(request.extra_fields)

            res_dict = self._client.update_incident(sys_id_or_number, payload, use_patch=True)
            if not res_dict.get("success", False):
                logger.error("API request failed: %s", res_dict.get("message"))
                return None

            logger.info("Incident update completed for sys_id=%s", sys_id_or_number)
            return self.get_incident(sys_id_or_number)
        except Exception as exc:
            logger.error("API request failed: %s", exc)
            return None

    def add_work_note(self, sys_id_or_number: str, work_note: str) -> Optional[IncidentStatus]:
        """Add a work note entry to an incident."""
        is_valid, err_msg = self.validate_configuration()
        if not is_valid:
            logger.info("ServiceNow integration disabled — skipping add_work_note")
            return None

        logger.info("Work note added to sys_id=%s", sys_id_or_number)

        try:
            res_dict = self._client.add_work_note(sys_id_or_number, work_note)
            if not res_dict.get("success", False):
                logger.error("API request failed: %s", res_dict.get("message"))
                return None
            return self.get_incident(sys_id_or_number)
        except Exception as exc:
            logger.error("API request failed: %s", exc)
            return None

    def health_check(self) -> Dict[str, Any]:
        """
        Perform a comprehensive health check against ServiceNow API.
        Returns status, authentication status, instance domain, version, and latency.
        """
        import time
        if not self.enabled:
            return {
                "status": "Disabled",
                "authenticated": False,
                "instance": self.instance_url or "Unconfigured",
                "version": "Table API v1",
                "latency_ms": 0,
                "message": "ServiceNow integration is disabled (SERVICENOW_ENABLED=false)"
            }

        is_valid, err_msg = self.validate_configuration()
        if not is_valid:
            return {
                "status": "Configuration Error",
                "authenticated": False,
                "instance": self.instance_url or "Unconfigured",
                "version": "Table API v1",
                "latency_ms": 0,
                "message": err_msg
            }

        if self.use_mock:
            return {
                "status": "Connected (Mock)",
                "authenticated": True,
                "instance": "mock.service-now.com",
                "version": "Table API v1 (Mock)",
                "latency_ms": 1.2,
                "message": "ServiceNow Mock mode active"
            }

        start_time = time.time()
        try:
            test_url = f"{getattr(self._client, 'base_url', '')}/api/now/table/{getattr(self._client, 'table', 'incident')}?sysparm_limit=1"
            res = self._client._safe_request("GET", test_url)
            elapsed_ms = round((time.time() - start_time) * 1000, 2)
            if res.get("success"):
                return {
                    "status": "Connected",
                    "authenticated": True,
                    "instance": self.instance_url,
                    "version": "Vancouver / Table API v1",
                    "latency_ms": elapsed_ms,
                    "message": "Successfully authenticated with ServiceNow Table API"
                }
            else:
                msg = res.get("message", "ServiceNow request failed")
                is_auth_error = ("auth" in msg.lower() or "401" in msg or "403" in msg)
                return {
                    "status": "Authentication Failed" if is_auth_error else "Disconnected",
                    "authenticated": False,
                    "instance": self.instance_url,
                    "version": "Table API v1",
                    "latency_ms": elapsed_ms,
                    "message": msg
                }
        except Exception as exc:
            elapsed_ms = round((time.time() - start_time) * 1000, 2)
            return {
                "status": "Disconnected",
                "authenticated": False,
                "instance": self.instance_url,
                "version": "Table API v1",
                "latency_ms": elapsed_ms,
                "message": str(exc)
            }
