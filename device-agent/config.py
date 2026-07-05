"""
config.py
---------
Centralised configuration for the Enterprise Device Agent.

All environment-level settings live here so other modules never
hard-code paths or version strings.
"""

import os
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

# Root directory of this module (device-agent/)
BASE_DIR: Path = Path(__file__).resolve().parent

# Absolute path to the approved-software catalog
SOFTWARE_CATALOG_PATH: Path = BASE_DIR / "software_catalog.json"

# Directory where log files are written
LOG_DIR: Path = BASE_DIR / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

LOG_FILE: Path = LOG_DIR / "device_agent.log"

# ---------------------------------------------------------------------------
# Application metadata
# ---------------------------------------------------------------------------

APP_TITLE: str = "Enterprise Device Agent"
APP_VERSION: str = "1.0"
APP_DESCRIPTION: str = (
    "Lightweight REST agent that executes approved IT actions on Windows devices. "
    "Does NOT contain any AI logic — only carries out pre-approved commands."
)

# ---------------------------------------------------------------------------
# Runtime settings
# ---------------------------------------------------------------------------

# Host / port for the Uvicorn server
HOST: str = os.getenv("DEVICE_AGENT_HOST", "0.0.0.0")
PORT: int = int(os.getenv("DEVICE_AGENT_PORT", "8765"))

# Maximum seconds to wait for a winget command to complete
WINGET_TIMEOUT_SECONDS: int = int(os.getenv("WINGET_TIMEOUT", "300"))  # 5 minutes
