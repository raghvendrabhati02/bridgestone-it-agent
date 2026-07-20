import os
import logging
from app.services.ai_provider import get_ai_provider

logger = logging.getLogger("it-agent-backend")

class EngineerSummaryAgent:
    """
    Agent that generates a rich Markdown IT diagnostic report/summary after diagnostics are complete.
    """

    def __init__(self):
        self.provider = get_ai_provider()

    def generate_summary(
        self,
        category: str,
        tool_chain: list[dict],
        hypotheses: list[dict],
        user_message: str
    ) -> str:
        """
        Generates a rich Markdown IT Diagnostic Report.
        """
        logger.info(
            "EngineerSummaryAgent: Generating report for category %s, chain length: %d",
            category,
            len(tool_chain)
        )

        # 1. Generate programmatic fallback report first
        fallback_report = self._generate_fallback(category, tool_chain, hypotheses, user_message)

        # 2. Try AI Provider for a richer, more professional narrative
        try:
            prompt = self._build_summary_prompt(category, tool_chain, hypotheses, user_message)
            response = self.provider.generate_response(prompt)
            if response:
                parsed_report = response.strip()
                if "## IT Diagnostic Report" in parsed_report or "### Tools Executed" in parsed_report:
                    logger.info("EngineerSummaryAgent: Rich report generated successfully by AI provider.")
                    return parsed_report
        except Exception as e:
            logger.warning("EngineerSummaryAgent: AI provider generation failed (%s). Using programmatic report.", e)

        logger.info("EngineerSummaryAgent: Using fallback programmatic report.")
        return fallback_report

    def _generate_fallback(
        self,
        category: str,
        tool_chain: list[dict],
        hypotheses: list[dict],
        user_message: str
    ) -> str:
        # Programmatic formatting of tools executed
        tools_section = ""
        for tool in tool_chain:
            tool_name = tool.get("tool_name", "unknown_tool")
            status = tool.get("status", "SUCCESS")
            data = tool.get("data", {})
            
            # Format status icon
            icon = "✅" if status == "SUCCESS" else "❌"
            
            # Format brief description
            details = []
            for k, v in data.items():
                details.append(f"{k}={v}")
            details_str = ", ".join(details)
            
            tools_section += f"- {icon} **{tool_name.replace('_', ' ').title()}**: {details_str}\n"

        if not tools_section:
            tools_section = "- ⚠️ No diagnostic tools were executed.\n"

        # Determine highest confidence hypothesis
        root_cause = "Could not identify definitive root cause."
        confidence_val = 50
        recommended_action = "ESCALATE_TO_L2"
        
        active_or_confirmed = [h for h in hypotheses if h.get("status") in ("ACTIVE", "CONFIRMED")]
        if active_or_confirmed:
            # Sort by confidence descending
            sorted_hyp = sorted(active_or_confirmed, key=lambda x: x.get("confidence", 0), reverse=True)
            best_hyp = sorted_hyp[0]
            root_cause = best_hyp.get("hypothesis", root_cause)
            confidence_val = int(best_hyp.get("confidence", 0.5) * 100)
            
            # Formulate recommended action based on hypothesis
            hyp_text = root_cause.lower()
            if "disabled" in hyp_text or "lock" in hyp_text:
                recommended_action = "VPN_ACCESS_RESTORATION"
            elif "approved" in hyp_text or "privilege" in hyp_text:
                recommended_action = "SOFTWARE_INSTALLATION"
            elif "exchange" in hyp_text or "mailbox" in hyp_text:
                recommended_action = "OUTLOOK_RECONFIGURATION"
            elif "local network" in hyp_text or "wifi" in hyp_text:
                recommended_action = "NETWORK_RESET"
            else:
                recommended_action = "ESCALATE_TO_L2"

        report = f"""## IT Diagnostic Report — {category.upper()} Issue

### Tools Executed ({len(tool_chain)}/{len(tool_chain)})
{tools_section}
### Root Cause
{root_cause}

### Recommended Action
**{recommended_action}** — Take action to address the root cause specified above.

### Confidence: {confidence_val}%
"""
        return report

    def _build_summary_prompt(
        self,
        category: str,
        tool_chain: list[dict],
        hypotheses: list[dict],
        user_message: str
    ) -> str:
        return f"""You are an IT Support Engineer for Bridgestone.
Your job is to generate a rich, professional, Markdown-formatted IT Diagnostic Report based on the troubleshooting data.

Structure requirements:
1. Title: "## IT Diagnostic Report — [Category] Issue"
2. Tools Executed Section: "### Tools Executed (X/X)" followed by a bulleted list of tools with a checkmark emoji and their result summary.
3. Root Cause Section: "### Root Cause" followed by a concise explanation of what is wrong.
4. Recommended Action Section: "### Recommended Action" followed by the action name (e.g. VPN_ACCESS_RESTORATION, SOFTWARE_INSTALLATION, OUTLOOK_RECONFIGURATION, NETWORK_RESET, ESCALATE_TO_L2) and brief instruction.
5. Confidence Section: "### Confidence: X%"

=== Context ===
Category: {category}
User Query: {user_message}
Tool Chain: {tool_chain}
Hypotheses: {hypotheses}

Generate ONLY the Markdown report (do not wrap in ```markdown code fences).

Markdown:
"""
