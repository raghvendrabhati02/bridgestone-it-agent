import logging
import json
import os
import google.generativeai as genai
from app.graph.state import AgentState
from app.services.catalog_service import get_service_catalog, create_service_request
from app.database.session import get_db

logger = logging.getLogger("it-agent-backend")

REQUIRED_SLOTS = {
    "SRV001": ["software_name", "justification"],
    "SRV002": ["connection_profile", "mfa_method", "justification"],
    "SRV003": ["folder_path", "access_type", "justification"],
    "SRV004": ["sap_system", "requested_role", "justification"],
    "SRV005": ["username_to_unlock", "justification"],
    "SRV006": ["list_name", "action", "justification"],
    "SRV007": ["printer_name", "location", "justification"],
    "SRV008": ["laptop_model", "justification"],
    "SRV009": ["monitor_size", "justification"],
    "SRV010": ["device_model", "justification"],
    "SRV011": ["new_hire_name", "start_date", "department", "justification"],
    "SRV012": ["db_type", "access_level", "justification"],
    "SRV013": ["cloud_provider", "justification"],
    "SRV014": ["badge_type", "location_access", "justification"],
    "SRV015": ["accessory_type", "justification"]
}

SLOT_PROMPTS = {
    "software_name": "Which software application do you need installed (e.g., Microsoft Visio, Adobe Acrobat, Zoom Pro)?",
    "justification": "Could you please provide a brief business justification or reason for this request?",
    "connection_profile": "Which VPN connection profile do you require (e.g., APAC-Gateway, US-Gateway, EMEA-Gateway)?",
    "mfa_method": "What is your preferred Multi-Factor Authentication (MFA) method (e.g., Microsoft Authenticator, SMS)?",
    "folder_path": "What is the network path or folder name of the shared folder you need access to?",
    "access_type": "Do you require 'Read-Only' or 'Read-Write' permissions?",
    "sap_system": "Which SAP system do you need access to (e.g., Production PRD, Sandbox, Development)?",
    "requested_role": "What specific role or transaction group do you require in SAP (e.g., FICO Analyst, BASIS, Read-Only)?",
    "username_to_unlock": "What is the domain username of the account you wish to unlock?",
    "list_name": "What is the email address, alias, or display name of the distribution list?",
    "action": "Do you want to 'Create New' or 'Modify Existing' for this distribution list?",
    "printer_name": "What is the name or device ID of the printer you want to connect to?",
    "location": "Where is the printer or workstation located (building, floor, desk number)?",
    "laptop_model": "Which corporate laptop model would you like to request (e.g., Lenovo ThinkPad, Apple MacBook Pro 16)?",
    "monitor_size": "What size monitor do you need (e.g., single 34-inch ultrawide, dual 24-inch flat panels)?",
    "device_model": "Which mobile device model are you requesting (e.g., Apple iPhone 15 Pro, Samsung Galaxy S24)?",
    "new_hire_name": "What is the full name of the new employee?",
    "start_date": "What is the employee's start date (YYYY-MM-DD)?",
    "department": "Which department or team will the new employee be joining?",
    "db_type": "What database type are you requesting access to (e.g., Oracle, PostgreSQL, MS SQL Server)?",
    "access_level": "What database permission level do you require (e.g., Read-Only, Read-Write)?",
    "cloud_provider": "Which cloud service provider sandbox do you need (AWS, Azure, GCP)?",
    "badge_type": "What type of physical access badge do you need (e.g., Employee, Contractor, Guest pass)?",
    "location_access": "Which building facilities or security zones do you need badge access to (e.g., Building A, Server Room)?",
    "accessory_type": "Which ergonomic accessory are you requesting (e.g., ergonomic mouse, keyboard, chair riser)?"
}

