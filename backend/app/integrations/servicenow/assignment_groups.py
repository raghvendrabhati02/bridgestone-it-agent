import logging
import urllib.parse
from app.services.servicenow_choice_resolver import ServiceNowChoiceResolver

logger = logging.getLogger("it-agent-backend")

def resolve_assignment_group(client, category_or_team: str) -> str:
    """
    Resolves category or team name to a 32-character ServiceNow Group sys_id.
    Maps:
      VPN -> "Network Team" -> sys_id
      Outlook -> "Messaging Team" -> sys_id
      Software -> "Desktop Support Team" -> sys_id
      SAP -> "SAP Support Team" -> sys_id
    """
    cat_upper = category_or_team.strip().upper()
    
    # 1. Map category to group name
    group_name = category_or_team
    if cat_upper in ("VPN", "NETWORK"):
        group_name = "Network Team"
    elif cat_upper == "OUTLOOK":
        group_name = "Messaging Team"
    elif cat_upper in ("SOFTWARE", "SOFTWARE_INSTALLATION", "PRINTER"):
        group_name = "Desktop Support Team"
    elif cat_upper == "SAP":
        group_name = "SAP Support Team"
    elif cat_upper == "GENERAL":
        group_name = "IT Support Team"
        
    resolver = ServiceNowChoiceResolver.get_instance()
    
    # If using mock (or client is mock), return resolved 32-character sys_id
    if getattr(client, "use_mock", False):
        return resolver.resolve_assignment_group(group_name)
        
    # 2. Query Real ServiceNow Group Table (sys_user_group)
    try:
        query = f"name={group_name}"
        url = f"{client.instance_url}/api/now/table/sys_user_group?sysparm_query={urllib.parse.quote(query)}&sysparm_limit=1"
        
        headers = client._get_headers()
        response = client._request("GET", url, headers=headers)
        
        if response.status_code == 200:
            result = response.json().get("result", [])
            if result:
                sys_id = result[0].get("sys_id")
                if sys_id and len(sys_id) == 32:
                    logger.info("ServiceNow Assignment: Resolved group '%s' to sys_id %s", group_name, sys_id)
                    return sys_id
    except Exception as e:
        logger.error("ServiceNow Assignment: Exception during group lookup for '%s': %s", group_name, e)
        
    return resolver.resolve_assignment_group(group_name)
