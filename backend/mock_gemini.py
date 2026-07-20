import sys
import json
from unittest.mock import MagicMock

class MockResponse:
    def __init__(self, text):
        self.text = text

class MockChatSession:
    def __init__(self, model, history=None):
        self.model = model
        self.history = history or []

    def send_message(self, message, request_options=None):
        self.history.append({"role": "user", "parts": [message]})
        resp = self.model.generate_content(message, request_options=request_options)
        self.history.append({"role": "model", "parts": [resp.text]})
        return resp

class MockGenerativeModel:
    def __init__(self, model_name, *args, **kwargs):
        self.model_name = model_name

    def start_chat(self, history=None):
        return MockChatSession(self, history)

    def generate_content(self, prompt, **kwargs):
        prompt_str = str(prompt)
        prompt_lower = prompt_str.lower()
        
        # Extract the latest user message context to avoid history matching pollution
        latest_msg = ""
        if "Latest User Message:" in prompt_str:
            latest_msg = prompt_str.split("Latest User Message:")[-1].split("\n")[0].strip().lower()
        elif "User Query:" in prompt_str:
            latest_msg = prompt_str.split("User Query:")[-1].split("\n")[0].strip().lower()
        elif "User Message:" in prompt_str:
            latest_msg = prompt_str.split("User Message:")[-1].split("\n")[0].strip().lower()
        elif "User:" in prompt_str:
            latest_msg = prompt_str.split("User:")[-1].split("\n")[0].strip().lower()
        else:
            latest_msg = prompt_lower
        
        # Default mock response text
        text = "Hello! I am the Bridgestone IT support assistant. Let me assist you with this issue."
        
        # 1. Intent Detection from intent_service.py
        if "classify it into exactly one of these categories" in prompt_str:
            category = "GENERAL"
            if "vpn" in prompt_lower:
                category = "VPN"
            elif "password" in prompt_lower or "unlock" in prompt_lower:
                category = "PASSWORD_RESET"
            elif "outlook" in prompt_lower or "email" in prompt_lower:
                category = "OUTLOOK"
            elif "visio" in prompt_lower or "software" in prompt_lower or "install" in prompt_lower:
                category = "SOFTWARE_INSTALLATION"
            elif "printer" in prompt_lower:
                category = "PRINTER"
            elif "sap" in prompt_lower:
                category = "SAP"
            elif "network" in prompt_lower or "switch" in prompt_lower:
                category = "NETWORK"
            elif "teams" in prompt_lower:
                category = "TEAMS"
            elif "onedrive" in prompt_lower:
                category = "ONEDRIVE"
            elif "wifi" in prompt_lower or "wi-fi" in prompt_lower or "wireless" in prompt_lower:
                category = "WIFI"
            elif "browser" in prompt_lower or "chrome" in prompt_lower or "edge" in prompt_lower:
                category = "BROWSER"
            elif "adobe" in prompt_lower or "pdf" in prompt_lower:
                category = "ADOBE"
            elif "citrix" in prompt_lower:
                category = "CITRIX"
            elif "bitlocker" in prompt_lower:
                category = "BITLOCKER"
            elif "driver" in prompt_lower:
                category = "DRIVERS"
            elif "performance" in prompt_lower or "slow" in prompt_lower:
                category = "PERFORMANCE"
            elif "login" in prompt_lower or "sign in" in prompt_lower:
                category = "LOGIN"
            elif "windows" in prompt_lower:
                category = "WINDOWS"
            elif "office" in prompt_lower:
                category = "OFFICE"
            elif "hardware" in prompt_lower or "keyboard" in prompt_lower or "monitor" in prompt_lower or "laptop" in prompt_lower:
                category = "HARDWARE"
            text = category

        # 2. Context Sufficiency Check from diagnostic_interview_node.py
        elif 'Return a JSON object with a single boolean key "sufficient"' in prompt_str or '"sufficient": true' in prompt_str:
            sufficient = True
            # Simulate insufficiency if the user message is too simple
            if "vpn access is disabled" in prompt_lower or "vpn is timing out" in prompt_lower:
                sufficient = True
            elif "vpn" in prompt_lower and len(prompt_lower) < 15:
                sufficient = False
            text = json.dumps({"sufficient": sufficient})

        # 3. Intent / Router Agent (Conversation Gateway)
        elif "Conversation Gateway Agent" in prompt_str:
            category = "GENERAL"
            intent = "IT_ISSUE"
            explanation = "IT query classified."
            
            if "vpn" in prompt_lower:
                category = "VPN"
                if "yes" in latest_msg or "approve" in latest_msg or "proceed" in latest_msg:
                    intent = "APPROVAL_RESPONSE"
                else:
                    intent = "IT_ISSUE"
            elif "password" in prompt_lower or "unlock" in prompt_lower:
                category = "PASSWORD_RESET"
                intent = "IT_ISSUE"
            elif "outlook" in prompt_lower or "email" in prompt_lower:
                category = "OUTLOOK"
                intent = "IT_ISSUE"
            elif "visio" in prompt_lower or "software" in prompt_lower or "install" in prompt_lower:
                category = "SOFTWARE_INSTALLATION"
                intent = "SERVICE_REQUEST"
            elif "printer" in prompt_lower:
                category = "PRINTER"
                intent = "IT_ISSUE"
            elif "sap" in prompt_lower:
                category = "SAP"
                intent = "IT_ISSUE"
            elif "network" in prompt_lower or "switch" in prompt_lower:
                category = "NETWORK"
                intent = "IT_ISSUE"
            elif "hardware" in prompt_lower or "keyboard" in prompt_lower or "monitor" in prompt_lower or "laptop" in prompt_lower:
                category = "HARDWARE"
                intent = "IT_ISSUE"
                
            text = json.dumps({
                "intent": intent,
                "category": category,
                "explanation": explanation
            })
            
        # 4. Hypothesis Tracker Agent
        elif "Hypothesis Tracker Agent" in prompt_str:
            text = json.dumps({
                "observations": ["System reported offline connectivity link."],
                "hypotheses": ["Hardware port unplugged", "Local switch offline"]
            })
            
        # 5. Multi-Step Planner Agent
        elif "Multi-Step Planner Agent" in prompt_str:
            decision = "CREATE_TICKET"
            action = None
            reason = "Creating support ticket for technician assignment."
            
            if "visio" in prompt_lower or "software" in prompt_lower:
                decision = "REQUEST_APPROVAL"
                action = "install_software Visio"
                reason = "Software installation requires approval."
            elif "vpn" in prompt_lower:
                if "yes" in latest_msg or "approve" in latest_msg or "proceed" in latest_msg:
                    decision = "EXECUTE_ACTION"
                    action = "VPN_ACCESS_RESTORATION"
                    reason = "Action approved."
                else:
                    decision = "REQUEST_APPROVAL"
                    action = "VPN_ACCESS_RESTORATION"
                    reason = "Privileged action requires approval."
            elif "password" in prompt_lower or "unlock" in prompt_lower:
                decision = "EXECUTE_ACTION"
                action = "unlock_ad_user"
                reason = "AD account unlock procedure initiated."
                
            ret = {"decision": decision, "reason": reason}
            if action:
                ret["action"] = action
            text = json.dumps(ret)
            
        # 6. Reflection Agent
        elif "Reflection Agent" in prompt_str:
            confidence = 0.9
            approval_needed = False
            recommended_action = None
            findings = "Standard investigation complete."
            
            if "vpn" in prompt_lower:
                recommended_action = "VPN_ACCESS_RESTORATION"
                if "yes" in latest_msg or "approve" in latest_msg or "proceed" in latest_msg:
                    approval_needed = False
                    findings = "VPN restoration approved and ready to execute."
                else:
                    approval_needed = True
                    findings = "VPN restoration requires approval."
            elif "visio" in prompt_lower:
                recommended_action = "install_software Visio"
                approval_needed = True
                findings = "Visio software install requires authorization."
            elif "password" in prompt_lower or "unlock" in prompt_lower:
                recommended_action = "unlock_ad_user"
                approval_needed = False
                findings = "AD account needs unlock check."
                
            text = json.dumps({
                "observations": ["Investigating reported symptoms."],
                "hypotheses": ["Service configuration mismatch"],
                "confidence": confidence,
                "approval_needed": approval_needed,
                "escalation_needed": False,
                "recommended_action": recommended_action or "",
                "findings": findings
            })

        # 7. Root Cause Analysis Agent
        elif "Root Cause Analysis agent" in prompt_str:
            text = json.dumps({
                "root_cause": "Configuration database timeout",
                "confidence": 0.95
            })

        # 8. SLA Priority Assessor / SLA Agent
        elif "IT Support SLA Agent" in prompt_str:
            priority = "LOW"
            if "critical" in prompt_lower or "production" in prompt_lower or "offline" in prompt_lower or "switch" in prompt_lower:
                priority = "CRITICAL"
            elif "high" in prompt_lower:
                priority = "HIGH"
            elif "medium" in prompt_lower:
                priority = "MEDIUM"
                
            text = json.dumps({
                "priority": priority,
                "reason": "Calculated based on business urgency and corporate impact guidelines."
            })

        # 9. Engineer Summary Agent
        elif "IT Support Engineer for Bridgestone" in prompt_str:
            text = "Resolution summary: Resolved issue and confirmed user connectivity."

        # 10. KB Article Generator
        elif "IT Knowledge Base Expert" in prompt_str:
            text = "Title: VPN Gateway Restorations\nResolution Steps: 1. Confirm MFA. 2. Restart connection."

        # 11. Response Agent / Colleague / general text replies
        elif "Service Desk Engineer" in prompt_str or "Service Desk Colleague" in prompt_str:
            text = "Thank you for reaching out to Bridgestone IT support. I will check our systems and help you resolve this issue."

        mock_resp = MagicMock()
        mock_resp.text = text
        mock_resp.usage_metadata = None
        return mock_resp

