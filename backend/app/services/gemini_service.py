"""
gemini_service.py
─────────────────────────────────────────────────────────────────────────────
A clean, self-contained wrapper around the Google Generative AI SDK that
supports multi-turn conversation history.

Responsibilities (this phase):
  • Read GEMINI_API_KEY and GEMINI_MODEL from environment / .env
  • Accept a list of prior conversation turns + the latest user message
  • Return Gemini's text response

Out of scope (deliberately NOT included here):
  • Tool calling / function declarations
  • Business logic (ticket creation, endpoint execution, policy checks)
  • RAG context injection  →  handled separately in llm_service.py
  • LangGraph integration  →  handled separately in the agents layer

Usage:
    from app.services.gemini_service import GeminiService

    svc = GeminiService()
    reply = svc.chat(
        history=[
            {"role": "user",  "text": "My VPN isn't connecting."},
            {"role": "model", "text": "I can help with that. Are you at the office or working remotely?"},
        ],
        user_message="I'm working from home and getting error 0x800704cf.",
    )
"""

from __future__ import annotations

import logging
import os
from typing import List

import google.generativeai as genai
from dotenv import load_dotenv

logger = logging.getLogger("it-agent-backend")

# ─────────────────────────────────────────────────────────────────────────────
# Environment bootstrap
# Attempt standard load first; fall back to the path relative to this file
# so the service works whether uvicorn is launched from /backend or /app.
# ─────────────────────────────────────────────────────────────────────────────
load_dotenv()

if not os.getenv("GEMINI_API_KEY"):
    _env_path = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "..", ".env")
    )
    load_dotenv(dotenv_path=_env_path)

# ─────────────────────────────────────────────────────────────────────────────
# Type alias: a single conversation turn
#   role  → "user" | "model"
#   text  → message content
# ─────────────────────────────────────────────────────────────────────────────
ConversationTurn = dict  # {"role": str, "text": str}


# ─────────────────────────────────────────────────────────────────────────────
# GeminiService
# ─────────────────────────────────────────────────────────────────────────────
class GeminiService:
    """
    Thin wrapper around google-generativeai that adds:
      - Environment-driven configuration (API key, model name)
      - Multi-turn conversation support via model.start_chat()
      - Structured error handling that never raises to the caller
      - Request timeout guard (default 30 s)
    """

    DEFAULT_MODEL   = "gemini-2.5-flash-lite"
    DEFAULT_TIMEOUT = 30.0  # seconds

    # System instruction injected into every chat session.
    # Keep it minimal here; agents/prompts add domain-specific context.
    SYSTEM_INSTRUCTION = (
        "You are Bridgestone IT Assistant — a professional, concise AI IT support agent "
        "helping Bridgestone employees resolve technology problems. "
        "Always respond in plain English. Never include internal chain-of-thought. "
        "If you cannot resolve an issue, say so clearly."
    )

    def __init__(self, model_name: str | None = None, timeout: float | None = None) -> None:
        self._api_key   = os.getenv("GEMINI_API_KEY", "")
        self._model_name = (
            model_name
            or os.getenv("GEMINI_MODEL", self.DEFAULT_MODEL)
        )
        self._timeout = timeout or self.DEFAULT_TIMEOUT
        self._ready   = False

        if not self._api_key:
            logger.error(
                "GeminiService: GEMINI_API_KEY is not set. "
                "Add it to backend/.env before using this service."
            )
            return

        try:
            genai.configure(api_key=self._api_key)
            self._ready = True
            logger.info(
                "GeminiService: Initialised. Model=%s Timeout=%.1fs",
                self._model_name,
                self._timeout,
            )
        except Exception as exc:
            logger.error("GeminiService: SDK configuration failed: %s", exc)

    # ─────────────────────────────────────────────────────────────────────
    # Public API
    # ─────────────────────────────────────────────────────────────────────

    def chat(
        self,
        user_message: str,
        history: List[ConversationTurn] | None = None,
    ) -> str:
        """
        Send a user message to Gemini, optionally supplying prior turns.

        Parameters
        ----------
        user_message : str
            The latest message from the user.
        history : list of {"role": str, "text": str}, optional
            Prior conversation turns in chronological order.
            Roles must be "user" or "model".

        Returns
        -------
        str
            Gemini's text response, or a human-readable error string prefixed
            with "[GeminiService Error]" so callers can detect failures.
        """
        if not self._ready:
            return (
                "[GeminiService Error] Service is not initialised. "
                "Check that GEMINI_API_KEY is set in backend/.env."
            )

        if not user_message or not user_message.strip():
            return "[GeminiService Error] user_message must not be empty."

        history = history or []

        try:
            model = genai.GenerativeModel(
                model_name=self._model_name,
                system_instruction=self.SYSTEM_INSTRUCTION,
            )

            # Convert our simple dict format to the Content objects Gemini expects.
            # The SDK also accepts plain dicts with "role" and "parts" keys.
            gemini_history = [
                {"role": turn["role"], "parts": [turn["text"]]}
                for turn in history
                if turn.get("role") in ("user", "model") and turn.get("text")
            ]

            chat_session = model.start_chat(history=gemini_history)

            logger.debug(
                "GeminiService.chat: sending message (history_turns=%d): %r",
                len(gemini_history),
                user_message[:120],
            )

            response = chat_session.send_message(
                user_message,
                request_options={"timeout": self._timeout},
            )

            if not response or not response.text:
                logger.warning("GeminiService: Received empty response from Gemini.")
                return "[GeminiService Error] Gemini returned an empty response."

            reply = response.text.strip()
            logger.debug("GeminiService.chat: response: %r", reply[:120])
            return reply

        except Exception as exc:
            error_str = str(exc)
            logger.error(
                "GeminiService.chat: Exception during Gemini call: %s",
                error_str,
                exc_info=True,
            )
            # Surface a clean error string — callers decide how to handle it
            return f"[GeminiService Error] {error_str}"

    def is_ready(self) -> bool:
        """Return True if the service is properly configured and usable."""
        return self._ready

    def model_name(self) -> str:
        """Return the active Gemini model identifier."""
        return self._model_name
