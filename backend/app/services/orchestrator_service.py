"""
orchestrator_service.py
─────────────────────────────────────────────────────────────────────────────
Single responsibility: own all Gemini/AI reasoning for the IT Support chat.

Phase 2 — Agentic Execution Loop:
    Implements the complete Reason → Act → Observe → Respond cycle.

    generate_turn() now:
        1. Calls generate_decision() — Gemini produces a structured JSON decision.
        2. If tool is null or requires_confirmation → returns assistant_message immediately.
        3. If tool is present → calls ToolRouter.route() exactly once.
        4. Passes the ToolRouter result back to Gemini for natural-language synthesis.
        5. Returns the final synthesized response — never raw JSON or tool names.

Public API
──────────
    generate_decision(category, history, user_message) -> dict
        Ask Gemini to produce a structured decision JSON.
        Returns a validated DecisionResult dict — never raises.

    generate_turn(category, history, user_message) -> str
        Full agentic execution loop used by ConversationService.
        Returns the final employee-facing response string — never raises.

DecisionResult format
──────────────────────
    {
        "assistant_message":   str,   # shown to the user on no-tool / confirmation turns
        "intent":              str,   # one of SUPPORTED_INTENTS
        "tool":                str | None,
        "parameters":          dict,
        "confidence":          float, # 0.0 – 1.0
        "requires_confirmation": bool  # if True, return assistant_message and wait
    }

Architecture contract
──────────────────────
- This module is the ONLY place GeminiService is imported.
- This module is the ONLY place PromptBuilder is called.
- This module is the ONLY place ToolRouter is called.
- ConversationService calls generate_turn() and uses the returned string.
- No changes to FastAPI, LangGraph, tickets, handlers, or any other layer.
"""

from __future__ import annotations

import json
import logging
import re
from typing import List

from app.services.gemini_service import GeminiService
from app.services.prompt_builder import build_decision_prompt, build_tool_result_prompt
import app.services.tool_router as tool_router

logger = logging.getLogger("it-agent-backend")

# ─────────────────────────────────────────────────────────────────────────────
# Supported intents — mirrors the values Gemini is instructed to produce.
# ─────────────────────────────────────────────────────────────────────────────
SUPPORTED_INTENTS = {
    "GENERAL_SUPPORT",
    "SEARCH_KNOWLEDGE_BASE",
    "INSTALL_SOFTWARE",
    "RESET_PASSWORD",
    "CHECK_VPN_STATUS",
    "VPN_ACCESS_RESTORE",
    "CHECK_OUTLOOK",
    "CHECK_DEVICE_STATUS",
    "CHECK_DEVICE_HEALTH",
    "RESTART_SERVICE",
    "CREATE_TICKET",
    "ESCALATE_TO_HUMAN",
    "UNKNOWN",
}

