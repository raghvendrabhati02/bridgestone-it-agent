"""
gemini_service.py
─────────────────────────────────────────────────────────────────────────────
A clean, self-contained wrapper around the active AI provider.
Delegates dynamically to the active provider (GeminiProvider, MockProvider, etc.).
"""

from __future__ import annotations
import logging
from typing import List
from app.services.ai_provider import get_ai_provider

logger = logging.getLogger("it-agent-backend")

class GeminiService:
    def __init__(self, model_name: str | None = None, timeout: float | None = None) -> None:
        self._provider = get_ai_provider()

    def is_ready(self) -> bool:
        """Return True if the service is properly configured and usable."""
        return self._provider.is_ready()

    def chat(
        self,
        user_message: str,
        history: List[dict] | None = None,
    ) -> str:
        """Send a user message to the active provider, optionally supplying prior turns."""
        return self._provider.chat(user_message, history)

    def model_name(self) -> str:
        """Return the active model identifier."""
        if hasattr(self._provider, "_model_name") and self._provider._model_name:
            return self._provider._model_name
        import os
        return os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
