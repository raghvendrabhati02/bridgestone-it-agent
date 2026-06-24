import logging
import time

logger = logging.getLogger("it-agent-backend")

def create_incident(client, category: str, description: str, assignment_group: str) -> dict:
    from app.core.metrics import SERVICENOW_REQUESTS_TOTAL, SERVICENOW_FAILURES_TOTAL, SERVICENOW_LATENCY_SECONDS, INCIDENTS_CREATED_TOTAL
    from .assignment_groups import resolve_assignment_group
    
    group_sys_id = resolve_assignment_group(client, assignment_group)
    url = f"{client.instance_url}/api/now/table/incident"
    payload = {
        "short_description": f"IT Support: {category}",
        "description": description,
        "category": category.lower(),
        "assignment_group": group_sys_id,
        "caller_id": client.username or "it_agent"
    }
    
    headers = client._get_headers()
    start_time = time.time()
    
    try:
        try:
            SERVICENOW_REQUESTS_TOTAL.labels(operation="create_incident").inc()
        except Exception:
            pass
            
        logger.info("ServiceNow Incident REST API: Creating incident for category=%s", category)
        response = client._request("POST", url, headers=headers, json=payload)
        latency = time.time() - start_time
        
        try:
            SERVICENOW_LATENCY_SECONDS.labels(operation="create_incident").observe(latency)
        except Exception:
            pass
            
        if response.status_code in (200, 201):
            result = response.json().get("result", {})
            sys_id = result.get("sys_id")
            number = result.get("number")
            state_raw = result.get("state")
            state_mapped = "CLOSED" if state_raw in ("7", "8") else "OPEN"
            
            logger.info("ServiceNow Audit: Incident Created - ID: %s, Number: %s", sys_id, number)
            try:
                INCIDENTS_CREATED_TOTAL.inc()
            except Exception:
                pass
                
            return {
                "sys_id": sys_id,
                "number": number,
                "state": state_mapped,
                "category": category,
                "description": description,
                "assignment_group": assignment_group
            }
        else:
            try:
                SERVICENOW_FAILURES_TOTAL.labels(operation="create_incident", error_type=str(response.status_code)).inc()
            except Exception:
                pass
            logger.error("ServiceNow Audit: ServiceNow Errors - Operation: create_incident, Status: %d, Response: %s", response.status_code, response.text)
            raise RuntimeError(f"ServiceNow Incident creation failed with status {response.status_code}: {response.text}")
            
    except Exception as e:
        logger.error("ServiceNow Audit: ServiceNow Errors - Operation: create_incident, Exception: %s", e)
        try:
            SERVICENOW_FAILURES_TOTAL.labels(operation="create_incident", error_type=type(e).__name__).inc()
        except Exception:
            pass
        raise e

def get_incident(client, sys_id: str) -> dict:
    from app.core.metrics import SERVICENOW_REQUESTS_TOTAL, SERVICENOW_FAILURES_TOTAL, SERVICENOW_LATENCY_SECONDS
    url = f"{client.instance_url}/api/now/table/incident/{sys_id}"
    headers = client._get_headers()
    start_time = time.time()
    
    try:
        try:
            SERVICENOW_REQUESTS_TOTAL.labels(operation="get_incident").inc()
        except Exception:
            pass
            
        logger.info("ServiceNow Incident REST API: Fetching incident %s", sys_id)
        response = client._request("GET", url, headers=headers)
        latency = time.time() - start_time
        
        try:
            SERVICENOW_LATENCY_SECONDS.labels(operation="get_incident").observe(latency)
        except Exception:
            pass
            
        if response.status_code == 200:
            result = response.json().get("result", {})
            state_raw = result.get("state")
            state_mapped = "CLOSED" if state_raw in ("7", "8") else "OPEN"
            
            return {
                "sys_id": result.get("sys_id"),
                "number": result.get("number"),
                "state": state_mapped,
                "category": result.get("category", ""),
                "description": result.get("description", ""),
                "assignment_group": result.get("assignment_group", "")
            }
        else:
            try:
                SERVICENOW_FAILURES_TOTAL.labels(operation="get_incident", error_type=str(response.status_code)).inc()
            except Exception:
                pass
            raise KeyError(f"ServiceNow Incident {sys_id} not found.")
    except Exception as e:
        try:
            SERVICENOW_FAILURES_TOTAL.labels(operation="get_incident", error_type=type(e).__name__).inc()
        except Exception:
            pass
        raise e

