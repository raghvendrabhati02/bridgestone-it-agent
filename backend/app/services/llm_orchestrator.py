"""
llm_orchestrator.py
─────────────────────────────────────────────────────────────────────────────
Single responsibility: generate free-conversation Gemini responses.

This wrapper exists to:
  • Keep ConversationService free of direct orchestrator_service imports.
  • Make Gemini calls injectable / swappable in tests.
  • Enforce the rule: Gemini only generates text, never drives workflow.

Note: llm_service.py (RAG + intent calls) is NOT modified or replaced.
      This orchestrator wraps orchestrator_service.generate_turn() only.

Design contract:
  • converse() always returns a safe string — never raises.
  • format_general() sanitises the Gemini output before it reaches the UI.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import app.services.conversation_memory as memory
import app.services.orchestrator_service as orchestrator_service
from app.services.response_builder import format_error, format_general

if TYPE_CHECKING:
    from app.services.conversation_service import SessionState

logger = logging.getLogger("it-agent-backend")


class LlmOrchestrator:
    """
    Thin wrapper around orchestrator_service.generate_turn().

    Gemini may only rewrite / explain / summarise / answer general IT questions.
    It may NEVER decide next troubleshooting steps, create tickets, or change state.
    """

    def converse(self, state: "SessionState", message: str) -> str:
        """
        Generate a natural-language response for a free-conversation turn.

        Returns a clean, sanitised response string. Never raises.
        """
        try:
            history = memory.get_history(state.session_id)
            raw = orchestrator_service.generate_turn(
                state.category, history, message
            )
            return format_general(raw)
        except Exception as exc:
            logger.error(
                "LlmOrchestrator: Gemini call failed for session %s: %s",
                state.session_id,
                exc,
            )
            return format_error("Gemini unavailable")

    def converse_with_step(self, state: "SessionState", message: str, step_details: dict) -> str:
        """
        Explain the current KB step or answer user's question, without generating new troubleshooting steps.
        """
        try:
            history = memory.get_history(state.session_id)
            
            primed_instruction = (
                f"CONTEXT: The user is currently on this troubleshooting step:\n"
                f"Step {step_details.get('step')}: {step_details.get('title')}\n"
                f"Instruction: {step_details.get('instruction')}\n\n"
                f"INSTRUCTION: You must ONLY explain this step, rewrite wording, or answer general IT questions. "
                f"You are strictly FORBIDDEN from generating new troubleshooting steps, diagnostic paths, or asking "
                f"troubleshooting questions. Provide a concise explanation or answer."
            )
            
            formatted_message = f"[Instruction: {primed_instruction}]\nUser Message: {message}"
            
            raw = orchestrator_service.generate_turn(
                state.category, history, formatted_message
            )
            return format_general(raw)
        except Exception as exc:
            logger.error(
                "LlmOrchestrator: converse_with_step failed for session %s: %s",
                state.session_id,
                exc,
            )
            return format_error("Gemini unavailable")

