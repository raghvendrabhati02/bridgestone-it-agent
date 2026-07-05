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
