"""
ticket_summary_service.py
──────────────────────────────────────────────────────────────────────────────
Enterprise AI-Powered Ticket Summary Generation Service for ServiceNow.

Responsibilities
----------------
• Build a structured, facts-only TicketSummaryContext from session state and history.
• Prompt the AI Provider (Gemini) to format the context into a professional,
  engineer-style ServiceNow incident summary.
• Validate every generated summary via a strict Anti-Hallucination Verification Engine.
• Fall back to a deterministic summary if LLM generation or verification fails.
• Never raise an exception — ticket creation must never fail due to summary generation.

Data Contracts
--------------
  • TicketSummaryContext: Facts-only structured object extracted from conversation.
  • TicketSummary: Short description (<=120 chars) and structured description (<=2000 chars)
    plus metadata (confidence, used_fallback, source, keywords, affected_service, etc.).
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from app.core.tracing import trace_span
from app.core.logging_context import correlation_id_ctx

logger = logging.getLogger("it-agent-backend")

_SHORT_DESC_MAX_LEN = 120
_DESC_MAX_LEN = 2000
_ERROR_CODE_REGEX = re.compile(
    r"\b(error\s*\d+|code\s*\d+|0x[0-9a-fA-F]+|ERR_[A-Z0-9_]+)\b",
    re.IGNORECASE,
)
_GENERIC_BAD_PHRASES = re.compile(
    r"^(hi|hello|my issue|need help|problem|laptop|help|support|ticket|issue)$",
    re.IGNORECASE,
)


# ── Data Contracts ────────────────────────────────────────────────────────────

@dataclass
class TicketSummaryContext:
    """Structured, facts-only context extracted before calling LLM or fallback."""
    issue: str
    category: str
    symptoms: List[str]                  = field(default_factory=list)
    troubleshooting_performed: List[str]  = field(default_factory=list)
    error_codes: List[str]                = field(default_factory=list)
    observed_results: List[str]           = field(default_factory=list)
    user_answers: Dict[str, str]          = field(default_factory=dict)
    resolution_status: str               = "UNRESOLVED"


@dataclass
class TicketSummary:
    """Intelligent summary output consumed by TicketService for ServiceNow POST."""
    short_description: str
    description: str
    confidence: float                    = 0.90
    used_fallback: bool                  = False
    source: str                          = "gemini"  # "gemini" | "deterministic"

    # Reserved enterprise fields for future ServiceNow integration
    keywords: List[str]                  = field(default_factory=list)
    affected_service: Optional[str]      = None
    probable_root_cause: Optional[str]   = None


# ── 1. Structured Context Builder ─────────────────────────────────────────────

class TicketSummaryContextBuilder:
    """Extracts a deterministic, facts-only TicketSummaryContext from conversation artifacts."""

    @staticmethod
    def build_context(
        conversation_history: List[Dict[str, Any]],
        troubleshooting_state: Optional[Any] = None,
        classification: Optional[Any] = None,
    ) -> TicketSummaryContext:
        category = "General IT"
        if classification and getattr(classification, "category", None):
            category = str(classification.category)
        elif troubleshooting_state and getattr(troubleshooting_state, "strategy_domain", None):
            category = str(troubleshooting_state.strategy_domain).replace("_", " ").title()

        # Issue extraction
        issue = "IT Support Request"
        if troubleshooting_state and getattr(troubleshooting_state, "current_issue", None):
            issue = str(troubleshooting_state.current_issue)
        elif classification and getattr(classification, "subcategory", None):
            issue = str(classification.subcategory)
        else:
            # First user message
            user_msgs = [
                m.get("text", "") for m in conversation_history
                if m.get("sender") == "user" or m.get("role") == "user"
            ]
            if user_msgs:
                issue = user_msgs[0].strip()

        # Symptoms
        symptoms: List[str] = []
        user_msgs = [
            m.get("text", "").strip() for m in conversation_history
            if (m.get("sender") == "user" or m.get("role") == "user") and m.get("text")
        ]
        for msg in user_msgs:
            if not _GENERIC_BAD_PHRASES.match(msg) and msg.lower() not in ("yes", "no", "ok", "sure", "done", "fixed"):
                if msg not in symptoms:
                    symptoms.append(msg)

        if not symptoms and issue:
            symptoms.append(issue)

        # Troubleshooting performed
        steps_performed: List[str] = []
        if troubleshooting_state:
            completed = getattr(troubleshooting_state, "completed_steps", [])
            for step in completed:
                instr = getattr(step, "instruction", str(step)) if not isinstance(step, str) else step
                if instr and instr not in steps_performed:
                    steps_performed.append(instr)

            attempted = getattr(troubleshooting_state, "attempted_actions", [])
            for act in attempted:
                if act and act not in steps_performed:
                    steps_performed.append(act)

        # Scan conversation for suggested/tried steps if state steps are empty
        if not steps_performed:
            agent_msgs = [
                m.get("text", "").strip() for m in conversation_history
                if (m.get("sender") in ("agent", "model", "assistant") or m.get("role") in ("model", "assistant"))
            ]
            for msg in agent_msgs:
                # Look for step indicators or bullet lines
                for line in msg.split("\n"):
                    line_clean = line.strip()
                    if line_clean.startswith(("1.", "2.", "3.", "4.", "5.", "•", "-", "*", "Step", "Try", "Please")):
                        clean_step = re.sub(r"^[0-9\.\•\-\*\s]+", "", line_clean).strip()
                        if len(clean_step) > 8 and clean_step not in steps_performed:
                            steps_performed.append(clean_step)

            # Fallback: if still empty, include non-initial agent turns as guidance offered
            if not steps_performed and len(agent_msgs) > 0:
                for msg in agent_msgs[1:]:
                    first_sentence = msg.split(". ")[0].strip()
                    if len(first_sentence) > 10 and first_sentence not in steps_performed:
                        steps_performed.append(first_sentence)

        # Error codes
        error_codes: List[str] = []
        if troubleshooting_state and getattr(troubleshooting_state, "error_codes", None):
            error_codes = list(troubleshooting_state.error_codes)

        # Scan user messages for error codes if state has none
        raw_full_text = " ".join(user_msgs)
        for match in _ERROR_CODE_REGEX.finditer(raw_full_text):
            code_found = match.group(0).upper()
            if code_found not in error_codes:
                error_codes.append(code_found)

        # User answers & status
        user_answers: Dict[str, str] = {}
        resolution_status = "UNRESOLVED"
        if troubleshooting_state:
            if getattr(troubleshooting_state, "user_answers", None):
                user_answers = dict(troubleshooting_state.user_answers)
            if getattr(troubleshooting_state, "resolution_status", None):
                res = troubleshooting_state.resolution_status
                resolution_status = res.value if hasattr(res, "value") else str(res)

        return TicketSummaryContext(
            issue=issue,
            category=category,
            symptoms=symptoms,
            troubleshooting_performed=steps_performed,
            error_codes=error_codes,
            observed_results=getattr(troubleshooting_state, "observed_results", []) if troubleshooting_state else [],
            user_answers=user_answers,
            resolution_status=resolution_status,
        )


# ── 2. Verification Engine (Anti-Hallucination Guard) ──────────────────────────

class VerificationEngine:
    """Validates candidate summaries against raw history and structured context."""

    @staticmethod
    def verify(
        summary: TicketSummary,
        context: TicketSummaryContext,
        conversation_history: List[Dict[str, Any]],
    ) -> bool:
        # 1. Length constraints
        if not summary.short_description or len(summary.short_description) > _SHORT_DESC_MAX_LEN:
            logger.warning(
                "[VerificationEngine]: Rejected summary — short_description length %d exceeds max %d",
                len(summary.short_description or ""), _SHORT_DESC_MAX_LEN,
            )
            return False

        if not summary.description or len(summary.description) > _DESC_MAX_LEN:
            logger.warning(
                "[VerificationEngine]: Rejected summary — description length %d exceeds max %d",
                len(summary.description or ""), _DESC_MAX_LEN,
            )
            return False

        # 2. Quality of short description
        sd_clean = summary.short_description.strip()
        if _GENERIC_BAD_PHRASES.match(sd_clean) or len(sd_clean) < 6:
            logger.warning(
                "[VerificationEngine]: Rejected summary — short_description '%s' is generic or too short",
                sd_clean,
            )
            return False

        # Build full raw conversation text for verification
        all_texts = [
            str(m.get("text", "")) for m in conversation_history if m.get("text")
        ]
        raw_text = " ".join(all_texts).upper()
        known_codes = [c.upper() for c in context.error_codes]

        # 3. Anti-hallucination check: Error codes
        combined_summary = (summary.short_description + " " + summary.description).upper()
        for match in _ERROR_CODE_REGEX.finditer(combined_summary):
            code_mentioned = match.group(0).upper()
            # If code is mentioned in summary, it MUST exist in context error_codes or raw history
            if code_mentioned not in known_codes and code_mentioned not in raw_text:
                logger.warning(
                    "[VerificationEngine]: Rejected summary — hallucinated error code '%s' not found in history/context",
                    code_mentioned,
                )
                return False

        # 4. Anti-hallucination check: Troubleshooting steps
        # If "Troubleshooting Performed:" contains bullet points, verify they don't claim steps never done
        if "Troubleshooting Performed:" in summary.description:
            lines = summary.description.split("Troubleshooting Performed:")[1].split("\n\n")[0].split("\n")
            for line in lines:
                line_s = line.strip()
                if line_s and (line_s.startswith(("1.", "2.", "3.", "4.", "•", "-"))):
                    step_text = re.sub(r"^[0-9\.\•\-\s]+", "", line_s).strip()
                    if step_text and "none" not in step_text.lower() and "no troubleshooting" not in step_text.lower():
                        # Verify at least one keyword from step_text is present in context steps or raw text
                        keywords = [w.lower() for w in re.findall(r"\b[a-zA-Z]{4,}\b", step_text)]
                        if keywords:
                            match_found = any(
                                kw in raw_text.lower() or
                                any(kw in s.lower() for s in context.troubleshooting_performed)
                                for kw in keywords
                            )
                            if not match_found:
                                logger.warning(
                                    "[VerificationEngine]: Rejected summary — step '%s' has no keyword matches in conversation/context",
                                    step_text,
                                )
                                return False

        return True


# ── 3. Deterministic Summary Builder (Fallback Engine) ────────────────────────

class DeterministicSummaryBuilder:
    """Generates a clean, grounded summary directly from TicketSummaryContext without LLM."""

    @staticmethod
    def build(context: TicketSummaryContext) -> TicketSummary:
        # Build short description
        issue_clean = context.issue.strip()
        if _GENERIC_BAD_PHRASES.match(issue_clean) or len(issue_clean) < 6:
            issue_clean = f"{context.category} issue"

        if context.error_codes:
            code_str = context.error_codes[0]
            if code_str.lower() not in issue_clean.lower():
                short_desc = f"{issue_clean} ({code_str})"
            else:
                short_desc = issue_clean
        else:
            short_desc = issue_clean

        # Format and trim short description
        short_desc = short_desc[0].upper() + short_desc[1:]
        if len(short_desc) > _SHORT_DESC_MAX_LEN:
            short_desc = short_desc[:_SHORT_DESC_MAX_LEN - 3].strip() + "..."

        # Build description
        summary_para = f"User reported an issue regarding {context.category}: {context.issue}."
        if context.error_codes:
            summary_para += f" Error code observed: {', '.join(context.error_codes)}."

        symptoms_str = "\n".join(f"- {s}" for s in context.symptoms) if context.symptoms else f"- {context.issue}"

        if context.troubleshooting_performed:
            steps_str = "\n".join(f"{i+1}. {step}" for i, step in enumerate(context.troubleshooting_performed))
        else:
            steps_str = "None performed."

        status_str = f"{context.resolution_status} - Escalated to IT Support."

        description = (
            f"Issue Summary:\n{summary_para}\n\n"
            f"Symptoms:\n{symptoms_str}\n\n"
            f"Troubleshooting Performed:\n{steps_str}\n\n"
            f"Current Status:\n{status_str}"
        )

        if len(description) > _DESC_MAX_LEN:
            description = description[:_DESC_MAX_LEN - 3].strip() + "..."

        return TicketSummary(
            short_description=short_desc,
            description=description,
            confidence=1.0,
            used_fallback=True,
            source="deterministic",
            keywords=[context.category.lower()],
            affected_service=context.category,
        )


# ── 4. Main Service Class ──────────────────────────────────────────────────────

class TicketSummaryService:
    """
    Enterprise AI-Powered Ticket Summary Service.

    Usage:
        service = TicketSummaryService(ai_provider=provider)
        summary = service.generate(conversation_history, troubleshooting_state, classification)
    """

    def __init__(self, ai_provider: Optional[Any] = None) -> None:
        self._ai_provider = ai_provider

    def _get_provider(self):
        if self._ai_provider:
            return self._ai_provider
        try:
            from app.services.ai_provider import get_ai_provider
            return get_ai_provider()
        except Exception:
            return None

    def generate(
        self,
        conversation_history: List[Dict[str, Any]],
        troubleshooting_state: Optional[Any] = None,
        classification: Optional[Any] = None,
        reasoning_result: Optional[Any] = None,
        knowledge_context: Optional[Any] = None,
    ) -> TicketSummary:
        """
        Generate a strictly-grounded TicketSummary for ticket creation.

        Never raises — falls back to DeterministicSummaryBuilder on any failure.
        """
        provider = self._get_provider()
        provider_name = getattr(provider, "provider_name", "gemini") if provider else "none"

        with trace_span(
            name="ticket_summary",
            attributes={
                "provider": provider_name,
                "model": getattr(provider, "model_name", "unknown") if provider else "none",
                "correlation_id": correlation_id_ctx.get() or "",
            },
        ):
            # Step 1: Extract structured facts context
            context = TicketSummaryContextBuilder.build_context(
                conversation_history=conversation_history,
                troubleshooting_state=troubleshooting_state,
                classification=classification,
            )

            # Step 2: Attempt AI summary generation
            if provider:
                try:
                    ai_summary = self._generate_with_llm(provider, context, conversation_history)
                    if ai_summary and VerificationEngine.verify(ai_summary, context, conversation_history):
                        logger.info(
                            "[TicketSummaryService]: Successfully generated and verified AI TicketSummary "
                            "(short_desc='%s', len=%d)",
                            ai_summary.short_description, len(ai_summary.short_description),
                        )
                        return ai_summary
                    else:
                        logger.warning(
                            "[TicketSummaryService]: AI summary failed verification — using deterministic fallback.",
                        )
                except Exception as exc:
                    logger.warning(
                        "[TicketSummaryService]: AI summary generation raised %s: %s — using deterministic fallback.",
                        type(exc).__name__, exc,
                    )

            # Step 3: Fallback engine
            return DeterministicSummaryBuilder.build(context)

    def _generate_with_llm(
        self,
        provider: Any,
        context: TicketSummaryContext,
        conversation_history: List[Dict[str, Any]],
    ) -> Optional[TicketSummary]:
        """Call LLM with structured context and parse JSON result."""
        prompt = (
            "You are an IT Service Desk Engineer.\n"
            "Your task is to summarize the completed troubleshooting conversation into a ServiceNow incident.\n\n"
            "STRICT FACTUAL CONSTRAINTS:\n"
            "- You MUST ONLY summarize information explicitly present in the provided context and history.\n"
            "- Do NOT invent symptoms.\n"
            "- Do NOT invent troubleshooting steps.\n"
            "- Do NOT invent error codes.\n"
            "- Do NOT infer hardware failure unless explicitly stated.\n"
            "- If information is unavailable, omit it.\n\n"
            "REQUIRED OUTPUT FORMAT:\n"
            "Return ONLY valid JSON matching this schema:\n"
            "{\n"
            '  "short_description": "Concise summary of the actual issue (MAX 120 CHARACTERS). No greetings or generic phrases.",\n'
            '  "description": "Structured summary formatted as:\\nIssue Summary:\\n<paragraph>\\n\\nSymptoms:\\n- <symptom>\\n\\nTroubleshooting Performed:\\n1. <step>\\n\\nCurrent Status:\\n<status> (MAX 2000 CHARACTERS)"\n'
            "}\n\n"
            f"STRUCTURED FACTS CONTEXT:\n"
            f"Category: {context.category}\n"
            f"Issue: {context.issue}\n"
            f"Symptoms: {json.dumps(context.symptoms)}\n"
            f"Troubleshooting Steps Performed: {json.dumps(context.troubleshooting_performed)}\n"
            f"Error Codes Observed: {json.dumps(context.error_codes)}\n"
            f"Current Resolution Status: {context.resolution_status}\n"
        )

        response = provider.generate_response(prompt)
        text = response.text if hasattr(response, "text") else str(response)

        # Strip markdown fences if present
        text_clean = text.strip()
        if text_clean.startswith("```"):
            text_clean = re.sub(r"^```(?:json)?\n?", "", text_clean)
            text_clean = re.sub(r"\n?```$", "", text_clean).strip()

        data = json.loads(text_clean)
        short_desc = str(data.get("short_description", "")).strip()
        desc = str(data.get("description", "")).strip()

        if not short_desc or not desc:
            return None

        return TicketSummary(
            short_description=short_desc,
            description=desc,
            confidence=0.92,
            used_fallback=False,
            source="gemini",
            keywords=[context.category.lower()],
            affected_service=context.category,
        )


# Helper function for convenient module-level invocation
def generate_ticket_summary(
    conversation_history: List[Dict[str, Any]],
    troubleshooting_state: Optional[Any] = None,
    classification: Optional[Any] = None,
    ai_provider: Optional[Any] = None,
) -> TicketSummary:
    """Convenience entry point for generating a TicketSummary."""
    service = TicketSummaryService(ai_provider=ai_provider)
    return service.generate(
        conversation_history=conversation_history,
        troubleshooting_state=troubleshooting_state,
        classification=classification,
    )
