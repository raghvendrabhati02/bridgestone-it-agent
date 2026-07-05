"""
services/command_executor.py
-----------------------------
Low-level subprocess wrapper used exclusively to run winget commands.

SAFETY CONTRACT
---------------
This module is the single chokepoint for all process execution.

  - Only pre-built winget command lists are accepted (no shell=True).
  - Callers must assemble the argument list themselves from catalog data;
    this module does NOT accept raw user strings.
  - If the winget executable is not found on PATH the error is caught and
    returned as a structured result rather than propagating an exception.

CommandResult
-------------
A plain dataclass returned by every execution function so that action
modules never have to inspect raw subprocess.CompletedProcess objects.
"""

import subprocess
from dataclasses import dataclass
from typing import Optional

from config import WINGET_TIMEOUT_SECONDS
from utils.logger import get_logger

log = get_logger(__name__)

# Winget exit code returned when a package is already installed
_WINGET_ALREADY_INSTALLED_CODE = 0x8A150008  # 2316632072 unsigned


@dataclass
class CommandResult:
    """
    Structured result from a subprocess execution.

    Attributes
    ----------
    success:
        True when the process exited with code 0 OR with the
        "already installed" winget code.
    returncode:
        Raw process exit code.
    stdout:
        Combined stdout + stderr from the process.
    already_installed:
        True when winget reported that the package is already present.
    error:
        Human-readable error message if the command could not be launched
        (e.g. winget not found). None on successful launch.
    """

    success: bool
    returncode: int
    stdout: str
    already_installed: bool = False
    error: Optional[str] = None


def run_winget(args: list[str], *, timeout: int = WINGET_TIMEOUT_SECONDS) -> CommandResult:
    """
    Execute a winget sub-command and return a CommandResult.

    Parameters
    ----------
    args:
        Argument list to pass AFTER "winget", e.g.
        ``["install", "--id", "7zip.7zip", "--silent", "--accept-package-agreements"]``
    timeout:
        Maximum seconds to wait for the process to complete.
        Defaults to WINGET_TIMEOUT_SECONDS from config.

    Returns
    -------
    CommandResult

    Notes
    -----
    - ``shell=False`` is intentional and must never be changed.
    - stdout and stderr are both captured and merged (stderr → stdout).
    - The process is run with ``text=True`` (UTF-8 decoding).
    """
    command = ["winget"] + args
    log.info("Executing command: %s", " ".join(command))

    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout,
            # Do NOT use shell=True — that would allow injection attacks.
            shell=False,
            encoding="utf-8",
            errors="replace",
        )
    except FileNotFoundError:
        msg = (
            "winget executable not found on PATH. "
            "Please ensure 'App Installer' is installed from the Microsoft Store."
        )
        log.error(msg)
        return CommandResult(success=False, returncode=-1, stdout="", error=msg)
    except subprocess.TimeoutExpired:
        msg = f"winget command timed out after {timeout} seconds: {' '.join(command)}"
        log.error(msg)
        return CommandResult(success=False, returncode=-2, stdout="", error=msg)
    except OSError as exc:
        msg = f"OS error while launching winget: {exc}"
        log.error(msg)
        return CommandResult(success=False, returncode=-3, stdout="", error=msg)

    # Merge stdout and stderr for a single output string
    combined_output = (result.stdout or "") + (result.stderr or "")

    # Mask the 32-bit unsigned "already installed" code in Python's signed int
    unsigned_code = result.returncode & 0xFFFFFFFF
    already_installed = unsigned_code == _WINGET_ALREADY_INSTALLED_CODE

    success = result.returncode == 0 or already_installed

    log.info(
        "Command finished — returncode=%d, already_installed=%s, success=%s",
        result.returncode,
        already_installed,
        success,
    )
    log.debug("winget stdout:\n%s", combined_output)

    return CommandResult(
        success=success,
        returncode=result.returncode,
        stdout=combined_output.strip(),
        already_installed=already_installed,
    )
