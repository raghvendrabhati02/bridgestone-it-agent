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
            "You are an experienced Bridgestone IT Service Desk Engineer.\n"
            "Speak naturally, professionally, and warmly — like a knowledgeable digital colleague, not a chatbot template.\n\n"

            "=== Response Style Rules ===\n"
            "1. Empathy first: Acknowledge the user's issue and pain point warmly before discussing diagnostics or next steps.\n"
            "2. Keep it conversational: NEVER say robotic phrases like 'I see you are having an issue with X.', 'Troubleshooting was unsuccessful', or dump raw diagnostic keys.\n"
            "3. Reference history: Scan the conversation history. If the user already answered a question (e.g., they are on home Wi-Fi or getting Error 809), acknowledge and refer to it naturally (e.g., 'Since you mentioned you are on home Wi-Fi...'). Do NOT ask it again.\n"
            "4. Explain the check: Tell the user what system or tool you are currently checking (e.g., 'I'm querying Active Directory to check for any lockouts...').\n"
            "5. Present options: When asking for details like error codes, offer clear multiple-choice options to make it easy for the user.\n"
            "6. Summarize first: Always provide a clear, user-friendly summary of observations and hypotheses before recommending a fix, asking for approval, or initiating a support ticket.\n"
            "7. Write 2-4 sentences maximum. Be direct, helpful, and colleague-like.\n"
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

        # Scan user message and history for parameters to avoid repeating questions
        msg_lower = user_message.lower()
        hist_text = " ".join(m.get("text", "").lower() for m in history)
        all_text = msg_lower + " " + hist_text

        # VPN parsing
        vpn_error = None
        if any(kw in all_text for kw in ["809", "868", "timeout", "time out"]):
            vpn_error = "Connection Timeout (Error 809 / 868)"
        elif any(kw in all_text for kw in ["auth", "credential", "denied", "lock", "disabled"]):
            vpn_error = "Authentication Denied"
        elif any(kw in all_text for kw in ["client", "anyconnect", "launch", "open"]):
            vpn_error = "Client Launch Failure"

        vpn_conn = None
        if any(kw in all_text for kw in ["wifi", "wi-fi", "wireless", "hotspot", "home"]):
            vpn_conn = "home Wi-Fi"
        elif any(kw in all_text for kw in ["ethernet", "wired", "cable", "lan", "office"]):
            vpn_conn = "wired ethernet"

        # Outlook parsing
        outlook_mode = None
        if any(kw in all_text for kw in ["desktop", "app", "pc", "mac"]):
            outlook_mode = "desktop app"
        elif any(kw in all_text for kw in ["web", "browser", "owa", "webmail"]):
            outlook_mode = "web app (OWA)"
        elif any(kw in all_text for kw in ["phone", "mobile", "ios", "android"]):
            outlook_mode = "mobile app"

        outlook_symptom = None
        if any(kw in all_text for kw in ["sync", "send", "receive", "mail", "refresh"]):
            outlook_symptom = "refusing to sync or send/receive emails"
        elif any(kw in all_text for kw in ["open", "launch", "start", "crash", "freeze"]):
            outlook_symptom = "failing to open or launch completely"

        # Network parsing
        net_scope = None
        if any(kw in all_text for kw in ["down", "all sites", "offline", "disconnect", "everything"]):
            net_scope = "completely offline"
        elif any(kw in all_text for kw in ["google", "website", "only one", "specific"]):
            net_scope = "limited to a specific site"

        net_symptom = None
        if any(kw in all_text for kw in ["slow", "lag", "ping", "latency"]):
            net_symptom = "slow connectivity and lag"
        elif any(kw in all_text for kw in ["packet", "loss", "drop"]):
            net_symptom = "intermittent packet loss"

        # Software parsing
        sw_name = None
        for word in ["chrome", "firefox", "zoom", "teams", "sap", "visio", "office"]:
            if word in all_text:
                sw_name = word.title()
                break
        
        sw_error = None
        if any(kw in all_text for kw in ["admin", "privilege", "permission", "password", "rights"]):
            sw_error = "local administrative rights warning"

        # 1. Approval request — use reflection hypothesis to explain WHY
        if plan_action == "REQUEST_APPROVAL" or approval_needed:
            hyp_reason = ""
            if hypotheses:
                hyp_reason = f" Based on the diagnostics, {hypotheses[0].lower().rstrip('.')}."
            if recommended_action == "VPN_ACCESS_RESTORATION":
                obs_summary = "I've checked the VPN connection and gateway. The gateway is online, but your account access permissions are set to disabled."
                return (
                    f"{obs_summary}{hyp_reason} I can submit an access restoration request to re-enable your account. "
                    f"Would you like me to proceed?"
                )
            if recommended_action == "SOFTWARE_INSTALLATION":
                target_software = sw_name or "requested software"
                obs_summary = f"I've verified the software catalog and your local device privileges for {target_software}. It is approved, but your account lacks administrative installation permissions."
                return (
                    f"{obs_summary}{hyp_reason} I can submit an installation request on your behalf through the IT portal. "
                    f"Shall I go ahead?"
                )
            if recommended_action == "OUTLOOK_RECONFIGURATION":
                obs_summary = "I've completed the Outlook diagnostics. The Exchange server is online, but your local mail profile appears out of sync."
                return (
                    f"{obs_summary}{hyp_reason} I recommend reconfiguring your local Outlook mail profile to restore proper sync. "
                    f"Would you like me to initiate this?"
                )
            if recommended_action == "NETWORK_RESET":
                obs_summary = "I've analyzed your network interface. The connection shows latency or packet loss."
                return (
                    f"{obs_summary}{hyp_reason} I recommend resetting your local network adapter configuration to clear the routing cache. "
                    f"Shall I run the network reset?"
                )
            obs_desc = f" {observations[0].lower()}" if observations else ""
            return (
                f"I've checked the system diagnostics and found that{obs_desc}.{hyp_reason} "
                f"I recommend proceeding with {recommended_action.replace('_', ' ').lower() if recommended_action else 'a corrective action'}. "
                f"Shall I initiate the request?"
            )

        # 2. Escalation — explain what was found before escalating
        if plan_action == "CREATE_TICKET" or escalation_needed:
            obs_summary = f" Diagnostics check showed: {observations[0].lower().rstrip('.')}." if observations else ""
            hyp_summary = f" This is likely caused by {hypotheses[0].lower().rstrip('.')}." if hypotheses else ""
            return (
                f"I've run through the initial troubleshooting steps, but it looks like we need support from our L2 IT engineering team to resolve this.{obs_summary}{hyp_summary} "
                f"I'm going to create a ServiceNow support ticket and assign it to the correct group so they can follow up with you directly."
            )

        # 3. Execute Action (post-approval)
        if plan_action == "EXECUTE_ACTION":
            return (
                "Understood. I have successfully submitted the request on your behalf. "
                "The ServiceNow workflow is now running, and you'll receive updates as the team processes it."
            )

        # 4. Cancel Workflow
        if plan_action == "CANCEL_WORKFLOW":
            return "No problem — I've cancelled the request. Let me know if you'd like to try a different approach or if you need help with anything else."

        # 5. Resolve Issue
        if plan_action == "RESOLVE_ISSUE":
            return "That's fantastic to hear! I'm glad we were able to resolve the issue. Have a great rest of your day, and feel free to reach out if any other IT needs come up."

        # 6. Diagnostic findings + follow-up (the most important case)
        if observations or findings:
            explanation = ""
            if observations:
                explanation = f"I ran the diagnostic checks and found that "
                if len(observations) >= 2:
                    explanation += f"{observations[0].lower().rstrip('.')} and {observations[1].lower()}"
                else:
                    explanation += f"{observations[0].lower()}"
            else:
                explanation = findings

            hyp_explanation = ""
            if hypotheses:
                hyp_explanation = f" Since {hypotheses[0].lower().rstrip('.')},"

            inv_questions = self._build_investigation_questions(hypotheses, category, plan_action)
            question_text = ""
            if inv_questions:
                question_text = f" {inv_questions[0]}"
            elif findings:
                question_text = " Would you like me to submit an escalation ticket, or shall we try another troubleshooting step?"

            return f"{explanation}.{hyp_explanation}{question_text}".strip()

        # 7. No diagnostic data — ask targeted category-specific questions
        cat_key = category.upper().strip()

        if cat_key == "VPN":
            ack = "I'm sorry you're running into VPN connection issues. Let's get that resolved."
            checking = "I'm going to run a quick check on the corporate VPN gateway status and check your user account permissions."
            
            if vpn_error and vpn_conn:
                return f"{ack} Since you mentioned you are seeing a {vpn_error} while connected via {vpn_conn}, {checking} Let's verify the gateway access."
            elif vpn_error:
                return f"{ack} Since you are getting a {vpn_error}, {checking} While I verify the gateway access, are you connected via Wi-Fi or wired ethernet?"
            elif vpn_conn:
                return f"{ack} Since you are connected to {vpn_conn}, {checking} While I do that, are you getting a specific error message, like a Connection Timeout (Error 809 / 868) or Authentication Denied?"
            else:
                return (
                    f"{ack} {checking} In the meantime, could you tell me: are you seeing a specific error or symptom?\n"
                    "  [A] Connection Timeout (Error 809 / 868)\n"
                    "  [B] Authentication Denied / locked account\n"
                    "  [C] Cisco AnyConnect client fails to open\n"
                    "  [D] Other / Not sure"
                )

        elif cat_key == "OUTLOOK":
            ack = "I understand Outlook is giving you trouble. Let's get your email sync working."
            checking = "I will query your mailbox sync status and check our Exchange server connectivity."
            
            if outlook_symptom and outlook_mode:
                return f"{ack} Since you are experiencing Outlook {outlook_symptom} on your {outlook_mode}, {checking} Let's inspect the server logs."
            elif outlook_symptom:
                return f"{ack} Since Outlook is {outlook_symptom}, {checking} Are you using the desktop app, web version (OWA), or mobile app?"
            elif outlook_mode:
                return f"{ack} Since you are accessing email via the {outlook_mode}, {checking} Is Outlook failing to open entirely, or is it open but refusing to send/receive?"
            else:
                return (
                    f"{ack} {checking} While I inspect the connection, is Outlook failing to open entirely, or is it open but refusing to send/receive emails?"
                )

        elif cat_key == "SOFTWARE_INSTALLATION":
            target = sw_name or "the application"
            ack = f"Getting {target} installed should be quick and easy."
            checking = f"I'm going to search our approved software catalog and check if you have local admin permissions."
            
            if sw_error == "admin":
                return f"{ack} Since you are seeing an administrator privilege warning, {checking} Let me check if your machine has self-service privileges enabled."
            elif sw_name:
                return f"{ack} {checking} Let's verify if the installation is allowed on your device."
            else:
                return f"I can help with software installations. {checking} What is the exact name of the software you want to install?"

        elif cat_key == "NETWORK":
            ack = "I'm sorry your network connection is running slow or dropping; that is always a hassle."
            checking = "I will check your network interface status and test for packet loss."
            
            if net_symptom and net_scope == "down":
                return f"{ack} Since your entire connection is {net_scope} with {net_symptom}, {checking} Let's check the gateway response."
            elif net_symptom:
                return f"{ack} Since you are experiencing {net_symptom}, {checking} Are you able to access any external websites (like google.com) normally?"
            elif net_scope:
                return f"{ack} Since your connection is {net_scope}, {checking} Let's verify if we detect network packet loss."
            else:
                return f"{ack} {checking} In the meantime, are other websites loading normally (like google.com), or is all internet access down?"

        elif cat_key == "PASSWORD_RESET":
            ack = "I can definitely help reset your password or unlock your account."
            checking = "I am querying our Active Directory domain controllers to inspect your account lockout status."
            return f"{ack} {checking} Is this password reset for your primary Windows laptop login, or for a specific application like SAP?"

        elif cat_key == "SAP":
            ack = "I understand SAP is throwing errors. Let's look into it."
            checking = "I'm checking the SAP Basis server health and database connectivity."
            return f"{ack} {checking} Could you let me know: what is the exact error code or transaction code (T-code) you are attempting to run?"

        elif cat_key == "PRINTER":
            ack = "I'm sorry you're dealing with printer issues."
            checking = "I will query the print spooler service and check the active printer queue status."
            return f"{ack} {checking} Is the printer showing as 'Offline' in your settings, or are your print jobs getting stuck in the queue?"

        elif cat_key == "HARDWARE":
            ack = "I'm sorry you're experiencing hardware trouble with your device."
            checking = "I'll query our device asset inventory database to check your device type and warranty."
            return f"{ack} {checking} Could you let me know: is there physical damage, or is a component like the display screen or keyboard failing?"

        # Default GENERAL
        return (
            "I understand you're experiencing an IT issue. Let's get that diagnosed and fixed. "
            "I'm going to run a general system health check on your workstation. "
            "Could you share a bit more detail about what error messages or symptoms you are seeing?"
        )
