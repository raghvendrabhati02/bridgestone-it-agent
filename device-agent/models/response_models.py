"""
models/response_models.py
--------------------------
Pydantic v2 response schemas for all Device Agent API endpoints.

Using typed response models gives:
  - Automatic OpenAPI documentation.
  - Runtime serialisation validation (no leaking of internal fields).
  - Consistent JSON shape across every endpoint.
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# /health
# ---------------------------------------------------------------------------


class HealthResponse(BaseModel):
    """Response body for GET /health."""

    status: str = Field(..., description="Agent health status.", examples=["healthy"])
    agent: str = Field(
        ...,
        description="Human-readable agent name.",
        examples=["Enterprise Device Agent"],
    )
    version: str = Field(..., description="Agent version string.", examples=["1.0"])

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "status": "healthy",
                    "agent": "Enterprise Device Agent",
                    "version": "1.0",
                }
            ]
        }
    }


# ---------------------------------------------------------------------------
# /system-info
# ---------------------------------------------------------------------------


class SystemInfoResponse(BaseModel):
    """Response body for GET /system-info."""

    hostname: str = Field(..., description="Machine hostname.")
    windows_version: str = Field(..., description="Windows OS version string.")
    cpu_model: str = Field(..., description="CPU model name.")
    cpu_cores_physical: int = Field(..., description="Number of physical CPU cores.")
    cpu_cores_logical: int = Field(..., description="Number of logical CPU cores (with HT).")
    cpu_usage_percent: float = Field(..., description="Current CPU usage percentage (1-second sample).")
    ram_total_gb: float = Field(..., description="Total installed RAM in GB.")
    ram_available_gb: float = Field(..., description="Available RAM in GB.")
    ram_used_percent: float = Field(..., description="RAM usage as a percentage.")
    disk_total_gb: float = Field(..., description="Total disk space on the system drive (GB).")
    disk_free_gb: float = Field(..., description="Free disk space on the system drive (GB).")
    disk_used_percent: float = Field(..., description="Disk usage as a percentage.")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "hostname": "BRIDGESTONE-PC01",
                    "windows_version": "10.0.19045",
                    "cpu_model": "Intel(R) Core(TM) i7-10750H CPU @ 2.60GHz",
                    "cpu_cores_physical": 6,
                    "cpu_cores_logical": 12,
                    "cpu_usage_percent": 14.3,
                    "ram_total_gb": 16.0,
                    "ram_available_gb": 9.4,
                    "ram_used_percent": 41.3,
                    "disk_total_gb": 476.9,
                    "disk_free_gb": 201.5,
                    "disk_used_percent": 57.7,
                }
            ]
        }
    }


# ---------------------------------------------------------------------------
# /install-software  &  /verify-installation
# ---------------------------------------------------------------------------


class SoftwareActionResponse(BaseModel):
    """
    Generic response for software install and verify operations.

    Fields
    ------
    software:
        The slug that was requested.
    winget_id:
        The resolved winget package identifier from the catalog.
    status:
        High-level outcome: "installed", "not_installed", "already_installed",
        "failed", "rejected".
    message:
        Human-readable explanation of the outcome.
    stdout:
        Raw standard output from winget (only for install; None for verify).
    returncode:
        Process exit code from winget (None if the command was rejected before
        being launched).
    """

    software: str = Field(..., description="Software slug that was requested.")
    winget_id: Optional[str] = Field(
        None, description="Winget package ID resolved from the catalog."
    )
    status: str = Field(
        ...,
        description=(
            "Outcome: 'installed', 'already_installed', 'not_installed', "
            "'failed', 'rejected'."
        ),
    )
    message: str = Field(..., description="Human-readable summary of the outcome.")
    stdout: Optional[str] = Field(
        None, description="Captured stdout from winget (install only)."
    )
    returncode: Optional[int] = Field(
        None, description="winget process exit code (None if not launched)."
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "software": "7zip",
                    "winget_id": "7zip.7zip",
                    "status": "installed",
                    "message": "7-Zip was installed successfully.",
                    "stdout": "Successfully installed",
                    "returncode": 0,
                }
            ]
        }
    }