# ─────────────────────────────────────────────────────────────────────────────
# Fallback decision returned when Gemini is unreachable or JSON parse fails.
# ─────────────────────────────────────────────────────────────────────────────
def _fallback_decision(category: str, reason: str = "") -> dict:
    import os
    if reason:
        logger.warning("OrchestratorService: using fallback decision — %s", reason)
    
    provider_choice = os.getenv("LLM_PROVIDER", "gemini").strip().lower()
    if provider_choice == "gemini":
        msg = f"System Error: Production AI (Gemini) is unavailable ({reason or 'Connection Error'})."
    else:
        msg = (
            f"I'm looking into your {category} issue. "
            "Could you describe what you're experiencing in a bit more detail, "
            "or would you like me to raise a support ticket?"
        )

    return {
        "assistant_message": msg,
        "intent": "GENERAL_SUPPORT",
        "tool": None,
        "parameters": {},
        "confidence": 0.0,
        "requires_confirmation": False,
        "action_type": "OTHER",
        "escalation_reason": None,
        "_fallback": True,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Module-level GeminiService singleton.
# ─────────────────────────────────────────────────────────────────────────────
_gemini = GeminiService()


# ─────────────────────────────────────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────────────────────────────────────

def _convert_history(history: List[dict]) -> List[dict]:
    """Convert ConversationService history format → GeminiService format."""
    result = []
    for msg in history:
        role = "model" if msg.get("sender") == "agent" else "user"
        text = msg.get("text", "").strip()
        if text:
            result.append({"role": role, "text": text})
    return result


def _extract_json(raw: str) -> dict | None:
    """
    Extract the first JSON object from a Gemini response string.

    Gemini sometimes wraps JSON in markdown fences (```json ... ```) or
    adds leading/trailing prose. This strips all of that.
    Returns None if no valid JSON object is found.
    """
    # 1. Try direct parse first (cleanest case)
    try:
        return json.loads(raw.strip())
    except json.JSONDecodeError:
        pass

    # 2. Strip markdown code fences and retry
    stripped = re.sub(r"```(?:json)?", "", raw, flags=re.IGNORECASE).strip().strip("`").strip()
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        pass

    # 3. Extract the first {...} block with a regex
    match = re.search(r"\{[\s\S]*\}", raw)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass

    return None


def _validate_decision(data: dict) -> dict:
    """
    Normalise and validate a parsed decision dict.

    Enforces required fields, type coercion, and clamps confidence to [0, 1].
    Never raises — fills in safe defaults for any missing or malformed field.
    """
    assistant_message = str(data.get("assistant_message") or "").strip()
    if not assistant_message:
        assistant_message = "I'm here to help. Could you tell me more about the issue?"

    intent = str(data.get("intent") or "UNKNOWN").strip().upper()
    if intent not in SUPPORTED_INTENTS:
        logger.warning(
            "OrchestratorService: unknown intent '%s' returned by Gemini — defaulting to UNKNOWN.",
            intent,
        )
        intent = "UNKNOWN"

    tool = data.get("tool")
    tool = str(tool).strip().upper() if tool else None

    parameters = data.get("parameters")
    if not isinstance(parameters, dict):
        parameters = {}

    try:
        confidence = float(data.get("confidence", 0.0))
        confidence = max(0.0, min(1.0, confidence))
    except (TypeError, ValueError):
        confidence = 0.0

    requires_confirmation = bool(data.get("requires_confirmation", False))

    action_type = data.get("action_type")
    if action_type:
        action_type = str(action_type).strip().upper()
    else:
        action_type = "OTHER"

    escalation_reason = data.get("escalation_reason")
    if escalation_reason:
        escalation_reason = str(escalation_reason).strip().upper()
        if escalation_reason in ("NULL", "NONE"):
            escalation_reason = None
    else:
        escalation_reason = None

    return {
        "assistant_message":   assistant_message,
        "intent":              intent,
        "tool":                tool,
        "parameters":          parameters,
        "confidence":          confidence,
        "requires_confirmation": requires_confirmation,
        "action_type":          action_type,
        "escalation_reason":    escalation_reason,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

def generate_decision(
    category: str,
    history: List[dict],
    user_message: str,
) -> dict:
    """
    Ask Gemini to produce a structured decision for the current conversation turn.

    Parameters
    ----------
    category : str
        Detected IT issue category (e.g. "VPN", "OUTLOOK").
    history : list of {"sender": str, "text": str}
        Full conversation history in ConversationService's internal format.
    user_message : str
        The latest message from the user.

    Returns
    -------
    dict
        A validated DecisionResult dict with keys:
            assistant_message, intent, tool, parameters,
            confidence, requires_confirmation.
        Never raises — returns a fallback decision on any failure.
    """
    if not _gemini.is_ready():
        return _fallback_decision(category, reason="GeminiService not ready")

    gemini_history = _convert_history(history)

    # On the very first turn, embed category context in the user message
    # so Gemini understands the domain without prior history.
    if not gemini_history:
        full_message = f"[Category: {category}] {user_message}"
    else:
        full_message = user_message

    logger.info(
        "OrchestratorService.generate_decision: category=%s history_turns=%d",
        category,
        len(gemini_history),
    )

    from app.services.rag_service import retrieve_context
    kb_context = ""
    try:
        kb_context = retrieve_context(category)
    except Exception as exc:
        logger.warning("OrchestratorService: failed to retrieve RAG context: %s", exc)

    # ── Build the decision-mode system prompt ─────────────────────────────────
    system_prompt = build_decision_prompt(category, kb_context)

    # ── Call GeminiService with the decision prompt as a temporary system override
    # GeminiService.chat() uses its own system_instruction set at init time.
    # For structured-JSON mode we need a different system instruction, so we
    # instantiate a one-shot model call via a fresh GeminiService with
    # the decision prompt injected as the first history turn (system role
    # emulation using the "user" prefixed message pattern).
    # This keeps GeminiService itself unchanged.
    decision_history = [
        {"role": "user",  "text": system_prompt},
        {"role": "model", "text": "Understood. I will respond exclusively with valid JSON in the specified format."},
    ] + gemini_history

    raw_reply = _gemini.chat(user_message=full_message, history=decision_history)

    # ── Handle AI Provider-level errors ─────────────────────────────────────
    if raw_reply.startswith("[AI Provider Error]") or raw_reply.startswith("[GeminiService Error]"):
        return _fallback_decision(category, reason=raw_reply)

    logger.debug(
        "OrchestratorService.generate_decision: raw reply (first 300 chars): %s",
        raw_reply[:300],
    )

    # ── Parse JSON ───────────────────────────────────────────────────────────
    parsed = _extract_json(raw_reply)
    if parsed is None:
        logger.warning(
            "OrchestratorService.generate_decision: JSON parse failed. "
            "Raw reply: %s",
            raw_reply[:500],
        )
        return _fallback_decision(category, reason="JSON parse failed")

    # ── Validate and normalise ────────────────────────────────────────────────
    decision = _validate_decision(parsed)

    logger.info(
        "OrchestratorService.generate_decision: intent=%s tool=%s confidence=%.2f requires_confirmation=%s",
        decision["intent"],
        decision["tool"],
        decision["confidence"],
        decision["requires_confirmation"],
    )

    return decision


def _synthesize_tool_response(tool_result: dict, category: str) -> str:
    """
    Ask Gemini to convert a raw ToolRouter result into a professional,
    employee-facing natural-language response.

    This is the "Observe → Respond" step of the agentic loop.
    The employee never sees JSON, tool names, or status codes.

    Parameters
    ----------
    tool_result : dict
        The dict returned by ToolRouter.route().
        Contains: tool, status (SUCCESS|ERROR|PLACEHOLDER), data, message.
    category : str
        Used in the fallback message if Gemini is unavailable.

    Returns
    -------
    str
        A professional, conversational IT support response.
        Never raises — returns a safe fallback on any error.
    """
    if not _gemini.is_ready():
        return (
            f"Your request has been processed. "
            f"The IT team will follow up on your {category} issue shortly."
        )

    synthesis_prompt = build_tool_result_prompt()

    # Inject synthesis instructions as a primed history so GeminiService
    # is not modified — same pattern as generate_decision().
    synthesis_history = [
        {"role": "user",  "text": synthesis_prompt},
        {"role": "model", "text": "Understood. I will transform the tool result into a professional, natural IT support response without revealing any technical details."},
    ]

    # The user turn is the raw tool result serialised as JSON.
    # Gemini has been instructed (via synthesis_prompt) to transform it into prose.
    tool_result_message = (
        f"Tool: {tool_result.get('tool', 'UNKNOWN')}\n"
        f"Status: {tool_result.get('status', 'UNKNOWN')}\n"
        f"Message: {tool_result.get('message', '')}\n"
        f"Data: {json.dumps(tool_result.get('data', {}))}"
    )

    raw_reply = _gemini.chat(user_message=tool_result_message, history=synthesis_history)
    if raw_reply.startswith("[AI Provider Error]") or raw_reply.startswith("[GeminiService Error]"):
        logger.warning(
            "OrchestratorService._synthesize_tool_response: AI provider error — %s",
            raw_reply,
        )
        # Safe human-readable fallback based on status
        status = tool_result.get("status", "")
        if status == "SUCCESS":
            return "Your request has been submitted successfully. The IT team will follow up shortly."
        elif status == "PLACEHOLDER":
            return "This capability is being prepared and will be available soon. I'll raise a support ticket in the meantime."
        else:
            return "I encountered an issue processing your request. I'll raise a support ticket so the IT team can assist you directly."

    return raw_reply.strip()


def generate_turn(
    category: str,
    history: List[dict],
    user_message: str,
) -> str:
    """
    Full agentic execution loop — the only function ConversationService calls.

    Implements: Reason → Act → Observe → Respond

        Step 1 — Reason  : generate_decision() asks Gemini to produce a
                           structured JSON decision.
        Step 2 — Gate    : if tool is null or requires_confirmation is True,
                           return assistant_message immediately (no tool call).
        Step 3 — Act     : call ToolRouter.route() exactly once with the
                           tool name and parameters from the decision.
        Step 4 — Observe : capture the ToolRouter result dict.
        Step 5 — Respond : pass the tool result to Gemini for synthesis into
                           a professional, employee-facing natural response.

    Parameters
    ----------
    category : str
    history : list of {"sender": str, "text": str}
    user_message : str

    Returns
    -------
    str
        The final employee-facing response. Never raises. Never returns
        raw JSON, tool names, status codes, or internal architecture details.
    """
    # ── Step 1: Reason ────────────────────────────────────────────────────────
    decision = generate_decision(category=category, history=history, user_message=user_message)

    tool_name = decision.get("tool")

    # ── Step 2: Gate — no tool or awaiting confirmation ───────────────────────
    if not tool_name:
        logger.info(
            "OrchestratorService.generate_turn: no tool — returning assistant_message directly."
        )
        return decision["assistant_message"]

    if decision.get("requires_confirmation"):
        logger.info(
            "OrchestratorService.generate_turn: tool=%s requires confirmation — "
            "returning assistant_message and waiting for employee approval.",
            tool_name,
        )
        return decision["assistant_message"]

    # ── Step 3: Act — invoke ToolRouter exactly once ──────────────────────────
    tool_request = {
        "tool":       tool_name,
        "parameters": decision.get("parameters", {}),
    }

    logger.info(
        "OrchestratorService.generate_turn: invoking ToolRouter — tool=%s parameters=%s",
        tool_name,
        list(tool_request["parameters"].keys()),
    )

    try:
        tool_result = tool_router.route(tool_request)
    except Exception as exc:
        logger.error(
            "OrchestratorService.generate_turn: ToolRouter raised unexpectedly — %s",
            exc,
            exc_info=True,
        )
        return (
            "I encountered a technical issue while processing your request. "
            "Please try again or I can raise a support ticket for you."
        )

    logger.info(
        "OrchestratorService.generate_turn: ToolRouter result — tool=%s status=%s",
        tool_result.get("tool"),
        tool_result.get("status"),
    )

    # ── Step 4 & 5: Observe + Respond — synthesize via Gemini ────────────────
    return _synthesize_tool_response(tool_result=tool_result, category=category)
