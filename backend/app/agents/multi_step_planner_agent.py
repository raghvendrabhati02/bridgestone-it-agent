import os
import json
import logging
import google.generativeai as genai

logger = logging.getLogger("it-agent-backend")

class MultiStepPlannerAgent:
    """
    Agent that decides the next troubleshooting step.
    Determines if additional diagnostic tools are needed or if we have sufficient info to diagnose.
    """

    def __init__(self):
        self.api_key = os.getenv("GEMINI_API_KEY")
        if self.api_key:
            genai.configure(api_key=self.api_key)

    def plan_next_step(
        self,
        category: str,
        tool_chain: list[dict],
        hypotheses: list[dict],
        user_message: str
    ) -> str | None:
        """
        Determines the next tool to run based on current history, tool chain, and hypotheses.
        Returns a category name (e.g. "VPN", "NETWORK", "OUTLOOK", "SOFTWARE_INSTALLATION") or None if done.
        """
        logger.info(
            "MultiStepPlannerAgent: planning next step. Category: %s, Tool chain length: %d",
            category,
            len(tool_chain)
        )

        # 1. Always check rule-based logic first as fallback / primary decision driver
        rule_based_next = self._plan_rule_based(category, tool_chain)

        # 2. Try Gemini to see if it can enrich/improve the decision, falling back to rule-based
        if self.api_key:
            try:
                prompt = self._build_planner_prompt(category, tool_chain, hypotheses, user_message)
                model = genai.GenerativeModel("gemini-2.5-flash-lite")
                response = model.generate_content(
                    prompt,
                    generation_config={"response_mime_type": "application/json"},
                    request_options={"timeout": 10.0}
                )
                if response and response.text:
                    result = json.loads(response.text.strip())
                    next_tool = result.get("next_tool")
                    # Normalize next_tool to None if "NONE" or empty
                    if next_tool in ("NONE", "", None):
                        next_tool = None
                    else:
                        next_tool = str(next_tool).upper().strip()
                        if next_tool not in ("VPN", "NETWORK", "OUTLOOK", "SOFTWARE_INSTALLATION"):
                            next_tool = None
                    
                    logger.info("MultiStepPlannerAgent: Gemini selected next tool: %s", next_tool)
                    return next_tool
            except Exception as e:
                logger.warning("MultiStepPlannerAgent: Gemini call failed (%s). Using rule-based fallback.", e)

        logger.info("MultiStepPlannerAgent: Using rule-based decision: %s", rule_based_next)
        return rule_based_next

    def _plan_rule_based(self, category: str, tool_chain: list[dict]) -> str | None:
        cat_upper = category.upper().strip()

        # Find which tools have run in this tool chain
        ran_vpn = any(t.get("tool_name") == "vpn_tools" for t in tool_chain)
        ran_network = any(t.get("tool_name") == "network_tools" for t in tool_chain)
        ran_outlook = any(t.get("tool_name") == "outlook_tools" for t in tool_chain)
        ran_software = any(t.get("tool_name") == "software_tools" for t in tool_chain)

        # Retrieve outputs of run tools for condition checks
        vpn_data = next((t.get("data", {}) for t in tool_chain if t.get("tool_name") == "vpn_tools"), {})
        network_data = next((t.get("data", {}) for t in tool_chain if t.get("tool_name") == "network_tools"), {})
        outlook_data = next((t.get("data", {}) for t in tool_chain if t.get("tool_name") == "outlook_tools"), {})

        if cat_upper == "VPN":
            if not ran_vpn:
                return "VPN"
            # If VPN tools ran, check gateway and access
            gateway = vpn_data.get("vpn_gateway", "UNKNOWN")
            user_access = vpn_data.get("user_access", "UNKNOWN")
            
            if gateway == "ONLINE" and user_access == "ACTIVE":
                # Gateway is healthy and user access is active, but they still have an issue.
                # Check local network connectivity.
                if not ran_network:
                    return "NETWORK"
            # If we already ran network or gateway/access suggests specific failure, stop.
            return None

        elif cat_upper == "OUTLOOK":
            if not ran_outlook:
                return "OUTLOOK"
            mailbox = outlook_data.get("mailbox_status", "UNKNOWN")
            exchange = outlook_data.get("exchange_server", "UNKNOWN")

            if exchange == "ONLINE" and mailbox == "ACTIVE":
                # Outlook infrastructure is healthy, let's run network tools to check user-side internet connection.
                if not ran_network:
                    return "NETWORK"
            return None

        elif cat_upper == "NETWORK":
            if not ran_network:
                return "NETWORK"
            return None

        elif cat_upper == "SOFTWARE_INSTALLATION":
            if not ran_software:
                return "SOFTWARE_INSTALLATION"
            return None

        # If it's general or other, just stop after the first default tool run if any
        if not tool_chain:
            return cat_upper
        return None

    def _build_planner_prompt(
        self,
        category: str,
        tool_chain: list[dict],
        hypotheses: list[dict],
        user_message: str
    ) -> str:
        return f"""You are an IT support Multi-Step Planner Agent for Bridgestone.
Your job is to decide whether we need to run another diagnostic tool, or if we have collected enough evidence to diagnose and resolve the issue.

Available Tools:
- VPN: Check VPN access, gateway and latency.
- NETWORK: Check Wi-Fi and ethernet connectivity, packet loss, local networks.
- OUTLOOK: Check mailbox status and exchange server connectivity.
- SOFTWARE_INSTALLATION: Check software availability, install permissions.

=== Rules ===
1. VPN issues: First check VPN. If VPN infrastructure is healthy (gateway ONLINE, access ACTIVE), check local NETWORK connectivity. If NETWORK is also healthy or already ran, stop.
2. OUTLOOK issues: First check OUTLOOK. If Outlook infrastructure is healthy (exchange ONLINE, mailbox ACTIVE), check local NETWORK connectivity. If NETWORK already ran, stop.
3. NETWORK issues: Run NETWORK tools, then stop.
4. SOFTWARE_INSTALLATION issues: Run SOFTWARE_INSTALLATION tools, then stop.
5. If the issue is already diagnosed or the critical failure is found (e.g. user_access is DISABLED), STOP running tools immediately.

=== Context ===
User Message: {user_message}
Current Issue Category: {category}
Tool Chain So Far: {json.dumps(tool_chain, indent=2)}
Hypotheses: {json.dumps(hypotheses, indent=2)}

Return ONLY a valid JSON object with the "next_tool" key. Value must be one of: "VPN", "NETWORK", "OUTLOOK", "SOFTWARE_INSTALLATION", or null/"NONE" if no further tools are needed.

JSON:
{{
  "next_tool": "NETWORK"
}}
"""
