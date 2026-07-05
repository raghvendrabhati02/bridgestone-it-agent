"""
actions/uninstall.py
---------------------
Reserved for Phase 2 — software removal via winget.

Phase 1 does NOT expose an uninstall endpoint.
This file is a placeholder that documents the intended design so the
implementation can be added without touching any other module.

Public function (not yet wired to a route)
-------------------------------------------
    run(slug: str) -> SoftwareActionResponse
"""

from models.response_models import SoftwareActionResponse
from utils.logger import get_logger

log = get_logger(__name__)


def run(slug: str) -> SoftwareActionResponse:
    """
    Uninstall a software package by its catalog slug.

    .. note::
        This function is **not connected to any API route in Phase 1**.
        It will be wired to ``DELETE /uninstall-software`` in Phase 2.

    Parameters
    ----------
    slug:
        Normalised lowercase slug (e.g. "7zip").

    Returns
    -------
    SoftwareActionResponse
        Always returns status="not_implemented" in Phase 1.
    """
    log.warning(
        "Uninstall requested for slug='%s' — uninstall is not implemented in Phase 1.",
        slug,
    )
    return SoftwareActionResponse(
        software=slug,
        winget_id=None,
        status="not_implemented",
        message=(
            "Uninstall is reserved for Phase 2 and is not available in this release."
        ),
    )
