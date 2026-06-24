import os
import json
import logging
import google.generativeai as genai
from dotenv import load_dotenv

logger = logging.getLogger("it-agent-backend")

class ConversationAgent:
    def __init__(self):
        load_dotenv()
        self.api_key = os.getenv("GEMINI_API_KEY")
        if self.api_key:
            genai.configure(api_key=self.api_key)

    def classify_message(self, message: str, history: list[dict], current_category: str = "GENERAL", current_status: str = "ACTIVE") -> dict:
        """
        Determines the intent and category of the user message.
        Intents: GREETING, IDENTITY, SMALL_TALK, IT_ISSUE, TICKET_REQUEST, APPROVAL_RESPONSE, FOLLOW_UP
        Categories: VPN, PASSWORD_RESET, OUTLOOK, SOFTWARE_INSTALLATION, PRINTER, SAP, NETWORK, GENERAL
        """
        logger.info("ConversationAgent: Classifying message: '%s'", message)
        
        # 1. First run rules fallback checks for high-priority deterministic intents (greetings, approvals, ticket requests)
        fallback_res = self._check_rule_based_fallback(message, history, current_category, current_status)
        
        # If we have a API key, try the Gemini LLM classification
        if self.api_key:
            try:
                prompt = self._build_prompt(message, history, current_category, current_status)
                model = genai.GenerativeModel("gemini-2.5-flash-lite")
                response = model.generate_content(
                    prompt,
                    generation_config={"response_mime_type": "application/json"},
                    request_options={"timeout": 10.0}
                )
                
                if response and response.text:
                    result = json.loads(response.text.strip())
                    intent = result.get("intent", "").strip().upper()
                    category = result.get("category", "").strip().upper()
                    
                    valid_intents = {"GREETING", "IDENTITY", "SMALL_TALK", "CAPABILITY", "THANKS", "GOODBYE", "IT_ISSUE", "TICKET_REQUEST", "APPROVAL_RESPONSE", "FOLLOW_UP"}
                    valid_categories = {"VPN", "PASSWORD_RESET", "OUTLOOK", "SOFTWARE_INSTALLATION", "PRINTER", "SAP", "NETWORK", "GENERAL"}
                    
                    if intent in valid_intents and category in valid_categories:
                        logger.info("ConversationAgent: Gemini classified successfully: Intent=%s, Category=%s", intent, category)
                        return {
                            "intent": intent,
                            "category": category,
                            "explanation": result.get("explanation", "")
                        }
            except Exception as e:
                logger.warning("ConversationAgent: Gemini classification failed: %s. Using rule-based fallback.", e)
                
        # 2. Fallback to rule-based classification
        logger.info("ConversationAgent: Using fallback classification: Intent=%s, Category=%s", fallback_res["intent"], fallback_res["category"])
        return fallback_res

    def _build_prompt(self, message: str, history: list[dict], current_category: str, current_status: str) -> str:
        prompt = (
            "You are an IT Support Conversation Gateway Agent.\n"
            "Analyze the current user message and the conversation history to classify the message's intent and target IT category.\n\n"
            "=== Intents ===\n"
            "- GREETING: User is saying hello, hi, good morning, etc.\n"
            "- IDENTITY: User is asking who you are, what you are, or what your name is (e.g. 'who are you', 'what are you').\n"
            "- CAPABILITY: User is asking what you can do, how you can help, or what services you support (e.g. 'what can you do', 'how can you help').\n"
            "- SMALL_TALK: User is making polite chitchat (e.g. 'how are you', 'how is your day').\n"
            "- THANKS: User is expressing gratitude or appreciation (e.g. 'thanks', 'thank you', 'awesome').\n"
            "- GOODBYE: User is saying goodbye (e.g. 'bye', 'goodbye', 'see you').\n"
            "- IT_ISSUE: User is describing a new technical issue or seeking troubleshooting help (e.g. 'VPN not connecting', 'Outlook is slow').\n"
            "- TICKET_REQUEST: User is explicitly requesting to create a support ticket, raise a ticket, or escalate to a human.\n"
            "- APPROVAL_RESPONSE: User is answering yes/no/approve/reject to a recommendation or authorization request (e.g. 'yes proceed', 'no cancel').\n"
            "- FOLLOW_UP: User is responding to a previous diagnostic question or following up on the active troubleshooting flow (e.g. 'still not working', 'it didn't help', 'it is resolved now', 'done').\n\n"
            "=== Categories ===\n"
            "VPN, PASSWORD_RESET, OUTLOOK, SOFTWARE_INSTALLATION, PRINTER, SAP, NETWORK, GENERAL\n\n"
            "=== Classification Rules ===\n"
            "1. If the message matches GREETING, IDENTITY, CAPABILITY, SMALL_TALK, THANKS, or GOODBYE, categorize as GENERAL.\n"
            f"2. If the current session has an active category ({current_category}) and the message is a FOLLOW_UP, APPROVAL_RESPONSE, or TICKET_REQUEST, retain the category as '{current_category}'.\n"
            f"3. If the current session status is '{current_status}' and is AWAITING_APPROVAL, a 'yes/no/cancel' message MUST be classified as APPROVAL_RESPONSE.\n"
            "4. If the message is a follow-up like 'still not working' or 'resolved' regarding a previously discussed issue, retain the category and classify as FOLLOW_UP.\n\n"
            "=== Input Context ===\n"
            f"Current Category Context: {current_category}\n"
            f"Current Session Status: {current_status}\n\n"
            "=== Conversation History ===\n"
        )
        
        for msg in history[-5:]:
            sender = "User" if msg["sender"] == "user" else "Agent"
            prompt += f"{sender}: {msg['text']}\n"
            
        prompt += f"\nLatest User Message: {message}\n\n"
        prompt += (
            "Return ONLY a valid JSON object matching this schema:\n"
            "{\n"
            '  "intent": "GREETING" | "IDENTITY" | "SMALL_TALK" | "CAPABILITY" | "THANKS" | "GOODBYE" | "IT_ISSUE" | "TICKET_REQUEST" | "APPROVAL_RESPONSE" | "FOLLOW_UP",\n'
            '  "category": "VPN" | "PASSWORD_RESET" | "OUTLOOK" | "SOFTWARE_INSTALLATION" | "PRINTER" | "SAP" | "NETWORK" | "GENERAL",\n'
            '  "explanation": "short rationale"\n'
            "}"
        )
        return prompt

    def _check_rule_based_fallback(self, message: str, history: list[dict], current_category: str, current_status: str) -> dict:
        text = message.lower().strip()
        
        # 1. Greetings
        greetings = {"hi", "hello", "hey", "heyyyy", "good morning", "good evening", "good afternoon", "greetings"}
        if any(text == g or text.startswith(g + " ") for g in greetings):
            return {"intent": "GREETING", "category": "GENERAL", "explanation": "Rule-based greeting match."}
            
        # 2. Identity
        identity_phrases = ["who are you", "what are you", "tell me about yourself", "your name", "what is your name", "who you are"]
        if any(phrase in text for phrase in identity_phrases):
            return {"intent": "IDENTITY", "category": "GENERAL", "explanation": "Rule-based identity question match."}
            
        # 3. Capability
        capability_phrases = ["what can you do", "how can you help", "what services do you support", "explain capabilities", "capabilities", "what services"]
        if any(phrase in text for phrase in capability_phrases):
            return {"intent": "CAPABILITY", "category": "GENERAL", "explanation": "Rule-based capability question match."}
            
        # 4. Small Talk
        small_talk = ["how are you", "what's up", "how is your day", "how's it going", "how are you doing", "nice day", "how is it going"]
        if any(phrase in text for phrase in small_talk):
            return {"intent": "SMALL_TALK", "category": "GENERAL", "explanation": "Rule-based small talk match."}

        # 5. Thanks
        thanks_words = ["thanks", "thank you", "great", "awesome"]
        if any(text == kw or text.startswith(kw + " ") for kw in thanks_words):
            return {"intent": "THANKS", "category": "GENERAL", "explanation": "Rule-based thanks match."}

        # 6. Goodbye
        goodbye_words = ["bye", "goodbye", "see you"]
        if any(text == kw or text.startswith(kw + " ") for kw in goodbye_words):
            return {"intent": "GOODBYE", "category": "GENERAL", "explanation": "Rule-based goodbye match."}

        # 7. Approval Response (check context first)
        approval_keywords = ["yes", "no", "approve", "reject", "cancel", "proceed", "go ahead", "ok", "okay", "do it", "abort", "stop"]
        if current_status == "AWAITING_APPROVAL" or any(kw == text for kw in approval_keywords) or any(text.startswith(kw + " ") for kw in approval_keywords):
            # Check if yes/no answers pending approval recommended action
            return {"intent": "APPROVAL_RESPONSE", "category": current_category if current_category else "GENERAL", "explanation": "Rule-based approval response match based on context."}

        # 8. Ticket Request
        ticket_keywords = [
            "create ticket", "create a ticket", "create support ticket", "create a support ticket",
            "raise ticket", "raise a ticket", "open incident", "open an incident", "escalate", "support ticket",
            "open a ticket", "open support ticket", "open a support ticket"
        ]
        if any(kw in text for kw in ticket_keywords):
            return {"intent": "TICKET_REQUEST", "category": current_category if current_category else "GENERAL", "explanation": "Rule-based ticket request match."}

        # 9. Follow-up
        follow_up_keywords = ["still not working", "failed", "didn't help", "didn't work", "did not help", "did not work", "unsuccessful", "still broken", "resolved", "solved", "fixed", "working now", "issue persists", "unresolved"]
        if any(kw in text for kw in follow_up_keywords) and current_category != "GENERAL":
            return {"intent": "FOLLOW_UP", "category": current_category, "explanation": "Rule-based follow-up match."}

        # 10. Category Switch / IT Issues detection
        detected_category = "GENERAL"
        if any(kw in text for kw in ["vpn not working", "remote access", "vpn", "anyconnect"]):
            detected_category = "VPN"
        elif any(kw in text for kw in ["wifi not connected", "wifi", "internet", "network", "lan", "connectivity", "gateway"]):
            detected_category = "NETWORK"
        elif any(kw in text for kw in ["outlook", "email", "mailbox", "exchange"]):
            detected_category = "OUTLOOK"
        elif any(kw in text for kw in ["software install", "application install", "install software", "install application", "cannot install", "unable to install", "installation", "setup", "chrome"]):
            detected_category = "SOFTWARE_INSTALLATION"
        elif "printer" in text:
            detected_category = "PRINTER"
        elif "sap" in text:
            detected_category = "SAP"
        elif "password" in text:
            detected_category = "PASSWORD_RESET"

        if detected_category != "GENERAL":
            return {"intent": "IT_ISSUE", "category": detected_category, "explanation": f"Rule-based IT Issue match: {detected_category}"}
            
        # Default follow-up if category context exists, else default general IT issue
        if current_category != "GENERAL":
            return {"intent": "FOLLOW_UP", "category": current_category, "explanation": "Defaulting to follow-up on existing category."}
            
        return {"intent": "IT_ISSUE", "category": "GENERAL", "explanation": "Defaulting to general IT issue classification."}

    def generate_conversational_response(self, message: str, history: list[dict], intent: str) -> str:
        """
        Generates a natural, friendly, ChatGPT-like response for conversational intents.
        """
        logger.info("ConversationAgent: Generating conversational response for intent: %s", intent)
        
        # Rule-based fallback response mapping
        fallback_responses = {
            "GREETING": "Hello! I am your Bridgestone IT support assistant. How can I help you today?",
            "IDENTITY": "I am your conversational Bridgestone IT Support Agent, designed to assist with account resets, VPN access, and troubleshooting.",
            "CAPABILITY": "I can troubleshoot VPN connection issues, diagnose network performance, reset passwords, check Outlook mailboxes, verify catalog software privileges, or escalate issues to specific support groups.",
            "SMALL_TALK": "I am doing well, thank you for asking! I'm ready to help you with any IT support questions or issues.",
            "THANKS": "You're very welcome! Let me know if there's anything else I can help you with.",
            "GOODBYE": "Goodbye! Have a great day, and feel free to reach out if you need IT help in the future."
        }
        
        fallback_text = fallback_responses.get(intent, "Hello! How can I assist you with your IT needs today?")
        
        if self.api_key:
            try:
                prompt = (
                    "You are Bridgestone's Conversational IT Support Agent. Speak naturally, professionally, and warmly, just like ChatGPT.\n"
                    f"The user message has the intent: {intent}.\n"
                    f"User message: '{message}'\n\n"
                    "=== Conversation History ===\n"
                )
                for msg in history[-5:]:
                    sender = "User" if msg["sender"] == "user" else "Agent"
                    prompt += f"{sender}: {msg['text']}\n"
                prompt += f"User: {message}\n"
                prompt += "\nWrite a friendly, natural, and helpful reply. Keep it under 2 sentences."
                
                model = genai.GenerativeModel("gemini-2.5-flash-lite")
                response = model.generate_content(
                    prompt,
                    request_options={"timeout": 10.0}
                )
                if response and response.text:
                    return response.text.strip()
            except Exception as e:
                logger.warning("ConversationAgent: Gemini generation failed: %s. Using rule-based fallback.", e)
                
        return fallback_text
