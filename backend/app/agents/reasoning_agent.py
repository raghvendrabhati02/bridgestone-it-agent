import os
import json
import logging
from app.services.ai_provider import get_ai_provider

logger = logging.getLogger("it-agent-backend")


class ReasoningAgent:
    """
    Reflection Agent that reasons over diagnostic tool results and conversation history.

    Outputs a structured reflection with:
      - observations:         Human-readable list of facts found from tool data
      - hypotheses:           Likely causes or explanations for the issue
      - confidence:           float 0.0–1.0, how confident the agent is in its analysis
      - recommended_action:   One of known action codes or ""
      - findings:             Single natural language summary paragraph (used by ResponseAgent)
      - escalation_needed:    bool — should this immediately become a ticket?
      - approval_needed:      bool — does it require user approval before action?
      - rationale:            Short technical justification (used by DecisionAgent)
    """

    def __init__(self):
        self.provider = get_ai_provider()

    # ──────────────────────────────────────────────────────────
    # Public interface
    # ──────────────────────────────────────────────────────────

    def reflect(self, query: str, category: str, tool_result: dict, history: list[dict]) -> dict:
        """
        Full reflection pipeline.

        Args:
            query:       The raw user message that triggered the diagnostic.
            category:    Detected issue category (e.g. 'VPN', 'OUTLOOK').
            tool_result: Raw dict output from tool_node.
            history:     Conversation history list of {role, content} dicts.

        Returns a reflection dict with all 8 fields listed in the class docstring.
        """
        logger.info(
            "ReasoningAgent.reflect: category=%s, tool_result_present=%s",
            category,
            bool(tool_result),
        )

        # Always run rule-based as deterministic fallback
        fallback = self._reflect_rule_based(category, tool_result)

        # Try AI Provider for richer reflection
        if tool_result and tool_result.get("data"):
            try:
                prompt = self._build_reflection_prompt(query, category, tool_result, history)
                response = self.provider.generate_response(prompt)

                if response:
                    result = json.loads(response.strip())
                    # Validate required fields exist and are non-empty
                    if result.get("findings") and result.get("observations"):
                        logger.info(
                            "ReasoningAgent.reflect: AI provider reflection successful. "
                            "Confidence=%.2f, EscalationNeeded=%s",
                            result.get("confidence", 0.0),
                            result.get("escalation_needed", False),
                        )
                        return self._normalize_reflection(result)
            except Exception as e:
                logger.warning(
                    "ReasoningAgent.reflect: AI provider call failed (%s). Using rule-based fallback.", e
                )

        logger.info(
            "ReasoningAgent.reflect: Using rule-based fallback. Findings='%s'",
            fallback["findings"][:80],
        )
        return fallback

    # Legacy compatibility — still called by decision_service.py
    def reason_over_state(self, category: str, tool_result: dict, history: list[dict]) -> dict:
        """
        Legacy wrapper so existing decision_service.py callers still work.
        Internally delegates to reflect() with an empty query string.
        """
        return self.reflect(
            query="",
            category=category,
            tool_result=tool_result,
            history=history,
        )

    # ──────────────────────────────────────────────────────────
    # Prompt builder
    # ──────────────────────────────────────────────────────────

    def _build_reflection_prompt(
        self,
        query: str,
        category: str,
        tool_result: dict,
        history: list[dict],
    ) -> str:
        history_text = "\n".join(
            f"{m.get('role', 'user').capitalize()}: {m.get('content', '')}"
            for m in (history[-6:] if len(history) > 6 else history)
        )

        return (
            "You are an IT Support Reflection Agent for Bridgestone Corporation.\n"
            "Your role is to reason deeply over diagnostic tool outputs and produce a structured reflection.\n\n"
            "=== Instructions ===\n"
            "1. observations: List 2–4 concrete facts observed from the tool data (plain English, no JSON keys).\n"
            "   Example: 'The VPN gateway is reachable and responding normally.'\n"
            "2. hypotheses: List 1–3 likely root causes or explanations for the user's issue.\n"
            "   Example: 'Password change may have invalidated the VPN session token.'\n"
            "3. confidence: float from 0.0 to 1.0 expressing how certain you are of the analysis.\n"
            "4. recommended_action: One of: 'VPN_ACCESS_RESTORATION', 'SOFTWARE_INSTALLATION',\n"
            "   'OUTLOOK_RECONFIGURATION', 'NETWORK_RESET', 'ESCALATE_TO_L2', '' (empty if none).\n"
            "5. findings: One clear paragraph summarizing what is wrong and what should happen next.\n"
            "   Write in friendly, professional language for a non-technical user.\n"
            "6. escalation_needed: true if the issue requires immediate ticket creation by IT support.\n"
            "7. approval_needed: true if an action needs explicit user approval before execution.\n"
            "8. rationale: One sentence technical justification (for IT staff / logs).\n\n"
            "=== Context ===\n"
            f"User Query: {query}\n"
            f"Issue Category: {category}\n\n"
            "--- Recent Conversation History ---\n"
            f"{history_text if history_text.strip() else '(No history)'}\n"
            "--- End History ---\n\n"
            "--- Raw Tool Diagnostic Output ---\n"
            f"{json.dumps(tool_result, indent=2)}\n"
            "--- End Tool Output ---\n\n"
            "Return ONLY a valid JSON object with exactly these 8 keys:\n"
            "{\n"
            '  "observations": ["fact 1", "fact 2", ...],\n'
            '  "hypotheses": ["cause 1", "cause 2", ...],\n'
            '  "confidence": 0.85,\n'
            '  "recommended_action": "VPN_ACCESS_RESTORATION",\n'
            '  "findings": "Natural language summary paragraph...",\n'
            '  "escalation_needed": false,\n'
            '  "approval_needed": true,\n'
            '  "rationale": "Short technical justification."\n'
            "}"
        )

    # ──────────────────────────────────────────────────────────
    # Rule-based fallback
    # ──────────────────────────────────────────────────────────

    def _reflect_rule_based(self, category: str, tool_result: dict) -> dict:
        if not tool_result or "data" not in tool_result:
            return self._empty_reflection("No diagnostic tests have run yet for this session.")

        tool_name = tool_result.get("tool_name", "")
        tool_data = tool_result.get("data", {})

        if tool_name == "vpn_tools":
            return self._reflect_vpn(tool_data)
        elif tool_name == "outlook_tools":
            return self._reflect_outlook(tool_data)
        elif tool_name == "software_tools":
            return self._reflect_software(tool_data)
        elif tool_name == "network_tools":
            return self._reflect_network(tool_data)
        else:
            return self._reflect_generic(tool_name, tool_data)

    def _reflect_vpn(self, data: dict) -> dict:
        observations = []
        hypotheses = []
        escalation_needed = False
        approval_needed = False
        recommended_action = ""
        confidence = 0.75

        gateway = data.get("vpn_gateway", "UNKNOWN")
        user_access = data.get("user_access", "UNKNOWN")
        latency = data.get("latency_ms")
        auth = data.get("auth_status", "UNKNOWN")

        if gateway == "ONLINE":
            observations.append("The corporate VPN gateway is online and reachable from the network.")
        else:
            observations.append("The VPN gateway is currently offline or unreachable.")
            hypotheses.append("There may be a network outage or service disruption at the VPN gateway level.")
            escalation_needed = True
            confidence = 0.9

        if user_access == "DISABLED":
            observations.append("Your personal VPN account is currently disabled in the directory.")
            hypotheses.append(
                "A recent password change or policy update may have locked or expired your VPN credentials."
            )
            approval_needed = True
            recommended_action = "VPN_ACCESS_RESTORATION"
            confidence = 0.9
        elif user_access == "ACTIVE":
            observations.append("Your account is active and has VPN access permissions.")

        if latency:
            observations.append(f"VPN connection response time is {latency} ms, which is within normal range.")

        if auth and auth not in ("UNKNOWN", "OK", "SUCCESS"):
            observations.append(f"Authentication status reported as '{auth}', which may indicate a credential issue.")
            hypotheses.append("Session token or certificate may have expired after password change.")

        findings = self._build_findings_paragraph(observations, recommended_action)
        rationale = "VPN gateway is online; user-level access is disabled — restoration action required."

        return self._normalize_reflection({
            "observations": observations,
            "hypotheses": hypotheses,
            "confidence": confidence,
            "recommended_action": recommended_action,
            "findings": findings,
            "escalation_needed": escalation_needed,
            "approval_needed": approval_needed,
            "rationale": rationale,
        })

    def _reflect_outlook(self, data: dict) -> dict:
        observations = []
        hypotheses = []
        escalation_needed = False
        approval_needed = False
        recommended_action = ""
        confidence = 0.75

        mailbox = data.get("mailbox_status", "UNKNOWN")
        exchange = data.get("exchange_server", "UNKNOWN")
        latency = data.get("exchange_latency")

        if mailbox == "ACTIVE":
            observations.append("Your email mailbox is active and provisioned on the Exchange server.")
        else:
            observations.append(f"Mailbox status is reported as '{mailbox}', which is abnormal.")
            hypotheses.append("The mailbox may have been disabled or the license may have expired.")
            recommended_action = "OUTLOOK_RECONFIGURATION"
            confidence = 0.85

        if exchange == "ONLINE":
            observations.append("The Microsoft Exchange mail server is online and accepting connections.")
        else:
            observations.append("The Microsoft Exchange server appears to be offline or degraded.")
            hypotheses.append("A server-side outage may be preventing mail delivery and sync.")
            escalation_needed = True
            confidence = 0.9

        if latency:
            observations.append(f"Exchange server response latency is {latency} ms.")

        findings = self._build_findings_paragraph(observations, recommended_action)
        rationale = "Outlook tools diagnostic — mailbox and Exchange server status evaluated."

        return self._normalize_reflection({
            "observations": observations,
            "hypotheses": hypotheses,
            "confidence": confidence,
            "recommended_action": recommended_action,
            "findings": findings,
            "escalation_needed": escalation_needed,
            "approval_needed": approval_needed,
            "rationale": rationale,
        })

    def _reflect_software(self, data: dict) -> dict:
        observations = []
        hypotheses = []
        escalation_needed = False
        approval_needed = False
        recommended_action = ""
        confidence = 0.80

        software = data.get("software", "Software")
        approved = data.get("approved", False)
        permissions = data.get("permissions", "DENIED")

        if approved:
            observations.append(
                f"{software} is listed in the Bridgestone approved software catalog."
            )
        else:
            observations.append(f"{software} is not currently approved for standard installation.")
            hypotheses.append(
                f"{software} may require IT procurement or a security review before it can be installed."
            )

        if permissions == "ALLOWED":
            observations.append("You have the necessary local admin permissions to install software.")
        else:
            observations.append("You do not have local administrative privileges for software installation.")
            hypotheses.append("Your device is enrolled in a policy that restricts self-service software installs.")
            approval_needed = True
            recommended_action = "SOFTWARE_INSTALLATION"

        findings = self._build_findings_paragraph(observations, recommended_action)
        rationale = "Software catalog check and permission evaluation completed."

        return self._normalize_reflection({
            "observations": observations,
            "hypotheses": hypotheses,
            "confidence": confidence,
            "recommended_action": recommended_action,
            "findings": findings,
            "escalation_needed": escalation_needed,
            "approval_needed": approval_needed,
            "rationale": rationale,
        })

    def _reflect_network(self, data: dict) -> dict:
        observations = []
        hypotheses = []
        escalation_needed = False
        approval_needed = False
        recommended_action = ""
        confidence = 0.75

        status = data.get("network_status", "UNKNOWN")
        packet_loss = data.get("packet_loss", "UNKNOWN")
        wifi = data.get("wifi_status", "UNKNOWN")
        ssid = data.get("ssid", "UNKNOWN")

        if status == "ONLINE":
            observations.append("Your internet connection is active and reachable.")
        else:
            observations.append("Your internet connection is currently offline.")
            hypotheses.append("Local network adapter failure, router issue, or ISP outage may be the cause.")
            recommended_action = "NETWORK_RESET"
            escalation_needed = True
            confidence = 0.88

        if wifi == "CONNECTED":
            observations.append(f"Wi-Fi is connected to the network '{ssid}'.")
        else:
            observations.append("Wi-Fi is currently disconnected or unable to associate with a network.")
            hypotheses.append("The device may be out of range or the SSID credentials may have changed.")

        if packet_loss not in ("UNKNOWN", "0%", "0"):
            observations.append(f"Packet loss detected: {packet_loss}. This may cause intermittent connectivity.")

        findings = self._build_findings_paragraph(observations, recommended_action)
        rationale = "Network diagnostic — connectivity, Wi-Fi status, and packet loss evaluated."

        return self._normalize_reflection({
            "observations": observations,
            "hypotheses": hypotheses,
            "confidence": confidence,
            "recommended_action": recommended_action,
            "findings": findings,
            "escalation_needed": escalation_needed,
            "approval_needed": approval_needed,
            "rationale": rationale,
        })

    def _reflect_generic(self, tool_name: str, data: dict) -> dict:
        findings = f"Diagnostic check completed for {tool_name}. Please review the results with your IT team."
        return self._normalize_reflection({
            "observations": [f"Tool '{tool_name}' executed and returned data successfully."],
            "hypotheses": ["Refer to IT support for further analysis of the diagnostic output."],
            "confidence": 0.5,
            "recommended_action": "",
            "findings": findings,
            "escalation_needed": False,
            "approval_needed": False,
            "rationale": f"Generic fallback for tool: {tool_name}.",
        })

    # ──────────────────────────────────────────────────────────
    # Helpers
    # ──────────────────────────────────────────────────────────

    def _build_findings_paragraph(self, observations: list, recommended_action: str) -> str:
        if not observations:
            return "Diagnostic completed. No significant issues were detected at this time."
        base = " ".join(observations)
        if recommended_action:
            base += (
                " Based on these findings, I recommend we proceed with a resolution action. "
                "Please confirm to continue."
            )
        return base

    def _empty_reflection(self, message: str) -> dict:
        return {
            "observations": [message],
            "hypotheses": [],
            "confidence": 0.0,
            "recommended_action": "",
            "findings": message,
            "escalation_needed": False,
            "approval_needed": False,
            "rationale": "No tool results available.",
        }

    def _normalize_reflection(self, raw: dict) -> dict:
        """Ensure all 8 required keys exist with correct types."""
        return {
            "observations": raw.get("observations") or [],
            "hypotheses": raw.get("hypotheses") or [],
            "confidence": float(raw.get("confidence", 0.5)),
            "recommended_action": str(raw.get("recommended_action", "")),
            "findings": str(raw.get("findings", "")),
            "escalation_needed": bool(raw.get("escalation_needed", False)),
            "approval_needed": bool(raw.get("approval_needed", False)),
            "rationale": str(raw.get("rationale", "")),
        }
