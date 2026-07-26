"""
context_builder.py
──────────────────────────────────────────────────────────────────────────────
Context Builder for the Enterprise Troubleshooting Orchestrator.

Responsibilities
----------------
• Collect classification, KB documents, conversation history, state, and
  strategy into structured context objects.
• Trim conversation history to a bounded window.
• Produce KB context as summaries only — never raw article dumps.
• Build the structured decision prompt for ReasoningService.
• Build the final Gemini chat prompt that generates natural language output.

Design contracts (MUST NOT be violated)
----------------------------------------
  ✓  Context objects are immutable data transfer objects — no business logic.
  ✓  KB context contains summaries only — never exposes full article text.
  ✓  Conversation history is capped at MAX_HISTORY_TURNS to control token cost.
  ✓  The Gemini response prompt always instructs the model to:
       - Act as an experienced IT engineer
       - Ask only ONE question if clarification is needed
       - Never mention KB articles or internal tools by name
       - Guide one step at a time
  ✓  No LLM calls — pure data assembly.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from app.models.classification_models import ITSMClassification
    from app.services.knowledge_retrieval_service import RetrievedDocument
    from app.services.troubleshooting_state_service import TroubleshootingState
    from app.services.troubleshooting_strategy import TroubleshootingStrategy
    from app.services.reasoning_service import ReasoningResult

logger = logging.getLogger("it-agent-backend")


# ── Context Data Contracts ────────────────────────────────────────────────────

@dataclass
class ReasoningContext:
    """
    Structured context passed to ReasoningService.

    Contains everything the ReasoningEngine needs to decide the next action.
    All fields are pre-processed and bounded (no raw dumps).
    """
    issue_summary: str
    category: str
    strategy_name: str
    required_evidence: List[str]
    escalation_criteria: List[str]
    retrieved_knowledge_summary: str      # KB article digests, not raw text
    conversation_history: List[dict]      # bounded to MAX_HISTORY_TURNS
    state_summary: str                    # serialised key state fields
    user_message: str
    turn_count: int
    attempted_actions: List[str]
    missing_evidence: List[str]           # required_evidence not yet gathered


@dataclass
class ResponseContext:
    """
    Structured context passed to GeminiProvider.chat() for final response.

    Produced by build_response_context() after reasoning is complete.
    """
    issue_summary: str
    strategy_guidance: str
    kb_context: str                       # summaries only
    state_context: str
    reasoning_decision: str               # serialised ReasoningResult summary
    conversation_history: List[dict]      # bounded history for chat()


# ── Service ───────────────────────────────────────────────────────────────────

class ContextBuilder:
    """
    Centralised context assembly for the TroubleshootingOrchestrator.

    All prompt-construction logic lives here — the orchestrator stays clean.
    """

    MAX_HISTORY_TURNS: int = 10
    MAX_KB_DOCS: int = 2
    MAX_KB_STEPS_PER_DOC: int = 4          # steps included in summary
    MAX_STEP_CHARS: int = 120              # truncate long step text

    # ── Public API ────────────────────────────────────────────────────────────

    def build_reasoning_context(
        self,
        user_message: str,
        classification: "ITSMClassification",
        strategy: "TroubleshootingStrategy",
        retrieved_docs: List["RetrievedDocument"],
        state: "TroubleshootingState",
        history: List[dict],
    ) -> ReasoningContext:
        """
        Build a ReasoningContext for the ReasoningEngine.

        Args:
            user_message:    Current user message.
            classification:  Validated ITSMClassification output.
            strategy:        Domain TroubleshootingStrategy.
            retrieved_docs:  KB documents from KnowledgeRetrievalService.
            state:           Current TroubleshootingState.
            history:         Raw conversation history list.

        Returns:
            ReasoningContext ready for ReasoningEngine.reason().
        """
        bounded_history = self._trim_history(history)
        kb_summary = self._build_kb_summary(retrieved_docs)
        state_summary = state.to_summary()

        # Determine which required evidence items have not yet been answered
        answered_keys = {k.lower() for k in state.user_answers.keys()}
        missing_evidence = [
            ev for ev in strategy.required_evidence
            if not any(kw in answered_keys for kw in ev.lower().split()[:3])
        ]

        ctx = ReasoningContext(
            issue_summary=self._build_issue_summary(classification, state),
            category=classification.category,
            strategy_name=strategy.name,
            required_evidence=strategy.required_evidence,
            escalation_criteria=strategy.escalation_criteria,
            retrieved_knowledge_summary=kb_summary,
            conversation_history=bounded_history,
            state_summary=state_summary,
            user_message=user_message,
            turn_count=state.turn_count,
            attempted_actions=state.attempted_actions,
            missing_evidence=missing_evidence,
        )
        logger.debug(
            "[ContextBuilder.build_reasoning_context]: built for session='%s', "
            "category='%s', missing_evidence=%d",
            state.session_id, classification.category, len(missing_evidence),
        )
        return ctx

    def build_response_context(
        self,
        reasoning_result: "ReasoningResult",
        strategy: "TroubleshootingStrategy",
        retrieved_docs: List["RetrievedDocument"],
        state: "TroubleshootingState",
        history: List[dict],
    ) -> ResponseContext:
        """
        Build a ResponseContext for GeminiProvider.chat().

        Args:
            reasoning_result: Output of ReasoningEngine.reason().
            strategy:         Domain TroubleshootingStrategy.
            retrieved_docs:   KB documents from KnowledgeRetrievalService.
            state:            Current TroubleshootingState (post-update).
            history:          Raw conversation history list.

        Returns:
            ResponseContext ready for build_response_prompt().
        """
        kb_context = self._build_kb_context_for_response(retrieved_docs)
        strategy_guidance = self._build_strategy_guidance(strategy)
        decision_summary = self._build_decision_summary(reasoning_result)
        state_context = state.to_summary()

        return ResponseContext(
            issue_summary=state.current_issue,
            strategy_guidance=strategy_guidance,
            kb_context=kb_context,
            state_context=state_context,
            reasoning_decision=decision_summary,
            conversation_history=self._trim_history(history),
        )

    def build_response_prompt(self, context: ResponseContext) -> str:
        """
        Build the system prompt string for GeminiProvider.chat().

        The prompt instructs Gemini to behave as an experienced IT support
        engineer — not a search engine and not a KB reader.

        Returns:
            Multi-section system prompt string.
        """
        sections = [
            "You are an experienced IT support engineer at Bridgestone.",
            "Your goal is to help the user resolve their IT issue through a natural, professional conversation.",
            "",
            "=== CRITICAL BEHAVIOUR RULES ===",
            "- Ask ONLY ONE question at a time — never list multiple questions.",
            "- Guide the user through ONE troubleshooting step at a time.",
            "- Do NOT mention KB articles, internal systems, or tool names.",
            "- Do NOT dump lists of steps — guide the user naturally.",
            "- Do NOT reveal your internal reasoning or decision process.",
            "- Speak like an experienced colleague, not a helpdesk script.",
            "- If the issue is resolved, confirm warmly and close the conversation.",
            "- If you need to escalate, reassure the user and summarise what was tried.",
            "",
            "=== CURRENT ISSUE ===",
            context.issue_summary,
            "",
            "=== TROUBLESHOOTING APPROACH ===",
            context.strategy_guidance,
            "",
        ]

        if context.kb_context:
            sections += [
                "=== RELEVANT TECHNICAL CONTEXT (use as reference, never quote directly) ===",
                context.kb_context,
                "",
            ]

        sections += [
            "=== SESSION CONTEXT ===",
            context.state_context,
            "",
            "=== NEXT ACTION DECIDED ===",
            context.reasoning_decision,
            "",
            "Based on all of the above, generate your next conversational reply as the IT support engineer.",
            "Remember: ONE question or ONE step only. Natural, professional English.",
        ]

        return "\n".join(sections)

    def build_decision_prompt(
        self,
        context: ReasoningContext,
    ) -> str:
        """
        Build the structured decision prompt for ReasoningService.

        The output of this prompt MUST be a JSON object conforming to
        DECISION_SCHEMA in reasoning_service.py.

        Returns:
            Structured prompt string for ai_provider.generate_response().
        """
        history_text = self._format_history_for_prompt(context.conversation_history)

        sections = [
            "You are an ITSM Reasoning Engine for an enterprise IT support system.",
            "Analyse the following information and return a structured JSON decision.",
            "",
            "=== CURRENT ISSUE ===",
            context.issue_summary,
            "",
            f"=== CATEGORY: {context.category} ===",
            f"Strategy: {context.strategy_name}",
            "",
            "=== REQUIRED EVIDENCE (what must be gathered before acting) ===",
            "\n".join(f"- {ev}" for ev in context.required_evidence),
            "",
            "=== EVIDENCE NOT YET GATHERED ===",
            (
                "\n".join(f"- {ev}" for ev in context.missing_evidence)
                if context.missing_evidence
                else "All required evidence has been gathered."
            ),
            "",
            "=== ESCALATION CRITERIA ===",
            "\n".join(f"- {ec}" for ec in context.escalation_criteria),
            "",
        ]

        if context.retrieved_knowledge_summary:
            sections += [
                "=== KNOWLEDGE BASE CONTEXT ===",
                context.retrieved_knowledge_summary,
                "",
            ]

        sections += [
            "=== SESSION STATE ===",
            context.state_summary,
            f"Turn count: {context.turn_count}",
            "",
            "=== STEPS ALREADY ATTEMPTED ===",
            (
                "\n".join(f"- {a}" for a in context.attempted_actions)
                if context.attempted_actions
                else "None yet."
            ),
            "",
            "=== RECENT CONVERSATION ===",
            history_text or "No history yet.",
            "",
            f"=== LATEST USER MESSAGE ===\n{context.user_message}",
            "",
            "=== DECISION REQUIRED ===",
            "Return ONLY a valid JSON object. No markdown, no explanation, no extra text.",
            "Schema:",
            json.dumps({
                "next_action":           "ASK_QUESTION | GUIDE_STEP | RETRIEVE_KNOWLEDGE | NEEDS_ADMIN | ESCALATE | RESOLVE | WAIT",
                "confidence":            "float 0.0-1.0",
                "missing_information":   ["list of strings — what info is still needed"],
                "selected_kb":           "article_id or empty string",
                "selected_step":         "brief step instruction or empty string",
                "escalation":            "true or false",
                "reason_code":           "short identifier e.g. NO_ERROR_CODE / STEPS_EXHAUSTED / RESOLVED",
                "requires_confirmation": "true or false",
            }, indent=2),
        ]

        return "\n".join(sections)

    # ── Internal Helpers ──────────────────────────────────────────────────────

    def _trim_history(self, history: List[dict]) -> List[dict]:
        """Return the last MAX_HISTORY_TURNS entries from conversation history."""
        if len(history) <= self.MAX_HISTORY_TURNS:
            return list(history)
        trimmed = history[-self.MAX_HISTORY_TURNS:]
        logger.debug(
            "[ContextBuilder]: Trimmed history from %d to %d turns.",
            len(history), len(trimmed),
        )
        return trimmed

    def _build_issue_summary(
        self,
        classification: "ITSMClassification",
        state: "TroubleshootingState",
    ) -> str:
        """Build a concise issue summary combining classification and state."""
        parts = [state.current_issue]
        if classification.category and classification.category != "General IT":
            parts.append(f"Category: {classification.category}")
        if classification.subcategory:
            parts.append(f"Sub-category: {classification.subcategory}")
        return " | ".join(parts)

    def _build_kb_summary(self, docs: List["RetrievedDocument"]) -> str:
        """
        Build a KB summary for the reasoning prompt.
        Includes problem description + up to MAX_KB_STEPS_PER_DOC step titles.
        """
        if not docs:
            return ""
        summaries = []
        for doc in docs[:self.MAX_KB_DOCS]:
            step_titles = []
            for step in doc.troubleshooting_steps[:self.MAX_KB_STEPS_PER_DOC]:
                if isinstance(step, dict):
                    title = step.get("title") or step.get("instruction") or step.get("step", "")
                    if title:
                        step_titles.append(title[:self.MAX_STEP_CHARS])
            steps_text = "; ".join(step_titles) if step_titles else "No steps available"
            summaries.append(
                f"[{doc.article_id}] {doc.title} (confidence: {doc.confidence:.2f})\n"
                f"  Summary: {doc.content_summary[:200]}\n"
                f"  Steps: {steps_text}"
            )
        return "\n\n".join(summaries)

    def _build_kb_context_for_response(self, docs: List["RetrievedDocument"]) -> str:
        """
        Build KB context for the Gemini response prompt.
        Returns summaries only — never article titles, IDs, or raw step text.
        """
        if not docs:
            return ""
        parts = []
        for doc in docs[:self.MAX_KB_DOCS]:
            parts.append(f"Technical context: {doc.content_summary[:300]}")
        return "\n".join(parts)

    def _build_strategy_guidance(self, strategy: "TroubleshootingStrategy") -> str:
        """Build a concise strategy guidance block for the response prompt."""
        lines = [f"Domain: {strategy.name}"]
        if strategy.common_sequence:
            seq = "; ".join(strategy.common_sequence[:4])
            lines.append(f"Typical approach: {seq}")
        if strategy.stopping_conditions:
            stop = "; ".join(strategy.stopping_conditions[:2])
            lines.append(f"Resolution signals: {stop}")
        return "\n".join(lines)

    def _build_decision_summary(self, reasoning_result: "ReasoningResult") -> str:
        """Serialise the reasoning result into a concise decision summary."""
        lines = [
            f"Next action: {reasoning_result.next_action.value}",
            f"Reason code: {reasoning_result.reason_code}",
            f"Confidence: {reasoning_result.confidence:.2f}",
        ]
        if reasoning_result.selected_step:
            lines.append(f"Step to guide: {reasoning_result.selected_step}")
        if reasoning_result.missing_information:
            lines.append(f"Still needed: {'; '.join(reasoning_result.missing_information[:3])}")
        if reasoning_result.requires_confirmation:
            lines.append("Requires user confirmation: yes")
        if reasoning_result.escalation:
            lines.append("Escalation: REQUIRED")
        return "\n".join(lines)

    def _format_history_for_prompt(self, history: List[dict]) -> str:
        """Format bounded conversation history as a readable block."""
        lines = []
        for turn in history:
            role = turn.get("role", "unknown")
            text = turn.get("text") or turn.get("content") or ""
            if text:
                prefix = "User" if role == "user" else "Assistant"
                lines.append(f"{prefix}: {text[:200]}")
        return "\n".join(lines)
