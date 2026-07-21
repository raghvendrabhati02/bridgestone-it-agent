"""
servicenow_exceptions.py
─────────────────────────────────────────────────────────────────────────────
Custom exception hierarchy for ServiceNow integration layer.
"""

from __future__ import annotations
from typing import Optional


class ServiceNowException(Exception):
    """Base exception for all ServiceNow integration errors."""
    pass


class ServiceNowConfigurationError(ServiceNowException):
    """Raised when ServiceNow configuration is missing, incomplete, or invalid."""
    pass


class ServiceNowAuthenticationError(ServiceNowException):
    """Raised when authentication credentials or token validation fails (401/403)."""
    def __init__(self, status_code: int = 401, message: str = "Authentication failed") -> None:
        super().__init__(f"Authentication failed (HTTP {status_code}): {message}")
        self.status_code = status_code
        self.message = message


class ServiceNowAPIError(ServiceNowException):
    """Raised when a ServiceNow Table API request returns a failure status or malformed payload."""
    def __init__(self, status_code: Optional[int] = None, message: str = "API request failed") -> None:
        prefix = f"HTTP {status_code}: " if status_code else ""
        super().__init__(f"{prefix}{message}")
        self.status_code = status_code
        self.message = message


class ServiceNowConnectionError(ServiceNowException):
    """Raised when network connectivity to ServiceNow fails."""
    pass


class ServiceNowTimeoutError(ServiceNowException):
    """Raised when a request to ServiceNow times out."""
    pass


# Backward compatibility aliases for existing test suites
ServiceNowAuthError = ServiceNowAuthenticationError
ServiceNowHTTPError = ServiceNowAPIError
