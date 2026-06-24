import os
import logging
import google.generativeai as genai

logger = logging.getLogger("it-agent-backend")


class ResponseAgent:
    """
    Generates final conversational responses using reflection output
    (observations, hypotheses, confidence, findings) as the primary intelligence source.

    The reflection dict is expected to contain:
        observations    list[str]   — facts from tool diagnostics
        hypotheses      list[str]   — probable root causes
        confidence      float       — 0.0-1.0 certainty score
        findings        str         — summary paragraph
        approval_needed bool
        escalation_needed bool
        recommended_action str
        rationale       str
    """

    def __init__(self):
        self.api_key = os.getenv("GEMINI_API_KEY")
        if self.api_key:
            genai.configure(api_key=self.api_key)

    # ──────────────────────────────────────────────────────────
    # Public interface
    # ──────────────────────────────────────────────────────────

    def generate_response(
        self,
        user_message: str,
        history: list[dict],
        plan: list[str],
        reasoning: dict,
        category: str,
        knowledge_context: str = "",
    ) -> str:
        """
        Generates a natural language response.

        `reasoning` is expected to be the full reflection dict
        (from ReasoningAgent.reflect / reflection_node).
        Falls back gracefully if reflection fields are missing.
        """
        logger.info(
            "ResponseAgent: Generating response. Plan=%s, Category=%s, "
            "HasObservations=%s, HasHypotheses=%s, Confidence=%.2f",
            plan,
            category,
            bool(reasoning.get("observations")),
            bool(reasoning.get("hypotheses")),
            reasoning.get("confidence", 0.0) if reasoning else 0.0,
        )

        # Build a deterministic fallback first
        fallback = self._generate_rule_based_response(
            user_message, history, plan, reasoning, category
        )

        if self.api_key:
            try:
                prompt = self._build_prompt(
                    user_message, history, plan, reasoning, category, knowledge_context
                )
                model = genai.GenerativeModel("gemini-2.5-flash-lite")
                response = model.generate_content(
                    prompt,
                    request_options={"timeout": 15.0},
                )
                if response and response.text:
                    text = response.text.strip()
                    logger.info(
                        "ResponseAgent: Gemini response generated: %s", text[:120]
                    )
                    return text
            except Exception as e:
                logger.warning(
                    "ResponseAgent: Gemini generation failed (%s). Using rule-based fallback.", e
                )

        logger.info("ResponseAgent: Using rule-based fallback response.")
        return fallback

    # ──────────────────────────────────────────────────────────
    # Prompt builder — reflection-first
    # ──────────────────────────────────────────────────────────

    def _build_prompt(
        self,
        user_message: str,
        history: list[dict],
        plan: list[str],
        reasoning: dict,
        category: str,
        knowledge_context: str,
    ) -> str:
        plan_action = plan[0] if plan else "ASK_QUESTION"

        # Extract structured reflection fields
        observations = reasoning.get("observations") or []
        hypotheses   = reasoning.get("hypotheses") or []
        confidence   = reasoning.get("confidence", 0.0)
        findings     = reasoning.get("findings", "")
        approval_needed   = reasoning.get("approval_needed", False)
        escalation_needed = reasoning.get("escalation_needed", False)
        recommended_action = reasoning.get("recommended_action", "")

        # Format observations and hypotheses as bullet lists
        obs_text = "\n".join(f"  - {o}" for o in observations) if observations else "  (none)"
        hyp_text = "\n".join(f"  - {h}" for h in hypotheses) if hypotheses else "  (none)"

        # Build investigation questions if hypotheses exist
        investigation_questions = self._build_investigation_questions(
            hypotheses, category, plan_action
        )
        inv_q_text = "\n".join(f"  {i+1}. {q}" for i, q in enumerate(investigation_questions)) if investigation_questions else ""

        prompt = (
            "You are Bridgestone's Conversational IT Support Agent.\n"
            "Speak naturally, professionally, and warmly — like a knowledgeable colleague, not a chatbot template.\n\n"

            "=== Response Style Rules ===\n"
            "1. NEVER say 'I see you are having an issue with X.' or 'Troubleshooting was unsuccessful.'\n"
            "2. NEVER dump raw diagnostic keys (e.g. vpn_gateway=ONLINE). Convert them to human language.\n"
            "3. Write 2-4 sentences maximum. Be conversational and direct.\n"
            "4. Use the Observations and Hypotheses to explain WHAT was found and WHY it likely happened.\n"
            "5. If a hypothesis exists, acknowledge it naturally: 'Since the issue started after your password changed...'\n"
            "6. If approval_needed is true, explain the recommended action and ask for confirmation warmly.\n"
            "7. If escalation_needed is true, explain you are escalating and why.\n"
            f"8. Planned next action: {plan_action}\n\n"

            "=== Structured Reflection Intelligence ===\n"
            "What the diagnostics found (Observations):\n"
            f"{obs_text}\n\n"
            "Most likely root causes (Hypotheses):\n"
            f"{hyp_text}\n\n"
            f"Diagnostic confidence: {confidence:.0%}\n"
            f"Approval needed: {approval_needed}\n"
            f"Escalation needed: {escalation_needed}\n"
            f"Recommended action: {recommended_action or '(none)'}\n"
            f"Summary: {findings}\n\n"
        )

        if inv_q_text:
            prompt += (
                "=== Suggested Investigation Questions (use naturally if asking follow-up) ===\n"
                f"{inv_q_text}\n\n"
            )

        if knowledge_context:
            prompt += (
                "=== Knowledge Base Context ===\n"
                f"{knowledge_context}\n\n"
            )

        prompt += "=== Conversation History ===\n"
        for msg in history[-5:]:
            sender = "User" if msg.get("sender") == "user" else "Agent"
            prompt += f"{sender}: {msg.get('text', '')}\n"

        prompt += f"User: {user_message}\n\nResponse:"
        return prompt

    # ──────────────────────────────────────────────────────────
    # Investigation question generator
    # ──────────────────────────────────────────────────────────

    def _build_investigation_questions(
        self,
        hypotheses: list[str],
        category: str,
        plan_action: str,
    ) -> list[str]:
        """
        Generates contextual follow-up questions based on reflection hypotheses.
        Only generates questions when plan_action == ASK_QUESTION.
        """
        if plan_action != "ASK_QUESTION" or not hypotheses:
            return []

        questions = []

        # VPN hypothesis keywords
        hyp_text = " ".join(hypotheses).lower()
        if "password" in hyp_text or "credential" in hyp_text or "token" in hyp_text:
            questions.extend([
                "Did the VPN issue begin immediately after your password change?",
                "Are you working remotely or from the office network?",
                "Do you see a specific authentication or certificate error when connecting?",
            ])
        elif "gateway" in hyp_text or "outage" in hyp_text or "server" in hyp_text:
            questions.extend([
                "Are other colleagues also experiencing this issue?",
                "Can you reach any internal resources (intranet, shared drives)?",
                "What error message are you seeing — connection timeout or authentication failure?",
            ])
        elif "mailbox" in hyp_text or "exchange" in hyp_text or "mail" in hyp_text:
            questions.extend([
                "Is Outlook showing a specific error — 'Cannot connect to server' or 'Mailbox not found'?",
                "Are you using Outlook on desktop, web browser, or mobile?",
                "Can you check if you can log in to Outlook Web Access (owa.bridgestone.com)?",
            ])
        elif "software" in hyp_text or "install" in hyp_text or "admin" in hyp_text:
            questions.extend([
                "Are you seeing a 'Permission Denied' or 'Administrator required' error?",
                "Is this software for a specific project or team?",
                "Do you have approval from your manager for this installation?",
            ])
        elif "wifi" in hyp_text or "network" in hyp_text or "connectivity" in hyp_text:
            questions.extend([
                "Are you connected to the Bridgestone corporate Wi-Fi or a personal hotspot?",
                "Can you open any website in your browser right now?",
                "Have you tried restarting your network adapter or router?",
            ])
        else:
            # Generic follow-up based on category
            category_questions = {
                "VPN": [
                    "What error message do you see when the VPN fails to connect?",
                    "Are you on the corporate network or working remotely?",
                ],
                "OUTLOOK": [
                    "Is the issue with sending, receiving, or both?",
                    "Does Outlook open but fail to sync, or does it crash on launch?",
                ],
                "SOFTWARE_INSTALLATION": [
                    "What error message appears when the installation fails?",
                    "Is this software listed in the company's approved software catalog?",
                ],
                "NETWORK": [
                    "Can you reach external websites, or is only internal access broken?",
                    "Have you restarted your device and router recently?",
                ],
                "SAP": [
                    "What error code is SAP displaying when you try to log in?",
                    "Has your SAP user role recently changed?",
                ],
                "PRINTER": [
                    "Is the printer showing as online or offline in your system tray?",
                    "Have you tried clearing the print queue?",
                ],
            }
            questions = category_questions.get(category, [
                "Can you describe any error message you are seeing?",
                "When did this issue first occur?",
            ])

        return questions[:3]  # Limit to 3 questions maximum

    # ──────────────────────────────────────────────────────────
    # Rule-based fallback — reflection-aware
    # ──────────────────────────────────────────────────────────

    def _generate_rule_based_response(
        self,
        user_message: str,
        history: list[dict],
        plan: list[str],
        reasoning: dict,
        category: str,
    ) -> str:
        plan_action = plan[0] if plan else "ASK_QUESTION"

        # Extract reflection fields (graceful fallback to old "findings" key)
        observations     = reasoning.get("observations") or []
        hypotheses       = reasoning.get("hypotheses") or []
        confidence       = reasoning.get("confidence", 0.0)
        findings         = reasoning.get("findings", "")
        approval_needed  = reasoning.get("approval_needed", False)
        escalation_needed = reasoning.get("escalation_needed", False)
        recommended_action = reasoning.get("recommended_action", "")

        # 1. Approval request — use reflection hypothesis to explain WHY
        if plan_action == "REQUEST_APPROVAL" or approval_needed:
            hyp_reason = ""
            if hypotheses:
                hyp_reason = f" Based on the diagnostics, {hypotheses[0].lower().rstrip('.')}."
            if recommended_action == "VPN_ACCESS_RESTORATION":
                obs_summary = ""
                if observations:
                    # Find the observation about disabled access
                    for obs in observations:
                        if "disabled" in obs.lower() or "locked" in obs.lower():
                            obs_summary = f" I found that {obs.lower()}"
                            break
                return (
                    f"I checked the VPN infrastructure and your connection settings.{obs_summary}"
                    f"{hyp_reason} I can submit an access restoration request to re-enable your account. "
                    f"Would you like me to proceed?"
                )
            if recommended_action == "SOFTWARE_INSTALLATION":
                return (
                    f"I've verified the software details.{hyp_reason} "
                    f"I can submit an installation request on your behalf through the IT portal. "
                    f"Shall I go ahead?"
                )
            if recommended_action == "OUTLOOK_RECONFIGURATION":
                return (
                    f"I've completed the Outlook diagnostics.{hyp_reason} "
                    f"I recommend reconfiguring your mail profile to restore connectivity. "
                    f"Would you like me to initiate this?"
                )
            return (
                f"Based on the diagnostic results, I recommend proceeding with {recommended_action or 'a corrective action'}. "
                f"Shall I initiate the request?"
            )

        # 2. Escalation — explain what was found before escalating
        if plan_action == "CREATE_TICKET" or escalation_needed:
            obs_summary = f" {observations[0]}" if observations else ""
            return (
                f"The diagnostic check revealed an issue that requires IT team intervention.{obs_summary} "
                f"I'll escalate this by creating a support ticket, and the appropriate team will follow up with you shortly."
            )

        # 3. Execute Action (post-approval)
        if plan_action == "EXECUTE_ACTION":
            return (
                "Your request has been submitted successfully. "
                "The IT team will process it and you should receive an update shortly."
            )

        # 4. Cancel Workflow
        if plan_action == "CANCEL_WORKFLOW":
            return "Understood — I've cancelled the request. Let me know if you'd like to explore a different solution or if you need help with anything else."

        # 5. Resolve Issue
        if plan_action == "RESOLVE_ISSUE":
            return "That's great to hear! I'm glad we were able to resolve the issue. Feel free to reach out if anything else comes up."

        # 6. Diagnostic findings + follow-up (the most important case)
        if observations or findings:
            # Build natural response from observations
            obs_text = ""
            if observations:
                # Use first 2 observations naturally
                if len(observations) >= 2:
                    obs_text = f"{observations[0]} {observations[1]}"
                else:
                    obs_text = observations[0]

            # Add hypothesis-driven explanation
            hyp_text = ""
            if hypotheses:
                hyp_text = f" Since {hypotheses[0].lower().rstrip('.')}, "

            # Add investigation question
            inv_questions = self._build_investigation_questions(hypotheses, category, plan_action)
            question_text = ""
            if inv_questions:
                question_text = f" {inv_questions[0]}"
            elif findings:
                question_text = " Would you like me to escalate this, or shall we try a different troubleshooting step?"

            return f"I ran a diagnostic check and found the following: {obs_text}.{hyp_text}{question_text}".strip()

        # 7. No diagnostic data — ask targeted category-specific questions
        category_prompts = {
            "VPN": (
                "Let me run a VPN diagnostic for you. "
                "While I check the gateway and your access permissions, could you tell me — "
                "are you seeing a specific error message when connecting?"
            ),
            "OUTLOOK": (
                "I'll check your mailbox and Exchange server status. "
                "In the meantime — is Outlook failing to open entirely, or is it open but not syncing?"
            ),
            "SOFTWARE_INSTALLATION": (
                "I'll verify this software against our approved catalog and check your device permissions. "
                "Which software are you trying to install?"
            ),
            "NETWORK": (
                "I'll run a connectivity diagnostic. "
                "Are other applications also failing, or is this specific to one app or website?"
            ),
            "SAP": (
                "Let me check the SAP system status for you. "
                "What error message or code are you seeing when logging in?"
            ),
            "PRINTER": (
                "I'll check the printer status. "
                "Is the printer showing as offline in Windows, or does the print job silently disappear?"
            ),
            "PASSWORD_RESET": (
                "I can help with that. "
                "Are you locked out of your Windows account, or is this for a specific application?"
            ),
        }
        return category_prompts.get(
            category,
            "Could you share a bit more about what you're experiencing? "
            "I'd like to run the right diagnostic checks for you.",
        )