def configure(*args, **kwargs):
    pass

# Mock legacy generativeai module exports
mock_genai = MagicMock()
mock_genai.GenerativeModel = MockGenerativeModel
mock_genai.configure = configure

# Inject legacy google.generativeai into sys.modules
sys.modules["google.generativeai"] = mock_genai
print("[MOCK] google.generativeai client successfully mocked globally.")

# Define modern google-genai SDK mocks
class MockHttpOptions:
    def __init__(self, *args, **kwargs):
        pass

class MockContent:
    def __init__(self, *args, **kwargs):
        pass

class MockPart:
    @staticmethod
    def from_text(text):
        return text

class MockGenerateContentConfig:
    def __init__(self, *args, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)

class MockGenAIChat:
    def __init__(self, model, history=None, config=None):
        self.model = model
        self.history = history or []
        self.config = config

    def send_message(self, message, config=None):
        m = MockGenerativeModel(self.model)
        system_instruction = getattr(self.config, "system_instruction", "") if self.config else ""
        prompt = message
        if system_instruction:
            prompt = f"{system_instruction}\n\n{prompt}"
        return m.generate_content(prompt)

class MockChats:
    def create(self, model, history=None, config=None):
        return MockGenAIChat(model, history, config)

class MockModels:
    def generate_content(self, model, contents, config=None):
        m = MockGenerativeModel(model)
        return m.generate_content(contents)

class MockGenAIClient:
    def __init__(self, *args, **kwargs):
        self.chats = MockChats()
        self.models = MockModels()

# Create mock google.genai module and google.genai.types
mock_genai_module = MagicMock()
mock_genai_module.Client = MockGenAIClient

mock_types_module = MagicMock()
mock_types_module.HttpOptions = MockHttpOptions
mock_types_module.Content = MockContent
mock_types_module.Part = MockPart
mock_types_module.GenerateContentConfig = MockGenerateContentConfig

# Inject modern google-genai into sys.modules
sys.modules["google.genai"] = mock_genai_module
sys.modules["google.genai.types"] = mock_types_module
print("[MOCK] google.genai and google.genai.types successfully mocked globally.")

