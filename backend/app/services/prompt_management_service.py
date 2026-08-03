"""
prompt_management_service.py
──────────────────────────────────────────────────────────────────────────────
Sprint 10: Admin Prompt Management Service

Allows administrators to:
  - View prompts
  - Edit prompts
  - Create prompt versions
  - Restore previous versions
  - Preview prompts
  - Maintain prompt history
"""

from __future__ import annotations

import datetime
import json
import os
import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger("it-agent-backend")

_PROMPT_STORAGE_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "knowledge_base",
    "prompt_store.json"
)

DEFAULT_PROMPTS = {
    "BASE_SYSTEM_PROMPT": {
        "key": "BASE_SYSTEM_PROMPT",
        "name": "Base Universal System Prompt",
        "description": "Core instructions for Bridgestone IT Assistant persona and protocol",
        "version": "1.0",
        "content": (
            "You are the Bridgestone IT Support Assistant, a professional conversational AI "
            "designed to troubleshoot IT issues, guide employees, and manage ServiceNow incidents."
        ),
        "updated_at": datetime.datetime.utcnow().isoformat() + "Z",
        "updated_by": "system"
    },
    "CLASSIFICATION_PROMPT": {
        "key": "CLASSIFICATION_PROMPT",
        "name": "ITSM Classification Prompt",
        "description": "Instructions for categorizing issues into INCIDENT, SERVICE_REQUEST, or PRIVILEGED_ACTION",
        "version": "1.0",
        "content": "Classify the user ticket into Category, Urgency, Impact, and Request Type.",
        "updated_at": datetime.datetime.utcnow().isoformat() + "Z",
        "updated_by": "system"
    }
}

_PROMPT_HISTORY: Dict[str, List[Dict[str, Any]]] = {}


def _load_prompts() -> Dict[str, Dict[str, Any]]:
    if os.path.exists(_PROMPT_STORAGE_FILE):
        try:
            with open(_PROMPT_STORAGE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error("PromptManagementService: Failed to read prompt store: %s", e)
    return DEFAULT_PROMPTS.copy()


def _save_prompts(data: Dict[str, Dict[str, Any]]) -> None:
    os.makedirs(os.path.dirname(_PROMPT_STORAGE_FILE), exist_ok=True)
    with open(_PROMPT_STORAGE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def get_all_prompts() -> List[Dict[str, Any]]:
    """Returns list of active system prompts."""
    prompts = _load_prompts()
    return list(prompts.values())


def get_prompt_by_key(prompt_key: str) -> Optional[Dict[str, Any]]:
    """Returns details of a specific prompt key."""
    prompts = _load_prompts()
    return prompts.get(prompt_key)


def update_prompt(prompt_key: str, content: str, updated_by: str = "admin") -> Dict[str, Any]:
    """
    Updates a prompt, creating a new version entry and saving history snapshot.
    """
    prompts = _load_prompts()
    current = prompts.get(prompt_key)
    if not current:
        current = {
            "key": prompt_key,
            "name": prompt_key,
            "description": f"System prompt for {prompt_key}",
            "version": "1.0",
            "content": content,
            "updated_at": datetime.datetime.utcnow().isoformat() + "Z",
            "updated_by": updated_by
        }
    else:
        # Save snapshot into history
        if prompt_key not in _PROMPT_HISTORY:
            _PROMPT_HISTORY[prompt_key] = []
        _PROMPT_HISTORY[prompt_key].append(current.copy())

        # Increment version
        try:
            major, minor = current.get("version", "1.0").split(".")
            new_version = f"{major}.{int(minor) + 1}"
        except Exception:
            new_version = "1.1"

        current["version"] = new_version
        current["content"] = content
        current["updated_at"] = datetime.datetime.utcnow().isoformat() + "Z"
        current["updated_by"] = updated_by

    prompts[prompt_key] = current
    _save_prompts(prompts)
    logger.info("PromptManagementService: Updated prompt '%s' to version %s", prompt_key, current["version"])
    return current


def get_prompt_history(prompt_key: str) -> List[Dict[str, Any]]:
    """Returns version history list for a prompt key."""
    history = _PROMPT_HISTORY.get(prompt_key, [])
    current = get_prompt_by_key(prompt_key)
    res = list(history)
    if current and current not in res:
        res.append(current)
    return res


def restore_prompt_version(prompt_key: str, version: str, restored_by: str = "admin") -> Optional[Dict[str, Any]]:
    """Restores a previous version of a prompt."""
    history = _PROMPT_HISTORY.get(prompt_key, [])
    for entry in history:
        if entry.get("version") == version:
            return update_prompt(prompt_key, entry["content"], updated_by=restored_by)
    return None


def preview_prompt(prompt_key: str, sample_vars: Dict[str, str] = None) -> str:
    """Previews prompt with variable substitutions."""
    p = get_prompt_by_key(prompt_key)
    if not p:
        return ""
    content = p["content"]
    if sample_vars:
        for k, v in sample_vars.items():
            content = content.replace(f"{{{k}}}", str(v))
    return content
