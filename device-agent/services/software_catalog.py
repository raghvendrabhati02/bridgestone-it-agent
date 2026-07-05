"""
services/software_catalog.py
------------------------------
Loads and exposes the approved software catalog from software_catalog.json.

Design principles
-----------------
- The catalog is read from disk exactly once (at module import time) and
  cached in memory for the lifetime of the process.
- All look-ups are case-insensitive on the slug field.
- If the catalog file is missing or malformed the process exits immediately
  with a clear error — there is no safe fallback that would allow arbitrary
  software installs.

Catalog entry schema (JSON)
----------------------------
{
  "name":              "7-Zip",          # Human-readable display name
  "slug":              "7zip",           # Short, lowercase lookup key
  "winget_id":         "7zip.7zip",      # Exact winget package identifier
  "approval_required": false             # Reserved for future approval flow
}
"""

import json
import sys
from pathlib import Path
from typing import Optional

from config import SOFTWARE_CATALOG_PATH
from utils.logger import get_logger

log = get_logger(__name__)


# ---------------------------------------------------------------------------
# Internal catalog representation
# ---------------------------------------------------------------------------


class CatalogEntry:
    """
    Lightweight wrapper around a single catalog record.

    Attributes
    ----------
    name:
        Human-readable name (e.g. "7-Zip").
    slug:
        Lowercase look-up key (e.g. "7zip").
    winget_id:
        Exact winget package identifier (e.g. "7zip.7zip").
    approval_required:
        When True, the install endpoint should (in future phases) block until
        a manager approves the request. Phase 1 logs a warning but proceeds.
    """

    __slots__ = ("name", "slug", "winget_id", "approval_required")

    def __init__(self, record: dict) -> None:
        self.name: str = record["name"]
        self.slug: str = record["slug"].strip().lower()
        self.winget_id: str = record["winget_id"]
        self.approval_required: bool = bool(record.get("approval_required", False))

    def __repr__(self) -> str:
        return (
            f"CatalogEntry(slug={self.slug!r}, winget_id={self.winget_id!r}, "
            f"approval_required={self.approval_required})"
        )


# ---------------------------------------------------------------------------
# Catalog loading
# ---------------------------------------------------------------------------


def _load_catalog(path: Path) -> dict[str, CatalogEntry]:
    """
    Read software_catalog.json and return a slug → CatalogEntry mapping.

    Raises SystemExit if the file is missing or cannot be parsed, because
    running without a valid catalog would be unsafe.

    Parameters
    ----------
    path:
        Absolute path to software_catalog.json.

    Returns
    -------
    dict[str, CatalogEntry]
        Keys are lowercase slugs; values are CatalogEntry objects.
    """
    if not path.exists():
        log.critical(
            "Software catalog not found at '%s'. "
            "The Device Agent cannot start without an approved software list.",
            path,
        )
        sys.exit(1)

    try:
        raw = path.read_text(encoding="utf-8")
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        log.critical(
            "Failed to parse software catalog at '%s': %s", path, exc
        )
        sys.exit(1)

    entries: dict[str, CatalogEntry] = {}
    for record in data.get("approved_software", []):
        try:
            entry = CatalogEntry(record)
            entries[entry.slug] = entry
        except KeyError as exc:
            log.warning(
                "Skipping malformed catalog record (missing key %s): %s",
                exc,
                record,
            )

    log.info(
        "Software catalog loaded: %d approved packages — %s",
        len(entries),
        list(entries.keys()),
    )
    return entries


# ---------------------------------------------------------------------------
# Module-level singleton — loaded once at import time
# ---------------------------------------------------------------------------

_CATALOG: dict[str, CatalogEntry] = _load_catalog(SOFTWARE_CATALOG_PATH)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def get_entry(slug: str) -> Optional[CatalogEntry]:
    """
    Return the CatalogEntry for a given slug, or None if not approved.

    Parameters
    ----------
    slug:
        Case-insensitive software slug (e.g. "7zip", "VLC").

    Returns
    -------
    CatalogEntry | None
    """
    return _CATALOG.get(slug.strip().lower())


def is_approved(slug: str) -> bool:
    """
    Return True if the slug exists in the approved catalog.

    Parameters
    ----------
    slug:
        Case-insensitive software slug.
    """
    return get_entry(slug) is not None


def all_approved_slugs() -> list[str]:
    """Return a sorted list of all approved software slugs."""
    return sorted(_CATALOG.keys())