def service_request_node(state: AgentState) -> dict:
    logger.info("--- Service Request Node ---")
    session_id = state.get("session_id")
    user_msg = state.get("user_message", "")
    username = state.get("username", "employee")
    
    active_req = state.get("active_request", "")
    goal_str = state.get("conversation_goal", "")
    
    slots = {}
    if goal_str:
        try:
            slots = json.loads(goal_str)
        except Exception:
            pass
            
    catalog = get_service_catalog()
    
    if not active_req:
        mapped_service_id = None
        
        msg_lower = user_msg.lower()
        if "visio" in msg_lower or "adobe" in msg_lower or "zoom" in msg_lower or "software installation" in msg_lower or "install software" in msg_lower:
            mapped_service_id = "SRV001"
        elif "vpn" in msg_lower or "anyconnect" in msg_lower:
            mapped_service_id = "SRV002"
        elif "shared folder" in msg_lower or "folder access" in msg_lower or "network share" in msg_lower:
            mapped_service_id = "SRV003"
        elif "sap" in msg_lower:
            mapped_service_id = "SRV004"
        elif "unlock" in msg_lower or "ad lock" in msg_lower:
            mapped_service_id = "SRV005"
        elif "distribution list" in msg_lower or "email list" in msg_lower or "mailing group" in msg_lower:
            mapped_service_id = "SRV006"
        elif "printer" in msg_lower:
            mapped_service_id = "SRV007"
        elif "laptop" in msg_lower or "macbook" in msg_lower or "thinkpad" in msg_lower:
            mapped_service_id = "SRV008"
        elif "monitor" in msg_lower or "screen" in msg_lower:
            mapped_service_id = "SRV009"
        elif "mobile" in msg_lower or "phone" in msg_lower or "iphone" in msg_lower or "galaxy" in msg_lower:
            mapped_service_id = "SRV010"
        elif "onboard" in msg_lower or "new employee" in msg_lower or "new hire" in msg_lower:
            mapped_service_id = "SRV011"
        elif "database" in msg_lower or "postgres" in msg_lower or "oracle" in msg_lower or "sql server" in msg_lower:
            mapped_service_id = "SRV012"
        elif "sandbox" in msg_lower or "aws" in msg_lower or "azure" in msg_lower or "gcp" in msg_lower:
            mapped_service_id = "SRV013"
        elif "badge" in msg_lower or "physical access" in msg_lower or "keycard" in msg_lower:
            mapped_service_id = "SRV014"
        elif "ergonomic" in msg_lower or "chair" in msg_lower or "keyboard" in msg_lower or "mouse" in msg_lower:
            mapped_service_id = "SRV015"
            
        api_key = os.getenv("GEMINI_API_KEY")
        if not mapped_service_id and api_key:
            try:
                catalog_desc = "\n".join([f"- {i['service_id']}: {i['name']} ({i['description']})" for i in catalog])
                prompt = (
                    "Match the user's service request message to one of the following corporate catalog service IDs.\n"
                    "If none matches perfectly, match the closest one or return null.\n\n"
                    f"Catalog:\n{catalog_desc}\n\n"
                    f"User Message: {user_msg}\n\n"
                    "Return ONLY a JSON object matching:\n"
                    '{\n  "service_id": "SRVxxx" or null\n}'
                )
                genai.configure(api_key=api_key)
                model = genai.GenerativeModel("gemini-2.5-flash-lite")
                resp = model.generate_content(prompt, generation_config={"response_mime_type": "application/json"})
                if resp and resp.text:
                    res_dict = json.loads(resp.text.strip())
                    mapped_service_id = res_dict.get("service_id")
            except Exception as e:
                logger.warning("Service Request Node: Gemini catalog mapping failed: %s", e)

        if not mapped_service_id:
            list_str = "\n".join([f"- {i['name']} (ID: {i['service_id']})" for i in catalog[:8]])
            response = f"I recognize that you want to request a service. Could you please specify which item from our Service Catalog you need?\nHere are some common ones:\n{list_str}"
            return {
                "decision_response": response,
                "route": "service_request"
            }
            
        active_req = mapped_service_id
        slots = {"service_id": active_req}
        
    service_item = next((item for item in catalog if item["service_id"] == active_req), None)
    if not service_item:
        return {
            "active_request": "",
            "conversation_goal": "",
            "decision_response": "I couldn't locate that service item in our catalog. How else can I assist you?",
            "route": "intent"
        }
        
    required_keys = REQUIRED_SLOTS.get(active_req, ["justification"])
    api_key = os.getenv("GEMINI_API_KEY")
    if api_key:
        try:
            history = []
            try:
                from app.services.conversation_service import get_conversation
                conv_state = get_conversation(session_id)
                history = conv_state.conversation_history if conv_state else []
            except Exception:
                pass
            
            history_str = "\n".join([f"{'User' if h['sender'] == 'user' else 'Agent'}: {h['text']}" for h in history[-5:]])
            history_str += f"\nLatest User Message: {user_msg}"
            
            slots_desc = "\n".join([f"- {k}: value (representing {SLOT_PROMPTS.get(k, k)})" for k in required_keys])
            
            prompt = (
                f"You are an information extraction assistant. Extract the value for these parameters from the user conversation history:\n"
                f"{slots_desc}\n\n"
                f"Conversation History:\n{history_str}\n\n"
                f"Current extracted parameters so far: {json.dumps(slots)}\n\n"
                "Return ONLY a JSON object of the updated extracted parameters (keys must exactly match, use null or omit if not found in conversation):\n"
                "{\n"
                '  "param1": "value", ...\n'
                "}"
            )
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel("gemini-2.5-flash-lite")
            resp = model.generate_content(prompt, generation_config={"response_mime_type": "application/json"})
            if resp and resp.text:
                extracted = json.loads(resp.text.strip())
                for k in required_keys:
                    if extracted.get(k):
                        slots[k] = extracted[k]
        except Exception as e:
            logger.warning("Service Request Node: Gemini slot extraction failed: %s", e)
            
    msg_lower = user_msg.lower()
    first_missing_before = None
    for k in required_keys:
        if k not in slots or not slots[k]:
            first_missing_before = k
            break

    for k in required_keys:
        if k not in slots or not slots[k]:
            if k == "software_name" and ("visio" in msg_lower or "adobe" in msg_lower or "zoom" in msg_lower):
                slots["software_name"] = "Microsoft Visio" if "visio" in msg_lower else ("Adobe Acrobat" if "adobe" in msg_lower else "Zoom Pro")
            elif k == "sap_system" and ("prd" in msg_lower or "sandbox" in msg_lower or "dev" in msg_lower):
                slots["sap_system"] = "PRD" if "prd" in msg_lower else ("Sandbox" if "sandbox" in msg_lower else "Development")
            elif k == "requested_role" and "fico" in msg_lower:
                slots["requested_role"] = "FICO Analyst"
            elif k == "justification" and len(user_msg) > 15 and not any(phrase in msg_lower for phrase in ["yes", "no", "ok", "please", "request"]):
                slots["justification"] = user_msg

    was_active = bool(state.get("active_request", ""))
    if was_active and first_missing_before:
        if first_missing_before not in slots or not slots[first_missing_before]:
            slots[first_missing_before] = user_msg

    missing_slot = None
    for slot in required_keys:
        if slot not in slots or not slots[slot]:
            missing_slot = slot
            break
            
    if missing_slot:
        prompt_text = SLOT_PROMPTS.get(missing_slot, f"Please specify the {missing_slot}:")
        return {
            "active_request": active_req,
            "conversation_goal": json.dumps(slots),
            "decision_response": f"To process your request for **{service_item['name']}**, I need a bit more details.\n{prompt_text}",
            "route": "service_request"
        }
        
    try:
        req_details = {k: slots[k] for k in required_keys}
        created_req = create_service_request(active_req, username, req_details)
        
        req_id = created_req["request_id"]
        status = created_req["status"]
        team = created_req["assigned_team"] or "Helpdesk"
        
        if status == "PENDING_APPROVAL":
            response = f"Thank you! I have created your Service Request **{req_id}** for **{service_item['name']}**.\n\n" \
                       f"Because this request requires manager approval, it has been routed to your manager for review. " \
                       f"Once approved, it will be fulfilled by the **{team}**."
        else:
            response = f"Success! I have created your Service Request **{req_id}** for **{service_item['name']}**.\n\n" \
                       f"The request is pre-approved and has been assigned to the **{team}** for fulfillment. " \
                       f"Estimated completion: **{service_item['estimated_completion'] or '1 Business Day'}**."
                       
        return {
            "active_request": "",
            "conversation_goal": "",
            "decision_response": response,
            "route": "intent"
        }
    except Exception as e:
        logger.error("Service Request Node: Failed to create request: %s", e)
        return {
            "active_request": "",
            "conversation_goal": "",
            "decision_response": f"I encountered an error while trying to register your request: {e}. Please contact the Helpdesk.",
            "route": "intent"
        }
