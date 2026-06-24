import datetime
import logging
from app.adapters.servicenow_adapter import ServiceNowAdapter

logger = logging.getLogger("it-agent-backend")

# Initialize ServiceNow adapter client
servicenow_client = ServiceNowAdapter()

actions = []
action_counter = 0

def get_all_actions() -> list[dict]:
    return actions

def create_vpn_restoration_request(detail: str = "") -> dict:
    return execute_action("VPN_ACCESS_RESTORATION", "VPN", detail or "VPN access restoration request.")

def create_software_install_request(software_name: str = "") -> dict:
    return execute_action("SOFTWARE_INSTALLATION", "SOFTWARE_INSTALLATION", f"Install software request for {software_name or 'Chrome'}.")

def create_access_restoration_request(category: str = "GENERAL", detail: str = "") -> dict:
    return execute_action("ACCESS_RESTORATION", category, detail or f"Access restoration request for {category}.")

def create_general_service_request(detail: str = "") -> dict:
    return execute_action("GENERAL_SERVICE_REQUEST", "GENERAL", detail or "General IT support service request.")

def execute_action(action_type: str, category: str, user_message: str) -> dict:
    global action_counter
    action_counter += 1
    
    request_id = f"REQ{action_counter:06d}"
    created_at = datetime.datetime.utcnow().isoformat() + "Z"
    
    # Resolve description
    description = user_message
    if action_type == "SOFTWARE_INSTALLATION" and "chrome" in user_message.lower():
        description = "Install software: Chrome"
    
    # Create ServiceNow catalog request using adapter client
    try:
        snow_req = servicenow_client.create_service_request(
            category=category,
            description=description,
            action_type=action_type
        )
        servicenow_id = snow_req.get("number", f"SR{action_counter:06d}")
    except Exception as e:
        logger.error("Action Service: Failed to create ServiceNow request. Error: %s", e)
        servicenow_id = f"SR{action_counter:06d}"
        
    action_record = {
        "request_id": request_id,
        "action_type": action_type,
        "servicenow_id": servicenow_id,
        "status": "OPEN",
        "created_at": created_at,
        "approved_by_user": True
    }
    
    actions.append(action_record)
    
    # Log Action History in Audit Logging Framework
    try:
        from app.services.audit_service import log_action
        log_action(
            request_id=request_id,
            action_type=action_type,
            status="OPEN",
            approved_by_user=True,
            servicenow_id=servicenow_id
        )
    except Exception as e:
        logger.error("Action Service: Failed to log audit action: %s", e)
        
    logger.info("Action Service: Executed action %s (Request: %s, ServiceNow: %s)", action_type, request_id, servicenow_id)
    return action_record
