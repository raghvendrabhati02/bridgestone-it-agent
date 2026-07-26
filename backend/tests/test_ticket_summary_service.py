"""
test_ticket_summary_service.py
──────────────────────────────────────────────────────────────────────────────
Comprehensive unit test suite for TicketSummaryService, VerificationEngine,
TicketSummaryContextBuilder, DeterministicSummaryBuilder, and TicketOrchestrator integration.

All external LLM calls are mocked — zero network, zero real Gemini calls.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from unittest.mock import MagicMock, patch

import pytest

from app.services.ticket_summary_service import (
    DeterministicSummaryBuilder,
    TicketSummary,
    TicketSummaryContext,
    TicketSummaryContextBuilder,
    TicketSummaryService,
    VerificationEngine,
    generate_ticket_summary,
)


# ── Fixtures & Mock Provider ──────────────────────────────────────────────────

def _make_mock_provider(json_response_dict: dict):
    provider = MagicMock()
    response = MagicMock()
    response.text = json.dumps(json_response_dict)
    provider.generate_response.return_value = response
    return provider


@dataclass
class _FakeStep:
    instruction: str
    status: str = "completed"


@dataclass
class _FakeState:
    session_id: str                     = "test-session-123"
    category: str                       = "GENERAL"
    current_issue: str                  = "Wi-Fi"
    strategy_domain: str                = "wifi_guide"
    completed_steps: list               = field(default_factory=list)
    failed_steps: list                  = field(default_factory=list)
    attempted_actions: list             = field(default_factory=list)
    observed_results: list              = field(default_factory=list)
    error_codes: list                   = field(default_factory=list)
    user_answers: dict                  = field(default_factory=dict)
    resolution_status: str              = "UNRESOLVED"


# ── 1. Context Builder Tests ──────────────────────────────────────────────────

class TestContextBuilder:

    def test_build_context_wifi_issue(self):
        history = [
            {"sender": "user", "text": "I have wifi issues"},
            {"sender": "agent", "text": "Can you connect to any network?"},
            {"sender": "user", "text": "No, airplane mode toggled"},
        ]
        state = _FakeState(
            current_issue="Wi-Fi Connection",
            strategy_domain="wifi_guide",
            completed_steps=[_FakeStep("Adapter verified"), _FakeStep("TCP/IP reset")],
            error_codes=[],
        )
        ctx = TicketSummaryContextBuilder.build_context(history, state)

        assert ctx.issue == "Wi-Fi Connection"
        assert "Adapter verified" in ctx.troubleshooting_performed
        assert "TCP/IP reset" in ctx.troubleshooting_performed
        assert len(ctx.symptoms) > 0

    def test_build_context_vpn_error_code_extraction(self):
        history = [
            {"sender": "user", "text": "My GlobalProtect VPN disconnects with Error 909 every 5 minutes."},
        ]
        state = _FakeState(current_issue="VPN Connection", strategy_domain="vpn_guide")
        ctx = TicketSummaryContextBuilder.build_context(history, state)

        assert "ERROR 909" in [e.upper() for e in ctx.error_codes]


# ── 2. Verification Engine Tests (Anti-Hallucination) ─────────────────────────

class TestVerificationEngine:

    def test_accepts_valid_summary(self):
        ctx = TicketSummaryContext(
            issue="Wi-Fi Connection",
            category="Wi-Fi",
            symptoms=["Unable to connect"],
            troubleshooting_performed=["Checked adapter", "Reset TCP/IP"],
            error_codes=[],
        )
        summary = TicketSummary(
            short_description="Unable to connect to any Wi-Fi network",
            description=(
                "Issue Summary:\nUser is unable to connect to any Wi-Fi network.\n\n"
                "Symptoms:\n- Unable to connect\n\n"
                "Troubleshooting Performed:\n1. Checked adapter\n2. Reset TCP/IP\n\n"
                "Current Status:\nUNRESOLVED"
            ),
        )
        history = [{"sender": "user", "text": "Unable to connect to wifi"}]
        assert VerificationEngine.verify(summary, ctx, history) is True

    def test_rejects_hallucinated_error_code(self):
        ctx = TicketSummaryContext(
            issue="Wi-Fi",
            category="Wi-Fi",
            symptoms=["No internet"],
            troubleshooting_performed=["Checked adapter"],
            error_codes=[],
        )
        # Summary claims Error 909, but it's not in ctx.error_codes or history
        summary = TicketSummary(
            short_description="Wi-Fi failure with Error 909",
            description="Issue Summary:\nUser reported Wi-Fi failure with Error 909.\n\nSymptoms:\n- No internet",
        )
        history = [{"sender": "user", "text": "Wi-Fi is not working"}]
        assert VerificationEngine.verify(summary, ctx, history) is False

    def test_rejects_hallucinated_troubleshooting_step(self):
        ctx = TicketSummaryContext(
            issue="Printer offline",
            category="Printer",
            symptoms=["Printer offline"],
            troubleshooting_performed=["Power cycled printer"],
            error_codes=[],
        )
        # Summary claims Outlook registry edit was done for a printer issue!
        summary = TicketSummary(
            short_description="Printer is offline and not responding",
            description=(
                "Issue Summary:\nPrinter offline.\n\n"
                "Symptoms:\n- Printer offline\n\n"
                "Troubleshooting Performed:\n1. Reinstalled Microsoft Outlook registry keys"
            ),
        )
        history = [{"sender": "user", "text": "My printer is offline"}]
        assert VerificationEngine.verify(summary, ctx, history) is False

    def test_rejects_generic_short_description(self):
        ctx = TicketSummaryContext(issue="Wi-Fi", category="Wi-Fi")
        summary = TicketSummary(
            short_description="Hi",
            description="Issue Summary:\nWi-Fi issue.",
        )
        history = [{"sender": "user", "text": "Hi"}]
        assert VerificationEngine.verify(summary, ctx, history) is False

    def test_rejects_oversized_short_description(self):
        ctx = TicketSummaryContext(issue="Wi-Fi", category="Wi-Fi")
        summary = TicketSummary(
            short_description="A" * 121,
            description="Issue Summary:\nWi-Fi issue.",
        )
        history = [{"sender": "user", "text": "Wi-Fi issue"}]
        assert VerificationEngine.verify(summary, ctx, history) is False


# ── 3. Deterministic Fallback Tests ───────────────────────────────────────────

class TestDeterministicSummaryBuilder:

    def test_build_fallback(self):
        ctx = TicketSummaryContext(
            issue="GlobalProtect VPN Disconnects",
            category="VPN",
            symptoms=["GlobalProtect disconnects frequently"],
            troubleshooting_performed=["Restarted GlobalProtect", "Flushed DNS"],
            error_codes=["Error 909"],
            resolution_status="UNRESOLVED",
        )
        summary = DeterministicSummaryBuilder.build(ctx)

        assert summary.used_fallback is True
        assert summary.source == "deterministic"
        assert summary.confidence == 1.0
        assert len(summary.short_description) <= 120
        assert "GlobalProtect VPN Disconnects" in summary.short_description
        assert "Error 909" in summary.short_description or "Error 909" in summary.description
        assert "Troubleshooting Performed:\n1. Restarted GlobalProtect\n2. Flushed DNS" in summary.description


# ── 4. Full TicketSummaryService Tests ────────────────────────────────────────

class TestTicketSummaryService:

    def test_generate_wifi_issue_success(self):
        llm_json = {
            "short_description": "Unable to connect to any Wi-Fi network",
            "description": (
                "Issue Summary:\nUser is completely unable to connect to any wireless network.\n\n"
                "Symptoms:\n- Wi-Fi adapter fails to discover networks\n\n"
                "Troubleshooting Performed:\n1. Adapter verified\n2. TCP/IP reset\n\n"
                "Current Status:\nUNRESOLVED - Escalated to IT Support"
            ),
        }
        provider = _make_mock_provider(llm_json)

        history = [
            {"sender": "user", "text": "I have wifi issues"},
            {"sender": "agent", "text": "Check adapter"},
            {"sender": "user", "text": "Adapter verified"},
        ]
        state = _FakeState(
            current_issue="Wi-Fi Connection",
            completed_steps=[_FakeStep("Adapter verified"), _FakeStep("TCP/IP reset")],
        )

        service = TicketSummaryService(ai_provider=provider)
        summary = service.generate(history, state)

        assert summary.used_fallback is False
        assert summary.source == "gemini"
        assert summary.short_description == "Unable to connect to any Wi-Fi network"
        assert len(summary.short_description) <= 120
        assert len(summary.description) <= 2000

    def test_generate_vpn_error_909_success(self):
        llm_json = {
            "short_description": "VPN connection fails with Error 909",
            "description": (
                "Issue Summary:\nGlobalProtect VPN disconnects unexpectedly with Error 909.\n\n"
                "Symptoms:\n- VPN disconnects every 5 minutes\n\n"
                "Troubleshooting Performed:\n1. Restarted GlobalProtect service\n\n"
                "Current Status:\nUNRESOLVED"
            ),
        }
        provider = _make_mock_provider(llm_json)

        history = [{"sender": "user", "text": "VPN connection fails with Error 909"}]
        state = _FakeState(
            current_issue="VPN Connection",
            completed_steps=[_FakeStep("Restarted GlobalProtect service")],
            error_codes=["ERROR 909"],
        )

        service = TicketSummaryService(ai_provider=provider)
        summary = service.generate(history, state)

        assert summary.short_description == "VPN connection fails with Error 909"
        assert summary.source == "gemini"

    def test_generate_outlook_crash_success(self):
        llm_json = {
            "short_description": "Outlook crashes while launching",
            "description": (
                "Issue Summary:\nMicrosoft Outlook crashes immediately upon startup.\n\n"
                "Symptoms:\n- Outlook crash on start\n\n"
                "Troubleshooting Performed:\n1. Launched Outlook in Safe Mode\n\n"
                "Current Status:\nUNRESOLVED"
            ),
        }
        provider = _make_mock_provider(llm_json)

        history = [{"sender": "user", "text": "Outlook crashes when launching"}]
        state = _FakeState(
            current_issue="Outlook Crash",
            completed_steps=[_FakeStep("Launched Outlook in Safe Mode")],
        )

        service = TicketSummaryService(ai_provider=provider)
        summary = service.generate(history, state)

        assert summary.short_description == "Outlook crashes while launching"

    def test_generate_printer_offline_success(self):
        llm_json = {
            "short_description": "Office printer is offline and non-responsive",
            "description": (
                "Issue Summary:\nFloor 2 printer is offline.\n\n"
                "Symptoms:\n- Print queue stuck\n\n"
                "Troubleshooting Performed:\n1. Restarted Print Spooler\n\n"
                "Current Status:\nUNRESOLVED"
            ),
        }
        provider = _make_mock_provider(llm_json)

        history = [{"sender": "user", "text": "Floor 2 printer is offline"}]
        state = _FakeState(
            current_issue="Printer Offline",
            completed_steps=[_FakeStep("Restarted Print Spooler")],
        )

        service = TicketSummaryService(ai_provider=provider)
        summary = service.generate(history, state)

        assert summary.short_description == "Office printer is offline and non-responsive"

    def test_generate_password_reset_success(self):
        llm_json = {
            "short_description": "Domain password reset requested",
            "description": (
                "Issue Summary:\nUser requested domain password reset.\n\n"
                "Symptoms:\n- Account locked out\n\n"
                "Troubleshooting Performed:\n1. Self-service portal verification\n\n"
                "Current Status:\nESCALATED"
            ),
        }
        provider = _make_mock_provider(llm_json)

        history = [{"sender": "user", "text": "Need password reset"}]
        state = _FakeState(
            current_issue="Password Reset",
            completed_steps=[_FakeStep("Self-service portal verification")],
        )

        service = TicketSummaryService(ai_provider=provider)
        summary = service.generate(history, state)

        assert summary.short_description == "Domain password reset requested"

    def test_fallback_on_llm_exception(self):
        provider = MagicMock()
        provider.generate_response.side_effect = RuntimeError("API unavailable")

        history = [{"sender": "user", "text": "Wi-Fi issue"}]
        state = _FakeState(current_issue="Wi-Fi Connection")

        service = TicketSummaryService(ai_provider=provider)
        summary = service.generate(history, state)

        assert summary.used_fallback is True
        assert summary.source == "deterministic"
        assert "Wi-Fi Connection" in summary.short_description

    def test_fallback_on_invalid_json(self):
        provider = MagicMock()
        resp = MagicMock()
        resp.text = "This is not json at all."
        provider.generate_response.return_value = resp

        history = [{"sender": "user", "text": "Outlook crash"}]
        state = _FakeState(current_issue="Outlook Crash")

        service = TicketSummaryService(ai_provider=provider)
        summary = service.generate(history, state)

        assert summary.used_fallback is True
        assert summary.source == "deterministic"

    def test_fallback_on_verification_failure(self):
        # LLM returns a hallucinated error code 999
        llm_json = {
            "short_description": "Wi-Fi failure with Error 999",
            "description": "Issue Summary:\nWi-Fi error 999.\n\nSymptoms:\n- No internet",
        }
        provider = _make_mock_provider(llm_json)

        history = [{"sender": "user", "text": "Wi-Fi is down"}]
        state = _FakeState(current_issue="Wi-Fi Connection", error_codes=[])

        service = TicketSummaryService(ai_provider=provider)
        summary = service.generate(history, state)

        # Because Error 999 was hallucinated, verification failed and triggered fallback
        assert summary.used_fallback is True
        assert summary.source == "deterministic"
        assert "999" not in summary.short_description

    def test_empty_conversation_history(self):
        service = TicketSummaryService(ai_provider=None)
        summary = service.generate(conversation_history=[], troubleshooting_state=None)

        assert summary.used_fallback is True
        assert len(summary.short_description) <= 120
        assert len(summary.description) <= 2000


# ── 5. Integration with TicketOrchestrator ─────────────────────────────────────

class TestTicketOrchestratorIntegration:

    @patch("app.services.ticket_service.create_ticket")
    @patch("app.services.conversation_memory.get_history")
    def test_ticket_orchestrator_uses_ticket_summary(self, mock_history, mock_create_ticket):
        from app.services.ticket_orchestrator import TicketOrchestrator

        mock_history.return_value = [
            {"sender": "user", "text": "My GlobalProtect VPN disconnects every 5 mins with Error 909"}
        ]
        mock_create_ticket.return_value = {
            "ticket_id": "INC0000001",
            "short_description": "VPN connection fails with Error 909",
            "description": "Issue Summary:\nVPN disconnects with Error 909.",
        }

        state = _FakeState(
            session_id="test-session-123",
            current_issue="VPN Connection",
            strategy_domain="vpn_guide",
            error_codes=["ERROR 909"],
        )
        state.category = "VPN"
        state.phase = MagicMock()
        state.phase.value = "WAITING_TICKET_CONFIRMATION"

        orchestrator = TicketOrchestrator()
        result = orchestrator.create(state, username="john.doe")

        # Verify create_ticket was called with short_description and description
        mock_create_ticket.assert_called_once()
        kwargs = mock_create_ticket.call_args.kwargs
        assert "short_description" in kwargs
        assert "description" in kwargs
        assert len(kwargs["short_description"]) <= 120
        assert len(kwargs["description"]) <= 2000
