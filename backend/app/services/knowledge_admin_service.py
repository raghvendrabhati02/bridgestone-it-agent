"""
knowledge_admin_service.py
─────────────────────────────────────────────────────────────────────────────
Admin service for Knowledge Base operations (CRUD, versioning, drafting,
publishing, archiving, and screenshot upload).
"""

from __future__ import annotations

import json
import logging
import os
import shutil
from typing import Dict, Any, List, Optional
import app.services.knowledge_service as ks

logger = logging.getLogger("it-agent-backend")

# Versions directory
VERSIONS_DIR: str = os.path.join(ks.KB_DIR, "versions")
# Images directory on backend
IMAGES_DIR: str = os.path.join(ks.KB_DIR, "images")
# Images directory on frontend public
FRONTEND_IMAGES_DIR: str = os.path.abspath(
    os.path.join(ks.KB_DIR, "..", "..", "frontend", "public", "images")
)


def _find_file_by_article_id(article_id: str) -> Optional[str]:
    """Find the path of the JSON file containing article_id."""
    if not os.path.isdir(ks.KB_DIR):
        return None
    for filename in os.listdir(ks.KB_DIR):
        if not filename.endswith(".json"):
            continue
        filepath = os.path.join(ks.KB_DIR, filename)
        try:
            with open(filepath, "r", encoding="utf-8") as fh:
                data = json.load(fh)
                if str(data.get("article_id")).strip() == article_id:
                    return filepath
        except Exception:
            continue
    return None


def list_all_articles() -> List[Dict[str, Any]]:
    """Scan and list all articles from the knowledge base directory (including drafts)."""
    articles = []
    if not os.path.isdir(ks.KB_DIR):
        return []
    for filename in sorted(os.listdir(ks.KB_DIR)):
        if not filename.endswith(".json"):
            continue
        filepath = os.path.join(ks.KB_DIR, filename)
        try:
            with open(filepath, "r", encoding="utf-8") as fh:
                data = json.load(fh)
                articles.append(data)
        except Exception as e:
            logger.warning("Admin KB: Failed to load %s: %s", filename, e)
    return articles


