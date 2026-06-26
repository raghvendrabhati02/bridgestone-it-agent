import os
import json
import logging
import google.generativeai as genai

logger = logging.getLogger("it-agent-backend")

class HypothesisTrackerAgent:
    """
    Agent that manages and updates diagnostic hypotheses based on new evidence (tool results).
    """

    def __init__(self):
        self.api_key = os.getenv("GEMINI_API_KEY")
        if self.api_key:
            genai.configure(api_key=self.api_key)

    def update_hypotheses(
        self,
        category: str,
        tool_chain: list[dict],
        current_hypotheses: list[dict],
        user_message: str
    ) -> list[dict]:
        """
        Updates the list of hypotheses based on new tool results.
        Returns a list of hypotheses dicts.
        """
        logger.info(
            "HypothesisTrackerAgent: Updating hypotheses for category %s. Chain length: %d",
            category,
            len(tool_chain)
        )

        # 1. Run rule-based update first as base / fallback
        rule_based_hypotheses = self._update_rule_based(category, tool_chain)

        # 2. Try Gemini to see if it can produce richer/more customized hypotheses
        if self.api_key and tool_chain:
            try:
                prompt = self._build_tracker_prompt(category, tool_chain, current_hypotheses, user_message)
                model = genai.GenerativeModel("gemini-2.5-flash-lite")
                response = model.generate_content(
                    prompt,
                    generation_config={"response_mime_type": "application/json"},
                    request_options={"timeout": 10.0}
                )
                if response and response.text:
                    result = json.loads(response.text.strip())
                    hypotheses = result.get("hypotheses", [])
                    if isinstance(hypotheses, list) and len(hypotheses) > 0:
                        # Validate hypothesis structure
                        validated = []
                        for h in hypotheses:
                            if isinstance(h, dict) and "hypothesis" in h and "confidence" in h:
                                validated.append({
                                    "hypothesis": h.get("hypothesis"),
                                    "confidence": float(h.get("confidence", 0.5)),
                                    "supporting_evidence": h.get("supporting_evidence", []),
                                    "contradicting_evidence": h.get("contradicting_evidence", []),
                                    "status": h.get("status", "ACTIVE")
                                })
                        if validated:
                            logger.info("HypothesisTrackerAgent: Gemini successfully updated %d hypotheses", len(validated))
                            return validated
            except Exception as e:
                logger.warning("HypothesisTrackerAgent: Gemini call failed (%s). Using rule-based fallback.", e)

        logger.info("HypothesisTrackerAgent: Using %d rule-based hypotheses", len(rule_based_hypotheses))
        return rule_based_hypotheses

    def _update_rule_based(self, category: str, tool_chain: list[dict]) -> list[dict]:
        hypotheses = []
        cat_upper = category.upper().strip()

        # Gather tool details
        vpn_data = next((t.get("data", {}) for t in tool_chain if t.get("tool_name") == "vpn_tools"), None)
        net_data = next((t.get("data", {}) for t in tool_chain if t.get("tool_name") == "network_tools"), None)
        outlook_data = next((t.get("data", {}) for t in tool_chain if t.get("tool_name") == "outlook_tools"), None)
        sw_data = next((t.get("data", {}) for t in tool_chain if t.get("tool_name") == "software_tools"), None)

        if cat_upper == "VPN" or vpn_data is not None:
            if vpn_data:
                gateway = vpn_data.get("vpn_gateway", "UNKNOWN")
                user_access = vpn_data.get("user_access", "UNKNOWN")
                
                if gateway == "OFFLINE":
                    hypotheses.append({
                        "hypothesis": "VPN corporate gateway is offline or unreachable",
                        "confidence": 0.95,
                        "supporting_evidence": ["VPN gateway status: OFFLINE"],
                        "contradicting_evidence": [],
                        "status": "CONFIRMED"
                    })
                else:
                    hypotheses.append({
                        "hypothesis": "VPN corporate gateway is offline or unreachable",
                        "confidence": 0.05,
                        "supporting_evidence": [],
                        "contradicting_evidence": ["VPN gateway status: ONLINE"],
                        "status": "RULED_OUT"
                    })

                if user_access == "DISABLED":
                    hypotheses.append({
                        "hypothesis": "User VPN account is disabled in Active Directory",
                        "confidence": 0.95,
                        "supporting_evidence": ["User account status: DISABLED"],
                        "contradicting_evidence": [],
                        "status": "CONFIRMED"
                    })
                else:
                    hypotheses.append({
                        "hypothesis": "User VPN account is disabled in Active Directory",
                        "confidence": 0.05,
                        "supporting_evidence": [],
                        "contradicting_evidence": ["User account status: ACTIVE"],
                        "status": "RULED_OUT"
                    })

        if cat_upper == "OUTLOOK" or outlook_data is not None:
            if outlook_data:
                exchange = outlook_data.get("exchange_server", "UNKNOWN")
                mailbox = outlook_data.get("mailbox_status", "UNKNOWN")

                if exchange == "OFFLINE":
                    hypotheses.append({
                        "hypothesis": "Exchange connectivity server is offline",
                        "confidence": 0.95,
                        "supporting_evidence": ["Exchange Server: OFFLINE"],
                        "contradicting_evidence": [],
                        "status": "CONFIRMED"
                    })
                else:
                    hypotheses.append({
                        "hypothesis": "Exchange connectivity server is offline",
                        "confidence": 0.05,
                        "supporting_evidence": [],
                        "contradicting_evidence": ["Exchange Server: ONLINE"],
                        "status": "RULED_OUT"
                    })

                if mailbox != "ACTIVE" and mailbox != "UNKNOWN":
                    hypotheses.append({
                        "hypothesis": "User email mailbox is disabled or inactive",
                        "confidence": 0.90,
                        "supporting_evidence": [f"Mailbox status: {mailbox}"],
                        "contradicting_evidence": [],
                        "status": "CONFIRMED"
                    })

        if net_data:
            net_status = net_data.get("network_status", "UNKNOWN")
            wifi_status = net_data.get("wifi_status", "UNKNOWN")
            packet_loss = net_data.get("packet_loss", 0)

            if net_status == "OFFLINE" or wifi_status == "OFFLINE":
                hypotheses.append({
                    "hypothesis": "User has local network connection issues or WiFi outage",
                    "confidence": 0.95,
                    "supporting_evidence": ["Local network/WiFi is offline"],
                    "contradicting_evidence": [],
                    "status": "CONFIRMED"
                })
            elif packet_loss and int(packet_loss) > 0:
                hypotheses.append({
                    "hypothesis": "User's local network experiences packet loss or high latency",
                    "confidence": 0.85,
                    "supporting_evidence": [f"Packet loss: {packet_loss}%"],
                    "contradicting_evidence": [],
                    "status": "ACTIVE"
                })
            else:
                hypotheses.append({
                    "hypothesis": "User has local network connection issues or WiFi outage",
                    "confidence": 0.05,
                    "supporting_evidence": [],
                    "contradicting_evidence": ["Local network is online", "WiFi is online"],
                    "status": "RULED_OUT"
                })

        if cat_upper == "SOFTWARE_INSTALLATION" or sw_data is not None:
            if sw_data:
                approved = sw_data.get("approved", True)
                permissions = sw_data.get("permissions", "ALLOWED")

                if not approved:
                    hypotheses.append({
                        "hypothesis": "Requested software is not approved by Bridgestone IT policy",
                        "confidence": 0.95,
                        "supporting_evidence": ["Software approved: False"],
                        "contradicting_evidence": [],
                        "status": "CONFIRMED"
                    })
                if permissions == "DENIED":
                    hypotheses.append({
                        "hypothesis": "User lacks local administrator permissions to install software",
                        "confidence": 0.95,
                        "supporting_evidence": ["Permissions: DENIED"],
                        "contradicting_evidence": [],
                        "status": "CONFIRMED"
                    })

        # If no specific rules matched, add a generic hypothesis
        if not hypotheses:
            hypotheses.append({
                "hypothesis": f"General issue with category {category}",
                "confidence": 0.50,
                "supporting_evidence": ["User reported problem"],
                "contradicting_evidence": [],
                "status": "ACTIVE"
            })

        return hypotheses

    def _build_tracker_prompt(
        self,
        category: str,
        tool_chain: list[dict],
        current_hypotheses: list[dict],
        user_message: str
    ) -> str:
        return f"""You are an IT support Hypothesis Tracker Agent for Bridgestone.
Your job is to update the confidence and status of diagnostic hypotheses based on new evidence from the tool runs.

Schema for each hypothesis:
- "hypothesis": Short text statement of the possible cause.
- "confidence": Float from 0.0 to 1.0 (certainty).
- "supporting_evidence": List of facts from tool results supporting this hypothesis.
- "contradicting_evidence": List of facts contradicting this hypothesis.
- "status": One of: "ACTIVE", "CONFIRMED", "RULED_OUT".

=== Evidence ===
User Message: {user_message}
Category: {category}
Tool Execution Chain: {json.dumps(tool_chain, indent=2)}
Previous Hypotheses: {json.dumps(current_hypotheses, indent=2)}

Please re-evaluate and return an updated, comprehensive list of hypotheses in JSON format.

JSON:
{{
  "hypotheses": [
    {{
      "hypothesis": "User VPN account is disabled in Active Directory",
      "confidence": 0.95,
      "supporting_evidence": ["User account status: DISABLED"],
      "contradicting_evidence": [],
      "status": "CONFIRMED"
    }}
  ]
}}
"""
