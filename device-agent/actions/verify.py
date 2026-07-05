"""
actions/verify.py
------------------
Checks whether a software package is currently installed on the device.

Strategy
--------
Runs ``winget list --id <winget_id>`` and inspects the output.

  - If winget outputs a table row that contains the package ID → Installed
  - If the output contains "No installed package found"    → Not Installed
  - If winget itself cannot be found or errors             → Failed

Public function
---------------
    run(slug: str) -> SoftwareActionResponse
"""

from models.response_models import SoftwareActionResponse
from services import command_executor, software_catalog
from utils.logger import get_logger

log = get_logger(__name__)

# Strings winget outputs when no package matches the filter
_NOT_FOUND_MARKERS = [
    "no installed package found",
    "no package found",
    "0 packages",
]


def _is_installed_in_output(winget_id: str, output: str) -> bool:
    """
    Heuristic check: does the winget list output contain the package ID?

    winget list --id returns a table like:

        Name   Id              Version  Source
        -----  --------------  -------  ------
        7-Zip  7zip.7zip       24.06.0  winget

    We look for the winget_id string anywhere in the output, case-insensitively.
    We also check for the common "not found" messages so we don't falsely
    report an install when winget errors out.

    Parameters
    ----------
    winget_id:
        The exact catalog winget ID (e.g. "7zip.7zip").
    output:
        Combined stdout + stderr from the winget list command.

    Returns
    -------
    bool
    """
    lower_output = output.lower()

    # Explicit "not found" from winget → definitely not installed
    for marker in _NOT_FOUND_MARKERS:
        if marker in lower_output:
            return False

    # If the winget_id appears in the output → installed
    return winget_id.lower() in lower_output


def run(slug: str) -> SoftwareActionResponse:
    """
    Verify whether a package is installed on the local device.

    Parameters
    ----------
    slug:
        Normalised lowercase slug from the request body (e.g. "7zip").

    Returns
    -------
    SoftwareActionResponse
        status will be one of:
          - "rejected"       — slug not in the approved catalog
          - "installed"      — the package is present on the device
          - "not_installed"  — the package was not found
          - "failed"         — winget could not be executed
    """
    log.info("Verify requested — slug='%s'", slug)

    # ------------------------------------------------------------------
    # Catalog safety gate — identical to install.py
    # ------------------------------------------------------------------
    entry = software_catalog.get_entry(slug)
    if entry is None:
        approved = software_catalog.all_approved_slugs()
        msg = (
            f"'{slug}' is not in the approved software catalog. "
            f"Approved slugs: {approved}"
        )
        log.warning("REJECTED verify request — %s", msg)
        return SoftwareActionResponse(
            software=slug,
            winget_id=None,
            status="rejected",
            message=msg,
        )

    # ------------------------------------------------------------------
    # Execute: winget list --id <winget_id> --exact
    # ------------------------------------------------------------------
    log.info(
        "Verifying installation of '%s' (winget_id=%s)", entry.name, entry.winget_id
    )

    result = command_executor.run_winget(
        [
            "list",
            "--id", entry.winget_id,
            "--exact",
            "--accept-source-agreements",
        ]
    )

    # ------------------------------------------------------------------
    # Interpret result
    # ------------------------------------------------------------------
    if result.error:
        return SoftwareActionResponse(
            software=slug,
            winget_id=entry.winget_id,
            status="failed",
            message=result.error,
            returncode=result.returncode,
        )

    installed = _is_installed_in_output(entry.winget_id, result.stdout)

    if installed:
        msg = f"'{entry.name}' is installed on this device."
        log.info(msg)
        return SoftwareActionResponse(
            software=slug,
            winget_id=entry.winget_id,
            status="installed",
            message=msg,
            stdout=result.stdout,
            returncode=result.returncode,
        )

    msg = f"'{entry.name}' is NOT installed on this device."
    log.info(msg)
    return SoftwareActionResponse(
        software=slug,
        winget_id=entry.winget_id,
        status="not_installed",
        message=msg,
        stdout=result.stdout,
        returncode=result.returncode,
    )