def get_article(article_id: str) -> Optional[Dict[str, Any]]:
    """Fetch article content by article_id."""
    filepath = _find_file_by_article_id(article_id)
    if not filepath:
        return None
    try:
        with open(filepath, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except Exception as e:
        logger.error("Admin KB: Failed to read %s: %s", filepath, e)
        return None


def create_article(article_data: Dict[str, Any]) -> Dict[str, Any]:
    """Generate a new article ID, set defaults as draft v1.0, and save."""
    # Find next article ID (e.g. KB0011)
    all_articles = list_all_articles()
    max_num = 0
    for art in all_articles:
        art_id = art.get("article_id", "")
        if art_id.startswith("KB") and art_id[2:].isdigit():
            try:
                num = int(art_id[2:])
                if num > max_num:
                    max_num = num
            except ValueError:
                pass
    next_id = f"KB{max_num + 1:04d}"

    # Build initial schema matching REQUIRED_FIELDS
    new_article = {
        "article_id": next_id,
        "title": article_data.get("title", "Untitled Article").strip(),
        "category": article_data.get("category", "VPN").upper().strip(),
        "version": "1.0",
        "source": article_data.get("source", "Bridgestone IT Knowledge Base").strip(),
        "status": "draft",
        "keywords": article_data.get("keywords", []),
        "problem": article_data.get("problem", "").strip(),
        "symptoms": article_data.get("symptoms", []),
        "prerequisites": article_data.get("prerequisites", []),
        "troubleshooting_steps": article_data.get("troubleshooting_steps", []),
        "verification": article_data.get("verification", []),
        "common_errors": article_data.get("common_errors", []),
        "escalation": article_data.get("escalation", {
            "after_attempts": 3,
            "team": "IT Support",
            "condition": "Escalate after all steps fail."
        }),
        "screenshots": article_data.get("screenshots", []),
        "faq": article_data.get("faq", []),
        "related_articles": article_data.get("related_articles", [])
    }

    filepath = os.path.join(ks.KB_DIR, f"{next_id}.json")
    with open(filepath, "w", encoding="utf-8") as fh:
        json.dump(new_article, fh, indent=4)

    logger.info("Admin KB: Created draft article %s at %s", next_id, filepath)
    ks.load_articles()  # Triggers re-indexing
    return new_article


def update_article(article_id: str, article_data: Dict[str, Any]) -> Dict[str, Any]:
    """Update existing article fields in the JSON file."""
    filepath = _find_file_by_article_id(article_id)
    if not filepath:
        raise ValueError(f"Article {article_id} not found.")

    with open(filepath, "r", encoding="utf-8") as fh:
        current_data = json.load(fh)

    # Update fields while preserving critical immutable keys if necessary
    for key in ["title", "category", "source", "status", "keywords", "problem", 
                "symptoms", "prerequisites", "troubleshooting_steps", "verification", 
                "common_errors", "escalation", "screenshots", "faq", "related_articles", "version"]:
        if key in article_data:
            if key == "category":
                current_data[key] = str(article_data[key]).upper().strip()
            elif isinstance(article_data[key], str):
                current_data[key] = article_data[key].strip()
            else:
                current_data[key] = article_data[key]

    with open(filepath, "w", encoding="utf-8") as fh:
        json.dump(current_data, fh, indent=4)

    logger.info("Admin KB: Updated article %s", article_id)
    ks.load_articles()
    return current_data


def delete_article(article_id: str) -> bool:
    """Delete the article's JSON file."""
    filepath = _find_file_by_article_id(article_id)
    if not filepath:
        raise ValueError(f"Article {article_id} not found.")
    
    os.remove(filepath)
    logger.info("Admin KB: Deleted article file %s", filepath)
    ks.load_articles()
    return True


def publish_article(article_id: str) -> Dict[str, Any]:
    """Archive current version, increment minor version, set status as published."""
    filepath = _find_file_by_article_id(article_id)
    if not filepath:
        raise ValueError(f"Article {article_id} not found.")

    with open(filepath, "r", encoding="utf-8") as fh:
        article = json.load(fh)

    # 1. Archive version to versions/
    os.makedirs(VERSIONS_DIR, exist_ok=True)
    curr_v = article.get("version", "1.0")
    archive_path = os.path.join(VERSIONS_DIR, f"{article_id}_v{curr_v}.json")
    with open(archive_path, "w", encoding="utf-8") as fh:
        json.dump(article, fh, indent=4)
    logger.info("Admin KB: Archived version %s of %s to %s", curr_v, article_id, archive_path)

    # 2. Increment version (minor version e.g. 1.0 -> 1.1)
    try:
        next_v = f"{float(curr_v) + 0.1:.1f}"
    except ValueError:
        next_v = "1.0"

    article["version"] = next_v
    article["status"] = "published"

    with open(filepath, "w", encoding="utf-8") as fh:
        json.dump(article, fh, indent=4)

    logger.info("Admin KB: Published article %s (version %s)", article_id, next_v)
    ks.load_articles()
    return article


def archive_article(article_id: str) -> Dict[str, Any]:
    """Set status to archived so it is excluded from active chatbot execution."""
    filepath = _find_file_by_article_id(article_id)
    if not filepath:
        raise ValueError(f"Article {article_id} not found.")

    with open(filepath, "r", encoding="utf-8") as fh:
        article = json.load(fh)

    article["status"] = "archived"

    with open(filepath, "w", encoding="utf-8") as fh:
        json.dump(article, fh, indent=4)

    logger.info("Admin KB: Archived active article %s", article_id)
    ks.load_articles()
    return article


def get_version_history(article_id: str) -> List[Dict[str, Any]]:
    """Scan and list all archived versions of article_id."""
    history = []
    if not os.path.isdir(VERSIONS_DIR):
        return []
    for filename in sorted(os.listdir(VERSIONS_DIR)):
        if filename.startswith(f"{article_id}_v") and filename.endswith(".json"):
            filepath = os.path.join(VERSIONS_DIR, filename)
            try:
                # Extract version from filename (e.g. KB0002_v1.0.json -> 1.0)
                v_part = filename[len(article_id)+2:-5]
                # Get file timestamp
                mtime = os.path.getmtime(filepath)
                history.append({
                    "version": v_part,
                    "filename": filename,
                    "timestamp": mtime,
                })
            except Exception:
                continue
    return sorted(history, key=lambda x: x["version"], reverse=True)


def get_version_content(article_id: str, version: str) -> Optional[Dict[str, Any]]:
    """Retrieve raw content of a specific archived version."""
    archive_path = os.path.join(VERSIONS_DIR, f"{article_id}_v{version}.json")
    if not os.path.isfile(archive_path):
        return None
    try:
        with open(archive_path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except Exception as e:
        logger.error("Admin KB: Failed to read version file %s: %s", archive_path, e)
        return None



# ──────────────────────────────────────────────────────────────────────────────
# Upload constants (Phase 4 security hardening)
# ──────────────────────────────────────────────────────────────────────────────
_ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
_MAX_UPLOAD_BYTES = 5 * 1024 * 1024  # 5 MB


def upload_screenshot(article_id: str, filename: str, content: bytes) -> str:
    """
    Save screenshot binary content to both frontend public and backend storage.

    Security (Phase 4):
      • Validates file extension against an image-only allowlist.
      • Enforces a 5 MB maximum file size.
      • Uses os.path.basename() to prevent path traversal in filenames.
      • Applies an alphanumeric slug filter on top of basename.

    Raises:
        ValueError: if the file extension is not allowed or size exceeds limit.
    """
    import os as _os

    # 1. Size guard (before any I/O)
    if len(content) > _MAX_UPLOAD_BYTES:
        raise ValueError(
            f"File size {len(content):,} bytes exceeds the maximum allowed "
            f"{_MAX_UPLOAD_BYTES // (1024 * 1024)} MB."
        )

    # 2. Path traversal guard — extract bare filename
    safe_basename = _os.path.basename(filename)

    # 3. Extension allowlist check
    _, ext = _os.path.splitext(safe_basename.lower())
    if ext not in _ALLOWED_IMAGE_EXTENSIONS:
        raise ValueError(
            f"File type '{ext}' is not allowed. Permitted types: "
            f"{', '.join(sorted(_ALLOWED_IMAGE_EXTENSIONS))}."
        )

    # 4. Character-level slug sanitisation (alphanumeric + safe punctuation)
    safe_filename = "".join(
        [c if c.isalnum() or c in (".", "_", "-") else "_" for c in safe_basename]
    )
    if not safe_filename or safe_filename.startswith("."):
        safe_filename = f"upload_{article_id}{ext}"

    # 5. Save to frontend public/images/
    try:
        os.makedirs(FRONTEND_IMAGES_DIR, exist_ok=True)
        frontend_path = os.path.join(FRONTEND_IMAGES_DIR, safe_filename)
        with open(frontend_path, "wb") as f:
            f.write(content)
        logger.info("Admin KB: Saved screenshot to frontend path: %s", frontend_path)
    except Exception as e:
        logger.warning("Admin KB: Failed to save to frontend directory: %s", e)

    # 6. Save to backend knowledge_base/images/
    os.makedirs(IMAGES_DIR, exist_ok=True)
    backend_path = os.path.join(IMAGES_DIR, safe_filename)
    with open(backend_path, "wb") as f:
        f.write(content)
    logger.info("Admin KB: Saved screenshot to backend path: %s", backend_path)

    return safe_filename
