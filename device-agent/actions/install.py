"""
actions/install.py
-------------------
Handles software installation via winget.

Workflow
--------
1. Look up the slug in the approved software catalog.
2. Reject immediately if not found.
3. Warn (but allow) if the entry is marked ``approval_required`` — future
   phases will block here until a manager approves the request.
4. Run:
       winget install --id <winget_id> --silent
                      --accept-package-agreements
                      --accept-source-agreements
5. Return a SoftwareActionResponse describing the outcome.

Public function
---------------
    run(slug: str) -> SoftwareActionResponse
"""

from models.response_models import SoftwareActionResponse
from services import command_executor, software_catalog
from utils.logger import get_logger

log = get_logger(__name__)


def run(slug: str) -> SoftwareActionResponse:
    """
    Install a software package by its catalog slug.

    Parameters
    ----------
    slug:
        Normalised lowercase slug from the request body (e.g. "7zip").

    Returns
    -------
    SoftwareActionResponse
        status will be one of:
          - "rejected"          — slug not in the approved catalog
          - "installed"         — winget succeeded (returncode 0)
          - "already_installed" — winget reported the package is already present
          - "failed"            — winget exited with a non-zero code
    """
    log.info("Install requested — slug='%s'", slug)

    # ------------------------------------------------------------------
    # Step 1 — Catalog look-up (safety gate)
    # ------------------------------------------------------------------
    entry = software_catalog.get_entry(slug)
    if entry is None:
        approved = software_catalog.all_approved_slugs()
        msg = (
            f"'{slug}' is not in the approved software catalog and cannot be installed. "
            f"Approved slugs: {approved}"
        )
        log.warning("REJECTED install request — %s", msg)
        return SoftwareActionResponse(
            software=slug,
            winget_id=None,
            status="rejected",
            message=msg,
        )

    # ------------------------------------------------------------------
    # Step 2 — Approval flag check (Phase 1: log only)
    # ------------------------------------------------------------------
    if entry.approval_required:
        log.warning(
            "Package '%s' (%s) is flagged as approval_required. "
            "Proceeding in Phase 1 — future phases will block here.",
            entry.slug,
            entry.winget_id,
        )

    # ------------------------------------------------------------------
    # Step 3 — Execute winget install
    # ------------------------------------------------------------------
    log.info(
        "Installing '%s' (winget_id=%s)", entry.name, entry.winget_id
    )

    result = command_executor.run_winget(
        [
            "install",
            "--id", entry.winget_id,
            "--silent",
            "--accept-package-agreements",
            "--accept-source-agreements",
        ]
    )

    # ------------------------------------------------------------------
    # Step 4 — Interpret result
    # ------------------------------------------------------------------
    if result.error:
        # The command could not even be launched (e.g. winget not on PATH)
        return SoftwareActionResponse(
            software=slug,
            winget_id=entry.winget_id,
            status="failed",
            message=result.error,
            returncode=result.returncode,
        )

    if result.already_installed:
        msg = f"'{entry.name}' is already installed on this device."
        log.info(msg)
        return SoftwareActionResponse(
            software=slug,
            winget_id=entry.winget_id,
            status="already_installed",
            message=msg,
            stdout=result.stdout,
            returncode=result.returncode,
        )

    if result.success:
        msg = f"'{entry.name}' was installed successfully."
        log.info(msg)
        return SoftwareActionResponse(
            software=slug,
            winget_id=entry.winget_id,
            status="installed",
            message=msg,
            stdout=result.stdout,
            returncode=result.returncode,
        )

    # Non-zero exit from winget — installation failed
    msg = (
        f"Installation of '{entry.name}' failed. "
        f"winget exited with code {result.returncode}. "
        "Check the log file for the full winget output."
    )
    log.error(msg)
    return SoftwareActionResponse(
        software=slug,
        winget_id=entry.winget_id,
        status="failed",
        message=msg,
        stdout=result.stdout,
        returncode=result.returncode,
    )
