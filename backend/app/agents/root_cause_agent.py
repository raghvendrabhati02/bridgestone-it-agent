"""
Root Cause Agent — deterministic reasoning over tool diagnostics.

Sits between tool_node and reflection_node in the graph.
Produces structured root-cause analysis that reflection_node
and decision_node can consume instead of raw tool output.

Output schema:
{
    "observations":        [str],   # facts extracted from tool_result
    "possible_causes":     [str],   # ranked from most to least likely
    "confidence":          float,   # 0.0 – 1.0
    "recommended_action":  str,     # action code or ""
    "summary":             str,     # plain-English paragraph for the user
}
"""

import json
import logging
import os
import re

logger = logging.getLogger("it-agent-backend")


class RootCauseAgent:
    """Deterministic root-cause analyser with optional Gemini enrichment."""

    def __init__(self):
        self.api_key = os.getenv("GEMINI_API_KEY")

    # ──────────────────────────────────────────────────────────
    # Public API
    # ──────────────────────────────────────────────────────────

    def analyze(
        self,
        *,
        category: str,
        user_message: str,
        tool_result: dict,
        knowledge_context: str = "",
    ) -> dict:
        """
        Run root-cause analysis.

        Always returns a valid dict — never throws.
        """
        logger.info(
            "RootCauseAgent.analyze: category=%s, tool_present=%s",
            category,
            bool(tool_result),
        )

        try:
            # Step 1 — deterministic rule-based analysis
            analysis = self._analyze_rules(category, user_message, tool_result)

            # Step 2 — optional Gemini enrichment
            if self.api_key and tool_result and tool_result.get("data"):
                enriched = self._try_gemini(
                    category, user_message, tool_result, knowledge_context
                )
                if enriched:
                    analysis = enriched

            logger.info(
                "RootCauseAgent: confidence=%.2f, causes=%d, action='%s'",
                analysis.get("confidence", 0.0),
                len(analysis.get("possible_causes", [])),
                analysis.get("recommended_action", ""),
            )
            return analysis

        except Exception as e:
            logger.error("RootCauseAgent.analyze: unexpected error: %s", e, exc_info=True)
            return self._empty_analysis(
                "Root cause analysis could not complete due to an internal error."
            )

    # ──────────────────────────────────────────────────────────
    # Rule engine
    # ──────────────────────────────────────────────────────────

    def _analyze_rules(self, category: str, user_message: str, tool_result: dict) -> dict:
        cat = category.upper()
        if cat == "VPN":
            return self._analyze_vpn(user_message, tool_result)
        elif cat == "OUTLOOK":
            return self._analyze_outlook(user_message, tool_result)
        elif cat == "NETWORK":
            return self._analyze_network(user_message, tool_result)
        elif cat == "SOFTWARE":
            return self._analyze_software(user_message, tool_result)
        else:
            return self._analyze_generic(category, user_message, tool_result)

    # ── VPN ───────────────────────────────────────────────────

    def _analyze_vpn(self, user_message: str, tool_result: dict) -> dict:
        data = (tool_result or {}).get("data", {})
        msg_lower = user_message.lower()

        observations = []
        causes = []
        confidence = 0.70
        action = ""

        gateway = data.get("vpn_gateway", "UNKNOWN")
        access = data.get("user_access", "UNKNOWN")
        auth = data.get("auth_status", "UNKNOWN")

        # Infrastructure check
        if gateway == "ONLINE":
            observations.append("VPN infrastructure is healthy — the corporate gateway is online and responding.")
        else:
            observations.append("The VPN gateway is offline or unreachable.")
            causes.append("VPN gateway outage or scheduled maintenance")
            confidence = 0.90

        # Account check
        if access == "ACTIVE":
            observations.append(
                "Your VPN account is active with valid permissions."
            )
        elif access == "DISABLED":
            observations.append("Your VPN account is currently disabled in the directory.")
            causes.append("Account disabled after security policy enforcement")
            action = "VPN_ACCESS_RESTORATION"
            confidence = max(confidence, 0.85)

        # Context clues from user message
        if any(kw in msg_lower for kw in ("password", "changed password", "reset password")):
            causes.insert(0, "Cached credentials after password change")
            if not action:
                action = "VPN_ACCESS_RESTORATION"
            confidence = max(confidence, 0.78)
        if any(kw in msg_lower for kw in ("token", "certificate", "cert")):
            causes.append("Expired VPN token or certificate")
            confidence = max(confidence, 0.75)
        if any(kw in msg_lower for kw in ("client", "app", "application", "software")):
            causes.append("VPN client-side configuration issue")

        if auth not in ("UNKNOWN", "OK", "SUCCESS"):
            observations.append(f"Authentication status: '{auth}' — may indicate credential mismatch.")
            if "Credential mismatch" not in " ".join(causes):
                causes.append("Credential mismatch between client and directory")

        # Ensure at least one cause
        if not causes and gateway == "ONLINE" and access == "ACTIVE":
            causes.append("VPN client-side configuration issue")
            causes.append("Local firewall or proxy interference")

        summary = self._build_summary(observations, causes, action)
        return self._normalize(observations, causes, confidence, action, summary)

    # ── OUTLOOK ──────────────────────────────────────────────

    def _analyze_outlook(self, user_message: str, tool_result: dict) -> dict:
        data = (tool_result or {}).get("data", {})
        msg_lower = user_message.lower()

        observations = []
        causes = []
        confidence = 0.70
        action = ""

        mailbox = data.get("mailbox_status", "UNKNOWN")
        exchange = data.get("exchange_server", "UNKNOWN")

        if exchange == "ONLINE":
            observations.append("Exchange server is online and accepting connections.")
        else:
            observations.append("Exchange server appears offline or degraded.")
            causes.append("Exchange server outage or maintenance window")
            confidence = 0.90

        if mailbox == "ACTIVE":
            observations.append("Your mailbox is active and provisioned.")
        else:
            observations.append(f"Mailbox status is '{mailbox}' — not fully functional.")
            causes.append("Mailbox corruption or license expiry")
            action = "OUTLOOK_RECONFIGURATION"
            confidence = max(confidence, 0.85)

        if any(kw in msg_lower for kw in ("sync", "syncing", "not syncing")):
            causes.append("Outlook sync profile desynchronisation")
        if any(kw in msg_lower for kw in ("password", "login", "auth")):
            causes.append("Authentication issue after password change")
        if any(kw in msg_lower for kw in ("send", "receive", "stuck")):
            causes.append("Send/receive queue stuck due to connectivity interruption")

        if not causes and exchange == "ONLINE" and mailbox == "ACTIVE":
            causes.append("Client-side Outlook profile corruption")
            causes.append("Cached authentication token expired")

        summary = self._build_summary(observations, causes, action)
        return self._normalize(observations, causes, confidence, action, summary)

    # ── NETWORK ──────────────────────────────────────────────

    def _analyze_network(self, user_message: str, tool_result: dict) -> dict:
        data = (tool_result or {}).get("data", {})
        msg_lower = user_message.lower()

        observations = []
        causes = []
        confidence = 0.70
        action = ""

        status = data.get("network_status", "UNKNOWN")
        packet_loss = data.get("packet_loss", "0%")
        wifi = data.get("wifi_status", "UNKNOWN")

        if status == "ONLINE":
            observations.append("Internet connectivity is active.")
        else:
            observations.append("Internet connectivity is down.")
            causes.append("ISP outage or local router failure")
            action = "NETWORK_RESET"
            confidence = 0.88

        if wifi == "CONNECTED":
            observations.append("Wi-Fi adapter is connected.")
        else:
            observations.append("Wi-Fi is disconnected.")
            causes.append("Wi-Fi adapter failure or SSID mismatch")

        if packet_loss not in ("0%", "0", "UNKNOWN"):
            observations.append(f"Packet loss detected: {packet_loss}.")
            causes.append("Network congestion or faulty cable/adapter")

        if "dns" in msg_lower:
            causes.append("DNS resolution failure")
        if "firewall" in msg_lower:
            causes.append("Firewall blocking required traffic")

        if not causes:
            causes.append("Intermittent connectivity issue")

        summary = self._build_summary(observations, causes, action)
        return self._normalize(observations, causes, confidence, action, summary)

    # ── SOFTWARE ─────────────────────────────────────────────

    def _analyze_software(self, user_message: str, tool_result: dict) -> dict:
        data = (tool_result or {}).get("data", {})

        observations = []
        causes = []
        confidence = 0.80
        action = ""

        approved = data.get("approved", False)
        permissions = data.get("permissions", "DENIED")
        software = data.get("software", "the requested software")

        if approved:
            observations.append(f"{software} is in the approved software catalog.")
        else:
            observations.append(f"{software} is not in the approved catalog.")
            causes.append("Software not approved for deployment")

        if permissions == "ALLOWED":
            observations.append("You have installation permissions.")
        else:
            observations.append("Your account lacks installation permissions.")
            causes.append("Restricted local admin policy on device")
            action = "SOFTWARE_INSTALLATION"

        if not causes:
            causes.append("Installation may require IT assistance")

        summary = self._build_summary(observations, causes, action)
        return self._normalize(observations, causes, confidence, action, summary)

    # ── GENERIC ──────────────────────────────────────────────

    def _analyze_generic(self, category: str, user_message: str, tool_result: dict) -> dict:
        observations = ["Diagnostic tools executed for this category."]
        causes = ["Further analysis by IT support is recommended."]
        return self._normalize(observations, causes, 0.50, "", 
            f"A diagnostic check was completed for {category}. "
            "Please consult the IT support team for a detailed review."
        )

    # ──────────────────────────────────────────────────────────
    # Gemini enrichment (optional, never crashes)
    # ──────────────────────────────────────────────────────────

    def _try_gemini(self, category, user_message, tool_result, knowledge_context) -> dict | None:
        try:
            import google.generativeai as genai
            genai.configure(api_key=self.api_key)

            prompt = (
                "You are a Root Cause Analysis agent for Bridgestone IT Support.\n"
                f"Category: {category}\n"
                f"User Message: {user_message}\n"
                f"Tool Result: {json.dumps(tool_result, indent=2)}\n"
                f"Knowledge Context: {knowledge_context[:500] if knowledge_context else 'None'}\n\n"
                "Return ONLY a valid JSON object:\n"
                "{\n"
                '  "observations": ["fact 1", ...],\n'
                '  "possible_causes": ["cause 1 (most likely)", ...],\n'
                '  "confidence": 0.85,\n'
                '  "recommended_action": "VPN_ACCESS_RESTORATION or empty",\n'
                '  "summary": "Plain English paragraph"\n'
                "}\n"
            )

            model = genai.GenerativeModel("gemini-2.5-flash-lite")
            response = model.generate_content(
                prompt,
                generation_config={"response_mime_type": "application/json"},
                request_options={"timeout": 10.0},
            )
            if response and response.text:
                result = json.loads(response.text.strip())
                if result.get("observations") and result.get("possible_causes"):
                    return self._normalize(
                        result["observations"],
                        result["possible_causes"],
                        float(result.get("confidence", 0.5)),
                        result.get("recommended_action", ""),
                        result.get("summary", ""),
                    )
        except Exception as e:
            logger.warning("RootCauseAgent: Gemini enrichment failed: %s", e)
        return None

    # ──────────────────────────────────────────────────────────
    # Helpers
    # ──────────────────────────────────────────────────────────

    def _build_summary(self, observations: list, causes: list, action: str) -> str:
        parts = []
        if observations:
            parts.append(" ".join(observations))
        if causes:
            cause_text = causes[0] if len(causes) == 1 else (
                ", ".join(causes[:-1]) + f", or {causes[-1]}"
            )
            parts.append(f"The most likely cause is: {cause_text}.")
        if action:
            parts.append(
                "I recommend proceeding with a resolution action to address this."
            )
        return " ".join(parts) if parts else "Diagnostic completed."

    @staticmethod
    def _normalize(observations, causes, confidence, action, summary) -> dict:
        return {
            "observations": list(observations or []),
            "possible_causes": list(causes or []),
            "confidence": max(0.0, min(1.0, float(confidence))),
            "recommended_action": str(action or ""),
            "summary": str(summary or ""),
        }

    @staticmethod
    def _empty_analysis(message: str) -> dict:
        return {
            "observations": [message],
            "possible_causes": [],
            "confidence": 0.0,
            "recommended_action": "",
            "summary": message,
        }
