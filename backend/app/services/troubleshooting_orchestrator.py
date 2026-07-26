"""
troubleshooting_orchestrator.py
──────────────────────────────────────────────────────────────────────────────
Enterprise Troubleshooting Orchestrator for the Bridgestone IT Agent.

Responsibilities
----------------
• Coordinate the complete troubleshooting lifecycle for incident categories.
• Call services in the correct order without embedding business logic.
• Route escalation to the existing TicketService with full session context.
• Generate final natural-language responses through AIProvider.chat().

Design contracts (MUST NOT be violated)
----------------------------------------
  ✓  INCIDENTS ONLY — Service Requests are out of scope (Phase 5).
  ✓  Never calls ServiceNow directly — escalation goes through TicketService.
  ✓  No prompt engineering — all prompts are built by ContextBuilder.
  ✓  No reasoning logic — all decisions are made by ReasoningEngine.
  ✓  No KB retrieval — all knowledge is fetched by KnowledgeRetrievalService.
  ✓  Never raises — all external calls wrapped with structured error handling.
  ✓  Structured audit log at every turn.

Orchestration flow (per handle() call)
----------------------------------------
  1. Get or create TroubleshootingState for session.
  2. Increment turn counter.
  3. Select TroubleshootingStrategy for classification domain.
  4. Retrieve relevant KB documents.
  5. Build ReasoningContext via ContextBuilder.
  6. Obtain structured ReasoningResult from ReasoningEngine.
  7. Update TroubleshootingState based on result.
  8. If ESCALATE → TicketService → return OrchestrationResult.
  9. If RESOLVE → mark resolved → return OrchestrationResult.
  10. Build ResponseContext via ContextBuilder.
  11. Generate natural language reply via AIProvider.chat().
  12. Return OrchestrationResult.

EnterprisePolicyService: DEFERRED (Phase 3)
  PolicyDecision stub is included here to reserve the interface.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from app.services.knowledge_retrieval_service import KnowledgeRetrievalService, RetrievedDocument
from app.services.troubleshooting_strategy import TroubleshootingStrategyRegistry, TroubleshootingStrategy
from app.services.context_builder import ContextBuilder
from app.services.reasoning_service import ReasoningEngine, ReasoningResult, NextAction
from app.services.troubleshooting_state_service import (
    TroubleshootingStateManager,
    TroubleshootingState,
    ResolutionStatus,
)
from app.services.ai_provider import BaseAIProvider

if TYPE_CHECKING:
    from app.models.classification_models import ITSMClassification

logger = logging.getLogger("it-agent-backend")


# ── Enterprise Policy Stub (Phase 3) ─────────────────────────────────────────

@dataclass
class PolicyDecision:
    """
    Minimal policy decision stub.

    Full EnterprisePolicyService will be introduced in Phase 3 when
    LAPS, admin privilege checks, and approval workflows are required.
    """
    requires_admin: bool   = False
    requires_approval: bool = False
    policy_name: str       = ""
    reason: str            = ""


# ── Data Contracts ────────────────────────────────────────────────────────────

@dataclass
class OrchestrationRequest:
    """Input to TroubleshootingOrchestrator.handle()."""
    session_id: str
    user_message: str
    classification: "ITSMClassification"
    conversation_history: List[dict] = field(default_factory=list)


@dataclass
class OrchestrationResult:
    """Output of TroubleshootingOrchestrator.handle()."""
    response_text: str
    state: TroubleshootingState
    is_resolved: bool
    requires_escalation: bool
    escalation_context: Optional[Dict[str, Any]] = None


# ── Service ───────────────────────────────────────────────────────────────────

class TroubleshootingOrchestrator:
    """
    Enterprise Troubleshooting Orchestrator.

    Coordinates KnowledgeRetrievalService, TroubleshootingStrategy,
    ContextBuilder, ReasoningEngine, TroubleshootingStateManager, and
    AIProvider.chat() to produce a natural, one-step-at-a-time IT support
    conversation.

    All dependencies are injected — no singletons, fully testable.
    """

    # Fallback response when AI provider fails unexpectedly
    _FALLBACK_RESPONSE = (
        "I'm having a moment of difficulty processing that. "
        "Could you repeat what you last tried? I want to make sure we pick up exactly where we left off."
    )

    def __init__(
        self,
        knowledge_service: KnowledgeRetrievalService,
        strategy_registry: TroubleshootingStrategyRegistry,
        context_builder: ContextBuilder,
        reasoning_engine: ReasoningEngine,
        state_manager: TroubleshootingStateManager,
        ai_provider: BaseAIProvider,
        ticket_service: Optional[Any] = None,
    ) -> None:
        self._knowledge_service  = knowledge_service
        self._strategy_registry  = strategy_registry
        self._context_builder    = context_builder
        self._reasoning_engine   = reasoning_engine
        self._state_manager      = state_manager
        self._ai_provider        = ai_provider
        self._ticket_service     = ticket_service

    # ── Public API ────────────────────────────────────────────────────────────

    def handle(self, request: OrchestrationRequest) -> OrchestrationResult:
        """
        Handle a single conversation turn for an incident troubleshooting session.

        Never raises — all errors are caught and a safe fallback response returned.

        Args:
            request: OrchestrationRequest with session_id, user_message,
                     classification, and conversation_history.

        Returns:
            OrchestrationResult with the natural language reply and updated state.
        """
        t_start = time.monotonic()

        logger.info(
            ">>> ENTRY [TroubleshootingOrchestrator.handle]: session='%s', "
            "category='%s', message='%s'",
            request.session_id,
            request.classification.category,
            request.user_message[:80],
        )

        try:
            result = self._handle_internal(request, t_start)
        except Exception as exc:
            logger.exception(
                "[TroubleshootingOrchestrator.handle]: Unexpected error for session '%s': %s",
                request.session_id, exc,
            )
            state = self._state_manager.get(request.session_id)
            if state is None:
                state = self._state_manager.create(
                    request.session_id,
                    request.user_message,
                    request.classification.category,
                )
            result = OrchestrationResult(
                response_text=self._FALLBACK_RESPONSE,
                state=state,
                is_resolved=False,
                requires_escalation=False,
            )

        elapsed_ms = int((time.monotonic() - t_start) * 1000)
        self._audit_log(request, result, elapsed_ms)
        return result

    # ── Internal Orchestration ────────────────────────────────────────────────

    def _handle_internal(
        self,
        request: OrchestrationRequest,
        t_start: float,
    ) -> OrchestrationResult:
        """Core orchestration sequence."""

        # ── 1. Session State ──────────────────────────────────────────────────
        state = self._state_manager.get_or_create(
            session_id=request.session_id,
            issue=request.user_message,
            strategy_domain=request.classification.category,
        )
        state = self._state_manager.increment_turn(state)

        # ── 2. Strategy Selection ─────────────────────────────────────────────
        strategy = self._strategy_registry.get(request.classification.category)

        # ── 3. Policy Check (Phase 3 stub — always passes in Phase 1) ─────────
        policy = self._evaluate_policy(request.classification, state)
        if policy.requires_admin and not policy.requires_approval:
            logger.info(
                "[TroubleshootingOrchestrator]: Policy requires admin for session '%s': %s",
                request.session_id, policy.reason,
            )
            # Phase 3 will handle this properly — for now, note in state and continue
            self._state_manager.mark_needs_admin(state)

        # ── 4. Knowledge Retrieval ─────────────────────────────────────────────
        query = f"{request.classification.category} {request.user_message}"
        retrieved_docs: List[RetrievedDocument] = []
        try:
            retrieved_docs = self._knowledge_service.retrieve(
                query=query,
                category=request.classification.category,
                max_results=2,
                min_confidence=0.10,
            )
        except Exception as exc:
            logger.warning(
                "[TroubleshootingOrchestrator]: KB retrieval failed for session '%s': %s",
                request.session_id, exc,
            )

        # ── 5. Build Reasoning Context ────────────────────────────────────────
        reasoning_ctx = self._context_builder.build_reasoning_context(
            user_message=request.user_message,
            classification=request.classification,
            strategy=strategy,
            retrieved_docs=retrieved_docs,
            state=state,
            history=request.conversation_history,
        )

        # ── 6. Reasoning ──────────────────────────────────────────────────────
        reasoning: ReasoningResult = self._reasoning_engine.reason(reasoning_ctx)

        # ── 7. State Update ───────────────────────────────────────────────────
        state = self._update_state(state, reasoning, request.user_message)

        # ── 8. Resolution ─────────────────────────────────────────────────────
        if reasoning.next_action == NextAction.RESOLVE:
            state = self._state_manager.mark_resolved(state)
            self._state_manager.update(request.session_id, state)
            return OrchestrationResult(
                response_text=self._generate_natural_response(
                    request, strategy, retrieved_docs, state, reasoning
                ),
                state=state,
                is_resolved=True,
                requires_escalation=False,
            )

        # ── 9. Escalation ─────────────────────────────────────────────────────
        if reasoning.next_action == NextAction.ESCALATE or reasoning.escalation:
            state = self._state_manager.mark_escalated(state)
            self._state_manager.update(request.session_id, state)
            escalation_ctx = self._build_escalation_context(request, state, reasoning)
            self._trigger_escalation(escalation_ctx)
            return OrchestrationResult(
                response_text=self._generate_natural_response(
                    request, strategy, retrieved_docs, state, reasoning
                ),
                state=state,
                is_resolved=False,
                requires_escalation=True,
                escalation_context=escalation_ctx,
            )

        # ── 10. Persist Updated State ─────────────────────────────────────────
        self._state_manager.update(request.session_id, state)

        # ── 11. Generate Natural Language Response via AIProvider.chat() ───────
        response_text = self._generate_natural_response(
            request, strategy, retrieved_docs, state, reasoning
        )

        return OrchestrationResult(
            response_text=response_text,
            state=state,
            is_resolved=False,
            requires_escalation=False,
        )

    # ── Helper Methods ────────────────────────────────────────────────────────

    def _evaluate_policy(
        self,
        classification: "ITSMClassification",
        state: TroubleshootingState,
    ) -> PolicyDecision:
        """
        Phase 1 stub — always returns a permissive policy.
        Phase 3: Replace with full EnterprisePolicyService.evaluate() call.
        """
        return PolicyDecision()

    def _update_state(
        self,
        state: TroubleshootingState,
        reasoning: ReasoningResult,
        user_message: str,
    ) -> TroubleshootingState:
        """Apply reasoning result updates to the troubleshooting state."""

        # Record any user answers inferred from the message
        if reasoning.missing_information:
            for item in reasoning.missing_information:
                # Only add questions that haven't been asked yet
                if item and item not in state.user_answers:
                    pass  # Will be captured when user responds

        # Record the guided step as attempted so it is not repeated
        if reasoning.selected_step and reasoning.next_action == NextAction.GUIDE_STEP:
            if not self._state_manager.has_attempted(state, reasoning.selected_step):
                state = self._state_manager.record_step(
                    state,
                    instruction=reasoning.selected_step,
                    result="Guided to user — awaiting confirmation",
                    success=True,
                )

        return state

    def _generate_natural_response(
        self,
        request: OrchestrationRequest,
        strategy: TroubleshootingStrategy,
        retrieved_docs: List[RetrievedDocument],
        state: TroubleshootingState,
        reasoning: ReasoningResult,
    ) -> str:
        """
        Generate the final natural language response via AIProvider.chat().

        The ContextBuilder assembles the system prompt; the AI generates
        the conversational reply.  No response text ever comes from the
        reasoning layer.

        The system prompt is prepended to the history so GeminiProvider.chat()
        receives full context framing even though it only accepts (user_message, history).
        """
        try:
            response_ctx = self._context_builder.build_response_context(
                reasoning_result=reasoning,
                strategy=strategy,
                retrieved_docs=retrieved_docs,
                state=state,
                history=request.conversation_history,
            )
            system_prompt = self._context_builder.build_response_prompt(response_ctx)

            # Prepend the system prompt as the first user/model exchange so
            # GeminiProvider.chat() receives the full context within its
            # existing history parameter (no separate system_instruction arg).
            history_for_chat = [
                {"role": "user",  "text": system_prompt},
                {"role": "model", "text": "Understood. I am ready to assist as the IT support engineer."},
            ]
            for turn in response_ctx.conversation_history:
                role = turn.get("role", "user")
                text = turn.get("text") or turn.get("content") or ""
                if text:
                    history_for_chat.append({"role": role, "text": text})

            response_text = self._ai_provider.chat(
                user_message=request.user_message,
                history=history_for_chat,
            )

            if not response_text or response_text.startswith("[AI Provider Error]"):
                logger.warning(
                    "[TroubleshootingOrchestrator]: AI provider returned error or empty response "
                    "for session '%s'. Using fallback.",
                    request.session_id,
                )
                return self._FALLBACK_RESPONSE

            return response_text

        except Exception as exc:
            logger.warning(
                "[TroubleshootingOrchestrator]: Response generation failed for session '%s': %s",
                request.session_id, exc,
            )
            return self._FALLBACK_RESPONSE


    def _build_escalation_context(
        self,
        request: OrchestrationRequest,
        state: TroubleshootingState,
        reasoning: ReasoningResult,
    ) -> Dict[str, Any]:
        """Build the full context dictionary passed to TicketService on escalation."""
        return {
            "session_id":         request.session_id,
            "issue_description":  state.current_issue,
            "category":           request.classification.category,
            "subcategory":        request.classification.subcategory,
            "assignment_group":   request.classification.assignment_group,
            "conversation_history": request.conversation_history,
            "completed_steps":    [s.to_dict() for s in state.completed_steps],
            "failed_steps":       [s.to_dict() for s in state.failed_steps],
            "error_codes":        state.error_codes,
            "user_answers":       state.user_answers,
            "reason_code":        reasoning.reason_code,
            "turn_count":         state.turn_count,
        }

    def _trigger_escalation(self, context: Dict[str, Any]) -> None:
        """
        Hand off to TicketService with full session context.
        Escalation is best-effort — failure is logged but does not crash the turn.
        """
        if self._ticket_service is None:
            logger.info(
                "[TroubleshootingOrchestrator]: No TicketService injected — "
                "skipping escalation for session '%s'.",
                context.get("session_id"),
            )
            return

        try:
            logger.info(
                "[TroubleshootingOrchestrator]: Escalating session '%s' to TicketService.",
                context.get("session_id"),
            )
            # TicketService.create_ticket() signature: (category, description, user_id, ...)
            # Pass full context — TicketService extracts what it needs
            self._ticket_service.create_ticket(
                category=context.get("category", "General IT"),
                issue_description=context.get("issue_description", ""),
                context=context,
            )
        except Exception as exc:
            logger.error(
                "[TroubleshootingOrchestrator]: TicketService escalation failed for session '%s': %s",
                context.get("session_id"), exc,
            )

    def _audit_log(
        self,
        request: OrchestrationRequest,
        result: OrchestrationResult,
        elapsed_ms: int,
    ) -> None:
        """Structured audit log for every orchestration turn."""
        logger.info(
            "\n========== TROUBLESHOOTING ORCHESTRATOR AUDIT ==========\n"
            "Session          : %s\n"
            "Category         : %s\n"
            "Turn             : %d\n"
            "Strategy Domain  : %s\n"
            "Resolution       : %s\n"
            "Is Resolved      : %s\n"
            "Requires Escalation: %s\n"
            "Latency          : %dms\n"
            "=========================================================",
            request.session_id,
            request.classification.category,
            result.state.turn_count,
            result.state.strategy_domain,
            result.state.resolution_status.value,
            result.is_resolved,
            result.requires_escalation,
            elapsed_ms,
        )
