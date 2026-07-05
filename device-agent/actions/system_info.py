"""
actions/system_info.py
-----------------------
Collects live hardware and OS metrics from the local Windows machine.

Uses the ``psutil`` library (cross-platform) plus ``platform`` from the
standard library. No subprocess calls are made here — everything is read
via Python APIs.

Public function
---------------
    gather() -> SystemInfoResponse
"""

import platform
import socket

import psutil

from models.response_models import SystemInfoResponse
from utils.logger import get_logger

log = get_logger(__name__)


def _round2(value: float) -> float:
    """Round a float to 2 decimal places for clean JSON output."""
    return round(value, 2)


def _bytes_to_gb(byte_count: int) -> float:
    """Convert bytes to gigabytes, rounded to 2 decimal places."""
    return _round2(byte_count / (1024 ** 3))


def gather() -> SystemInfoResponse:
    """
    Collect system information and return a typed response object.

    Metrics gathered
    ----------------
    - Hostname
    - Windows version (platform.version())
    - CPU model, physical cores, logical cores, current usage %
    - RAM total, available, usage %
    - Disk total, free, usage % (for the C:\\ drive / root partition)

    Returns
    -------
    SystemInfoResponse
        A fully populated Pydantic model ready for serialisation.

    Raises
    ------
    Does not raise. Any unexpected psutil errors are caught, logged, and
    replaced with safe sentinel values so the endpoint always responds.
    """
    log.info("Collecting system information")

    # --- Hostname ---
    hostname = socket.gethostname()

    # --- OS version ---
    windows_version = platform.version()

    # --- CPU ---
    try:
        cpu_model: str = platform.processor() or "Unknown"
        cpu_cores_physical: int = psutil.cpu_count(logical=False) or 1
        cpu_cores_logical: int = psutil.cpu_count(logical=True) or 1
        # interval=1 → 1-second blocking measurement for an accurate reading
        cpu_usage_percent: float = _round2(psutil.cpu_percent(interval=1))
    except Exception as exc:  # noqa: BLE001
        log.warning("Failed to read CPU metrics: %s", exc)
        cpu_model = "Unknown"
        cpu_cores_physical = 0
        cpu_cores_logical = 0
        cpu_usage_percent = 0.0

    # --- RAM ---
    try:
        vm = psutil.virtual_memory()
        ram_total_gb: float = _bytes_to_gb(vm.total)
        ram_available_gb: float = _bytes_to_gb(vm.available)
        ram_used_percent: float = _round2(vm.percent)
    except Exception as exc:  # noqa: BLE001
        log.warning("Failed to read RAM metrics: %s", exc)
        ram_total_gb = 0.0
        ram_available_gb = 0.0
        ram_used_percent = 0.0

    # --- Disk (C:\ on Windows, / on other platforms) ---
    disk_path = "C:\\" if platform.system() == "Windows" else "/"
    try:
        du = psutil.disk_usage(disk_path)
        disk_total_gb: float = _bytes_to_gb(du.total)
        disk_free_gb: float = _bytes_to_gb(du.free)
        disk_used_percent: float = _round2(du.percent)
    except Exception as exc:  # noqa: BLE001
        log.warning("Failed to read disk metrics for '%s': %s", disk_path, exc)
        disk_total_gb = 0.0
        disk_free_gb = 0.0
        disk_used_percent = 0.0

    log.info(
        "System info collected — hostname=%s, CPU=%s%%, RAM=%.1f/%.1f GB, Disk=%.1f/%.1f GB",
        hostname,
        cpu_usage_percent,
        ram_available_gb,
        ram_total_gb,
        disk_free_gb,
        disk_total_gb,
    )

    return SystemInfoResponse(
        hostname=hostname,
        windows_version=windows_version,
        cpu_model=cpu_model,
        cpu_cores_physical=cpu_cores_physical,
        cpu_cores_logical=cpu_cores_logical,
        cpu_usage_percent=cpu_usage_percent,
        ram_total_gb=ram_total_gb,
        ram_available_gb=ram_available_gb,
        ram_used_percent=ram_used_percent,
        disk_total_gb=disk_total_gb,
        disk_free_gb=disk_free_gb,
        disk_used_percent=disk_used_percent,
    )