def update_incident(client, sys_id: str, updates: dict) -> dict:
    from app.core.metrics import SERVICENOW_REQUESTS_TOTAL, SERVICENOW_FAILURES_TOTAL, SERVICENOW_LATENCY_SECONDS
    from .assignment_groups import resolve_assignment_group
    
    url = f"{client.instance_url}/api/now/table/incident/{sys_id}"
    headers = client._get_headers()
    
    payload = {}
    if "state" in updates:
        payload["state"] = "7" if updates["state"] == "CLOSED" else "1"
    if "assignment_group" in updates:
        payload["assignment_group"] = resolve_assignment_group(client, updates["assignment_group"])
        
    start_time = time.time()
    try:
        try:
            SERVICENOW_REQUESTS_TOTAL.labels(operation="update_incident").inc()
        except Exception:
            pass
            
        logger.info("ServiceNow Incident REST API: Updating incident %s with %s", sys_id, payload)
        response = client._request("PATCH", url, headers=headers, json=payload)
        latency = time.time() - start_time
        
        try:
            SERVICENOW_LATENCY_SECONDS.labels(operation="update_incident").observe(latency)
        except Exception:
            pass
            
        if response.status_code == 200:
            result = response.json().get("result", {})
            state_raw = result.get("state")
            state_mapped = "CLOSED" if state_raw in ("7", "8") else "OPEN"
            
            logger.info("ServiceNow Audit: Incident Updated - ID: %s, Updates: %s", sys_id, payload)
            return {
                "sys_id": result.get("sys_id"),
                "number": result.get("number"),
                "state": state_mapped,
                "category": result.get("category", ""),
                "description": result.get("description", ""),
                "assignment_group": result.get("assignment_group", "")
            }
        else:
            try:
                SERVICENOW_FAILURES_TOTAL.labels(operation="update_incident", error_type=str(response.status_code)).inc()
            except Exception:
                pass
            logger.error("ServiceNow Audit: ServiceNow Errors - Operation: update_incident, Status: %d, Response: %s", response.status_code, response.text)
            raise KeyError(f"ServiceNow Incident {sys_id} not found.")
    except Exception as e:
        logger.error("ServiceNow Audit: ServiceNow Errors - Operation: update_incident, Exception: %s", e)
        try:
            SERVICENOW_FAILURES_TOTAL.labels(operation="update_incident", error_type=type(e).__name__).inc()
        except Exception:
            pass
        raise e

def close_incident(client, sys_id: str) -> dict:
    res = update_incident(client, sys_id, {"state": "CLOSED"})
    logger.info("ServiceNow Audit: Incident Closed - ID: %s", sys_id)
    return res

def get_all_incidents(client) -> list:
    from app.core.metrics import SERVICENOW_REQUESTS_TOTAL, SERVICENOW_FAILURES_TOTAL, SERVICENOW_LATENCY_SECONDS
    url = f"{client.instance_url}/api/now/table/incident"
    headers = client._get_headers()
    start_time = time.time()
    try:
        try:
            SERVICENOW_REQUESTS_TOTAL.labels(operation="get_all_incidents").inc()
        except Exception:
            pass
            
        logger.info("ServiceNow Incident REST API: Fetching all incidents")
        response = client._request("GET", url, headers=headers)
        latency = time.time() - start_time
        
        try:
            SERVICENOW_LATENCY_SECONDS.labels(operation="get_all_incidents").observe(latency)
        except Exception:
            pass
            
        if response.status_code == 200:
            results = response.json().get("result", [])
            mapped = []
            for result in results:
                state_raw = result.get("state")
                state_mapped = "CLOSED" if state_raw in ("7", "8") else "OPEN"
                mapped.append({
                    "sys_id": result.get("sys_id"),
                    "number": result.get("number"),
                    "state": state_mapped,
                    "category": result.get("category", ""),
                    "description": result.get("description", ""),
                    "assignment_group": result.get("assignment_group", "")
                })
            return mapped
        else:
            try:
                SERVICENOW_FAILURES_TOTAL.labels(operation="get_all_incidents", error_type=str(response.status_code)).inc()
            except Exception:
                pass
            logger.error("ServiceNow Audit: ServiceNow Errors - Operation: get_all_incidents, Status: %d, Response: %s", response.status_code, response.text)
            raise RuntimeError(f"Failed to fetch ServiceNow incidents: {response.text}")
    except Exception as e:
        logger.error("ServiceNow Audit: ServiceNow Errors - Operation: get_all_incidents, Exception: %s", e)
        try:
            SERVICENOW_FAILURES_TOTAL.labels(operation="get_all_incidents", error_type=type(e).__name__).inc()
        except Exception:
            pass
        raise e
