import logging
from app.adapters.servicenow_adapter import ServiceNowAdapter

logger = logging.getLogger("it-agent-backend")
adapter = ServiceNowAdapter()

def create_servicenow_incident(category: str, description: str, assignment_group: str) -> dict:
    """
    Creates an incident in ServiceNow.
    """
    logger.info("Tools: Creating ServiceNow incident for category: %s, assigned to: %s", category, assignment_group)
    try:
        res = adapter.create_incident(category, description, assignment_group)
        return {
            "success": True,
            "sys_id": res.get("sys_id"),
            "number": res.get("number"),
            "category": res.get("category"),
            "description": res.get("description"),
            "assignment_group": res.get("assignment_group")
        }
    except Exception as e:
        logger.error("Tools: Failed to create ServiceNow incident: %s", e)
        return {"success": False, "error": str(e)}

def update_servicenow_incident(sys_id: str, updates: dict) -> dict:
    """
    Updates an incident in ServiceNow.
    """
    logger.info("Tools: Updating ServiceNow incident sys_id: %s", sys_id)
    try:
        res = adapter.update_incident(sys_id, updates)
        return {"success": True, "incident": res}
    except Exception as e:
        logger.error("Tools: Failed to update ServiceNow incident %s: %s", sys_id, e)
        return {"success": False, "error": str(e)}

def get_servicenow_incident(sys_id: str) -> dict:
    """
    Retrieves a ServiceNow incident by sys_id.
    """
    logger.info("Tools: Fetching ServiceNow incident sys_id: %s", sys_id)
    try:
        res = adapter.get_incident(sys_id)
        return {"success": True, "incident": res}
    except Exception as e:
        logger.error("Tools: Failed to retrieve ServiceNow incident %s: %s", sys_id, e)
        return {"success": False, "error": str(e)}

def close_servicenow_incident(sys_id: str) -> dict:
    """
    Closes a ServiceNow incident by sys_id.
    """
    logger.info("Tools: Closing ServiceNow incident sys_id: %s", sys_id)
    try:
        res = adapter.close_incident(sys_id)
        return {"success": True, "incident": res}
    except Exception as e:
        logger.error("Tools: Failed to close ServiceNow incident %s: %s", sys_id, e)
        return {"success": False, "error": str(e)}
