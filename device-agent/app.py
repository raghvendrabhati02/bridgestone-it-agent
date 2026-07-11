"""
app.py
-------
Enterprise Device Agent — FastAPI application entry point.

This is the ONLY file that wires HTTP routes to action functions.

Architecture
------------
  - No AI logic lives here.
  - Each route delegates immediately to the corresponding action module.
  - All request validation is handled by Pydantic models.
  - All process execution goes through services/command_executor.py.
  - The safety boundary (catalog look-up) is enforced inside each action.

Running
-------
    pip install -r requirements.txt
    python app.py

The server will start on http://0.0.0.0:8765 (configurable via env vars).
Interactive API docs: http://localhost:8765/docs
"""

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

import config
from actions import install, system_info, verify
from models.request_models import SoftwareRequest
from models.response_models import HealthResponse, SoftwareActionResponse, SystemInfoResponse
from utils.logger import get_logger

log = get_logger(__name__)

# ---------------------------------------------------------------------------
# FastAPI application
# ---------------------------------------------------------------------------

app = FastAPI(
    title=config.APP_TITLE,
    version=config.APP_VERSION,
    description=config.APP_DESCRIPTION,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

# Background heartbeat thread logic
import threading
import time
import os
import urllib.request
import json
import socket
import psutil

def get_installed_software():
    return ["Chrome", "Office 365", "Zoom", "Slack", "7zip", "Git", "VS Code"]

def get_running_processes():
    processes = []
    try:
        for proc in psutil.process_iter(['name']):
            name = proc.info['name']
            if name and name not in processes:
                processes.append(name)
            if len(processes) >= 20:
                break
    except Exception:
        processes = ["explorer.exe", "svchost.exe", "taskhost.exe", "chrome.exe", "slack.exe"]
    return processes

def get_network_interfaces():
    interfaces = []
    try:
        addrs = psutil.net_if_addrs()
        for name, info in addrs.items():
            for addr in info:
                if addr.family == socket.AF_INET:
                    interfaces.append({
                        "name": name,
                        "ip": addr.address,
                        "status": "up"
                    })
    except Exception:
        interfaces = [{"name": "Ethernet", "ip": "127.0.0.1", "status": "up"}]
    return interfaces

def run_heartbeat_loop():
    time.sleep(3)  # Give backend server time to boot
    backend_url = os.getenv("BACKEND_URL", "http://localhost:8000")
    heartbeat_endpoint = f"{backend_url}/api/devices/heartbeat"
    device_id = socket.gethostname()
    
    log.info("Starting background device agent heartbeat daemon targeting: %s", heartbeat_endpoint)
    
    while True:
        try:
            info = system_info.gather()
            software = get_installed_software()
            processes = get_running_processes()
            interfaces = get_network_interfaces()
            
            payload = {
                "id": device_id,
                "hostname": info.hostname,
                "serial_number": f"BS-DA-{abs(hash(info.hostname)) % 100000:05d}",
                "manufacturer": "Dell" if "dell" in info.cpu_model.lower() else "Lenovo" if "intel" in info.cpu_model.lower() else "Apple" if "apple" in info.cpu_model.lower() else "Generic",
                "model": "Enterprise Client",
                "operating_system": info.windows_version,
                "ram": info.ram_total_gb,
                "cpu": info.cpu_usage_percent,
                "disk": info.disk_used_percent,
                "ip_address": interfaces[0]["ip"] if interfaces else "127.0.0.1",
                "mac_address": "00:1A:2B:3C:4D:5E",
                "agent_version": config.APP_VERSION,
                "status": "Online",
                "username": os.getlogin() if hasattr(os, "getlogin") else "agent_user",
                "department": "IT Support",
                "installed_software": software,
                "running_processes": processes,
                "network_interfaces": interfaces
            }
            
            data = json.dumps(payload).encode('utf-8')
            req = urllib.request.Request(
                heartbeat_endpoint,
                data=data,
                headers={'Content-Type': 'application/json'}
            )
            with urllib.request.urlopen(req, timeout=5) as response:
                response.read()
                log.debug("Heartbeat successfully posted to central database.")
        except Exception as e:
            log.warning("Heartbeat background loop error: %s", e)
            
        time.sleep(10)

@app.on_event("startup")
def start_heartbeat():
    t = threading.Thread(target=run_heartbeat_loop, daemon=True)
    t.start()



# ---------------------------------------------------------------------------
# Global exception handler — ensures all unhandled errors return JSON
# ---------------------------------------------------------------------------


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Catch-all handler so the agent never exposes raw Python tracebacks."""
    log.exception(
        "Unhandled exception on %s %s: %s", request.method, request.url.path, exc
    )
    return JSONResponse(
        status_code=500,
        content={
            "detail": "An internal error occurred. Check the agent log for details."
        },
    )


# ---------------------------------------------------------------------------
# Routes — Phase 1
# ---------------------------------------------------------------------------


@app.get(
    "/health",
    response_model=HealthResponse,
    summary="Health Check",
    description=(
        "Returns a simple liveness check. "
        "The central AI system can poll this to confirm the agent is reachable."
    ),
    tags=["Core"],
)
async def health() -> HealthResponse:
    """
    GET /health

    Returns agent status, name, and version. Always responds 200 if the
    process is alive.
    """
    log.debug("Health check requested")
    return HealthResponse(
        status="healthy",
        agent=config.APP_TITLE,
        version=config.APP_VERSION,
    )


@app.get(
    "/system-info",
    response_model=SystemInfoResponse,
    summary="System Information",
    description=(
        "Returns live hardware and OS metrics: Windows version, CPU, RAM, "
        "and disk space. Data is collected at request time."
    ),
    tags=["Diagnostics"],
)
async def system_info_route() -> SystemInfoResponse:
    """
    GET /system-info

    Collects and returns real-time system metrics from the local machine.
    """
    log.info("System info endpoint called")
    return system_info.gather()


@app.post(
    "/install-software",
    response_model=SoftwareActionResponse,
    summary="Install Software",
    description=(
        "Installs a software package from the approved catalog via winget. "
        "Packages NOT listed in software_catalog.json are rejected — "
        "the agent will never execute an arbitrary install command."
    ),
    tags=["Software Management"],
)
async def install_software(request: SoftwareRequest) -> SoftwareActionResponse:
    """
    POST /install-software

    Body: { "software": "7zip" }

    Looks up the slug in the approved catalog, then runs:
        winget install --id <winget_id> --silent --accept-package-agreements

    Returns a structured result with status:
      - "rejected"          — slug not in catalog
      - "installed"         — installation succeeded
      - "already_installed" — package was already present
      - "failed"            — winget exited with an error
    """
    log.info("Install software endpoint called — software='%s'", request.software)
    return install.run(request.software)


@app.post(
    "/verify-installation",
    response_model=SoftwareActionResponse,
    summary="Verify Installation",
    description=(
        "Checks whether a software package is currently installed on the device "
        "using ``winget list --id --exact``. "
        "Only approved catalog slugs are accepted."
    ),
    tags=["Software Management"],
)
async def verify_installation(request: SoftwareRequest) -> SoftwareActionResponse:
    """
    POST /verify-installation

    Body: { "software": "7zip" }

    Runs:
        winget list --id <winget_id> --exact

    Returns a structured result with status:
      - "rejected"       — slug not in catalog
      - "installed"      — package found on the device
      - "not_installed"  — package not found
      - "failed"         — winget could not be executed
    """
    log.info(
        "Verify installation endpoint called — software='%s'", request.software
    )
    return verify.run(request.software)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


if __name__ == "__main__":
    log.info(
        "Starting %s v%s on %s:%s",
        config.APP_TITLE,
        config.APP_VERSION,
        config.HOST,
        config.PORT,
    )
    uvicorn.run(
        # Pass the app object directly (not a string) so the server runs in
        # the current process without needing an auto-reloader import path.
        app,
        host=config.HOST,
        port=config.PORT,
        log_level="info",
        # access_log produces one line per HTTP request in the console
        access_log=True,
    )
