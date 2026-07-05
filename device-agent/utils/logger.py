"""
utils/logger.py
---------------
Configures a module-level logger that writes to both the console and a
rotating file (logs/device_agent.log).

Usage
-----
    from utils.logger import get_logger

    log = get_logger(__name__)
    log.info("Device Agent started")
"""

import logging
import sys
from logging.handlers import RotatingFileHandler

from config import LOG_FILE

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Maximum size of a single log file before rotation (10 MB)
MAX_BYTES: int = 10 * 1024 * 1024
BACKUP_COUNT: int = 5

LOG_FORMAT: str = (
    "%(asctime)s | %(levelname)-8s | %(name)s | %(funcName)s:%(lineno)d | %(message)s"
)
DATE_FORMAT: str = "%Y-%m-%d %H:%M:%S"


def _build_formatter() -> logging.Formatter:
    """Return a consistently formatted Formatter instance."""
    return logging.Formatter(fmt=LOG_FORMAT, datefmt=DATE_FORMAT)


def _configure_root_logger() -> None:
    """
    Set up the root logger exactly once.

    Attaches:
      - StreamHandler  → stdout (INFO+)
      - RotatingFileHandler → LOG_FILE (DEBUG+)
    """
    root = logging.getLogger()

    # Avoid adding duplicate handlers if this module is imported multiple times
    if root.handlers:
        return

    root.setLevel(logging.DEBUG)

    formatter = _build_formatter()

    # --- Console handler (INFO and above) ---
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    root.addHandler(console_handler)

    # --- Rotating file handler (DEBUG and above) ---
    file_handler = RotatingFileHandler(
        filename=LOG_FILE,
        maxBytes=MAX_BYTES,
        backupCount=BACKUP_COUNT,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    root.addHandler(file_handler)


# Configure once at import time
_configure_root_logger()


def get_logger(name: str) -> logging.Logger:
    """
    Return a named child logger.

    Parameters
    ----------
    name:
        Typically ``__name__`` from the calling module.

    Returns
    -------
    logging.Logger
        A logger that inherits handlers from the root logger configured above.
    """
    return logging.getLogger(name)
