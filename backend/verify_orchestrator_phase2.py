"""
Verify Phase 2 agentic execution loop without making live API calls.
Tests: AST, imports, logic gates, ToolRouter integration, error paths.
"""
import ast, json, sys
from unittest.mock import patch, MagicMock

# ── 1. AST checks ─────────────────────────────────────────────────────────────
for f in ['app/services/orchestrator_service.py', 'app/services/prompt_builder.py']:
    ast.parse(open(f, encoding='utf-8').read())
    print('AST OK:', f)

# ── 2. PromptBuilder new function ─────────────────────────────────────────────
from app.services.prompt_builder import build_tool_result_prompt, build_decision_prompt
trp = build_tool_result_prompt()
assert isinstance(trp, str) and 'NEVER' in trp and len(trp) > 100
print('build_tool_result_prompt(): OK  len=%d' % len(trp))

# ── 3. OrchestratorService imports cleanly ────────────────────────────────────
import app.services.orchestrator_service as orch
assert callable(orch.generate_decision)
assert callable(orch.generate_turn)
assert callable(orch._synthesize_tool_response)
print('orchestrator_service imports: OK')
print('  generate_decision callable:', callable(orch.generate_decision))
print('  generate_turn callable:    ', callable(orch.generate_turn))
print('  _synthesize_tool_response: ', callable(orch._synthesize_tool_response))

# ── 4. Gate: tool=None → returns assistant_message immediately ────────────────
mock_decision_no_tool = {
    "assistant_message": "Tell me more about your issue.",
    "intent": "GENERAL_SUPPORT",
    "tool": None,
    "parameters": {},
    "confidence": 0.8,
    "requires_confirmation": False,
}
with patch.object(orch, 'generate_decision', return_value=mock_decision_no_tool):
    with patch.object(orch, 'tool_router') as mock_router:
        result = orch.generate_turn("VPN", [], "my vpn is down")
        mock_router.route.assert_not_called()
        assert result == "Tell me more about your issue."
        print('Gate (tool=None → no ToolRouter call): OK')

# ── 5. Gate: requires_confirmation=True → returns assistant_message, no tool ──
mock_decision_confirm = {
    "assistant_message": "I can reset your VPN access. Shall I proceed?",
    "intent": "VPN_ACCESS_RESTORE",
    "tool": "VPN_ACCESS_RESTORE",
    "parameters": {},
    "confidence": 0.95,
    "requires_confirmation": True,
}
with patch.object(orch, 'generate_decision', return_value=mock_decision_confirm):
    with patch.object(orch, 'tool_router') as mock_router:
        result = orch.generate_turn("VPN", [], "reset my vpn")
        mock_router.route.assert_not_called()
        assert result == "I can reset your VPN access. Shall I proceed?"
        print('Gate (requires_confirmation=True → no ToolRouter call): OK')

# ── 6. Full loop: tool present, no confirmation → ToolRouter called once ──────
mock_decision_act = {
    "assistant_message": "I'll install VS Code for you.",
    "intent": "INSTALL_SOFTWARE",
    "tool": "INSTALL_SOFTWARE",
    "parameters": {"software": "VS Code"},
    "confidence": 0.98,
    "requires_confirmation": False,
}
mock_tool_result = {
    "tool": "INSTALL_SOFTWARE",
    "status": "SUCCESS",
    "data": {"request_id": "REQ000001"},
    "message": "Software install request created for 'VS Code'.",
}
with patch.object(orch, 'generate_decision', return_value=mock_decision_act):
    with patch.object(orch, 'tool_router') as mock_router:
        mock_router.route.return_value = mock_tool_result
        with patch.object(orch, '_synthesize_tool_response', return_value="VS Code will be installed shortly.") as mock_synth:
            result = orch.generate_turn("SOFTWARE_INSTALLATION", [], "install vs code")
            mock_router.route.assert_called_once_with({
                "tool": "INSTALL_SOFTWARE",
                "parameters": {"software": "VS Code"},
            })
            mock_synth.assert_called_once_with(tool_result=mock_tool_result, category="SOFTWARE_INSTALLATION")
            assert result == "VS Code will be installed shortly."
            print('Full loop (tool → ToolRouter called once → synthesize): OK')

# ── 7. ToolRouter exception → clean fallback (never raises) ───────────────────
with patch.object(orch, 'generate_decision', return_value=mock_decision_act):
    with patch.object(orch, 'tool_router') as mock_router:
        mock_router.route.side_effect = RuntimeError("Unexpected crash")
        result = orch.generate_turn("SOFTWARE_INSTALLATION", [], "install vs code")
        assert "technical issue" in result.lower() or "support ticket" in result.lower()
        print('ToolRouter exception → clean fallback (no raise): OK')

# ── 8. _synthesize_tool_response: GeminiService error → status-based fallback ─
success_result  = {"tool": "INSTALL_SOFTWARE", "status": "SUCCESS",     "data": {}, "message": "Done."}
placeholder_res = {"tool": "CHECK_DEVICE_HEALTH", "status": "PLACEHOLDER", "data": {}, "message": "Pending."}
error_result    = {"tool": "CREATE_TICKET",  "status": "ERROR",       "data": {}, "message": "Failed."}

with patch.object(orch._gemini, 'chat', return_value="[GeminiService Error] quota"):
    fb_success     = orch._synthesize_tool_response(success_result, "SOFTWARE")
    fb_placeholder = orch._synthesize_tool_response(placeholder_res, "DEVICE")
    fb_error       = orch._synthesize_tool_response(error_result, "TICKET")
    assert "submitted successfully" in fb_success or "follow up" in fb_success
    assert "not yet" in fb_placeholder.lower() or "pending" in fb_placeholder.lower() or "prepared" in fb_placeholder.lower()
    assert "issue" in fb_error.lower() or "ticket" in fb_error.lower()
    print('_synthesize_tool_response (Gemini error → status fallbacks): OK')

print('\nAll Phase 2 checks passed.')
