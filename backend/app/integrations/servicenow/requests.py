import logging
import time

logger = logging.getLogger("it-agent-backend")

def create_service_request(client, category: str, description: str, action_type: str) -> dict:
    from app.core.metrics import SERVICENOW_REQUESTS_TOTAL, SERVICENOW_FAILURES_TOTAL, SERVICENOW_LATENCY_SECONDS, SERVICE_REQUESTS_CREATED_TOTAL
    
    url = f"{client.instance_url}/api/now/table/sc_request"
    payload = {
        "short_description": f"Service Request: {action_type}",
        "description": f"Category: {category}\nAction Type: {action_type}\nDescription: {description}",
        "requested_for": client.username or "it_agent",
        "approval": "approved"
    }
    
    headers = client._get_headers()
    start_time = time.time()
    
    try:
        try:
            SERVICENOW_REQUESTS_TOTAL.labels(operation="create_request").inc()
        except Exception:
            pass
            
        logger.info("ServiceNow Request REST API: Creating catalog request for action_type=%s", action_type)
        response = client._request("POST", url, headers=headers, json=payload)
        latency = time.time() - start_time
        
        try:
            SERVICENOW_LATENCY_SECONDS.labels(operation="create_request").observe(latency)
        except Exception:
            pass
            
        if response.status_code in (200, 201):
            result = response.json().get("result", {})
            sys_id = result.get("sys_id")
            number = result.get("number")
            state_raw = result.get("request_state") or result.get("approval")
            state_mapped = "CLOSED" if state_raw in ("closed_complete", "rejected") else "OPEN"
            
            logger.info("ServiceNow Audit: Request Created - ID: %s, Number: %s", sys_id, number)
            try:
                SERVICE_REQUESTS_CREATED_TOTAL.inc()
            except Exception:
                pass
                
            return {
                "sys_id": sys_id,
                "number": number,
                "state": state_mapped,
                "category": category,
                "description": description,
                "action_type": action_type
            }
        else:
            try:
                SERVICENOW_FAILURES_TOTAL.labels(operation="create_request", error_type=str(response.status_code)).inc()
            except Exception:
                pass
            logger.error("ServiceNow Audit: ServiceNow Errors - Operation: create_request, Status: %d, Response: %s", response.status_code, response.text)
            raise RuntimeError(f"ServiceNow Request creation failed with status {response.status_code}: {response.text}")
            
    except Exception as e:
        logger.error("ServiceNow Audit: ServiceNow Errors - Operation: create_request, Exception: %s", e)
        try:
            SERVICENOW_FAILURES_TOTAL.labels(operation="create_request", error_type=type(e).__name__).inc()
        except Exception:
            pass
        raise e

def get_request_status(client, sys_id: str) -> dict:
    from app.core.metrics import SERVICENOW_REQUESTS_TOTAL, SERVICENOW_FAILURES_TOTAL, SERVICENOW_LATENCY_SECONDS
    url = f"{client.instance_url}/api/now/table/sc_request/{sys_id}"
    headers = client._get_headers()
    start_time = time.time()
    
    try:
        try:
            SERVICENOW_REQUESTS_TOTAL.labels(operation="get_request").inc()
        except Exception:
            pass
            
        logger.info("ServiceNow Request REST API: Fetching request %s", sys_id)
        response = client._request("GET", url, headers=headers)
        latency = time.time() - start_time
        
        try:
            SERVICENOW_LATENCY_SECONDS.labels(operation="get_request").observe(latency)
        except Exception:
            pass
            
        if response.status_code == 200:
            result = response.json().get("result", {})
            state_raw = result.get("request_state") or result.get("approval")
            state_mapped = "CLOSED" if state_raw in ("closed_complete", "rejected") else "OPEN"
            
            return {
                "sys_id": result.get("sys_id"),
                "number": result.get("number"),
                "state": state_mapped,
                "category": "GENERAL",
                "description": result.get("description", ""),
                "action_type": result.get("short_description", "")
            }
        else:
            try:
                SERVICENOW_FAILURES_TOTAL.labels(operation="get_request", error_type=str(response.status_code)).inc()
            except Exception:
                pass
            raise KeyError(f"ServiceNow Catalog Request {sys_id} not found.")
    except Exception as e:
        try:
            SERVICENOW_FAILURES_TOTAL.labels(operation="get_request", error_type=type(e).__name__).inc()
        except Exception:
            pass
        raise e

def update_request(client, sys_id: str, updates: dict) -> dict:
    from app.core.metrics import SERVICENOW_REQUESTS_TOTAL, SERVICENOW_FAILURES_TOTAL, SERVICENOW_LATENCY_SECONDS
    url = f"{client.instance_url}/api/now/table/sc_request/{sys_id}"
    headers = client._get_headers()
    
    payload = {}
    if "state" in updates:
        payload["request_state"] = "closed_complete" if updates["state"] == "CLOSED" else "requested"
        
    start_time = time.time()
    try:
        try:
            SERVICENOW_REQUESTS_TOTAL.labels(operation="update_request").inc()
        except Exception:
            pass
            
        logger.info("ServiceNow Request REST API: Updating request %s with %s", sys_id, payload)
        response = client._request("PATCH", url, headers=headers, json=payload)
        latency = time.time() - start_time
        
        try:
            SERVICENOW_LATENCY_SECONDS.labels(operation="update_request").observe(latency)
        except Exception:
            pass
            
        if response.status_code == 200:
            result = response.json().get("result", {})
            state_raw = result.get("request_state") or result.get("approval")
            state_mapped = "CLOSED" if state_raw in ("closed_complete", "rejected") else "OPEN"
            
            return {
                "sys_id": result.get("sys_id"),
                "number": result.get("number"),
                "state": state_mapped,
                "category": "GENERAL",
                "description": result.get("description", ""),
                "action_type": result.get("short_description", "")
            }
        else:
            try:
                SERVICENOW_FAILURES_TOTAL.labels(operation="update_request", error_type=str(response.status_code)).inc()
            except Exception:
                pass
            raise KeyError(f"ServiceNow Catalog Request {sys_id} not found.")
    except Exception as e:
        try:
            SERVICENOW_FAILURES_TOTAL.labels(operation="update_request", error_type=type(e).__name__).inc()
        except Exception:
            pass
        raise e

def get_all_requests(client) -> list:
    from app.core.metrics import SERVICENOW_REQUESTS_TOTAL, SERVICENOW_FAILURES_TOTAL, SERVICENOW_LATENCY_SECONDS
    url = f"{client.instance_url}/api/now/table/sc_request"
    headers = client._get_headers()
    start_time = time.time()
    try:
        try:
            SERVICENOW_REQUESTS_TOTAL.labels(operation="get_all_requests").inc()
        except Exception:
            pass
            
        logger.info("ServiceNow Request REST API: Fetching all service requests")
        response = client._request("GET", url, headers=headers)
        latency = time.time() - start_time
        
        try:
            SERVICENOW_LATENCY_SECONDS.labels(operation="get_all_requests").observe(latency)
        except Exception:
            pass
            
        if response.status_code == 200:
            results = response.json().get("result", [])
            mapped = []
            for result in results:
                state_raw = result.get("request_state") or result.get("approval")
                state_mapped = "CLOSED" if state_raw in ("closed_complete", "rejected") else "OPEN"
                mapped.append({
                    "sys_id": result.get("sys_id"),
                    "number": result.get("number"),
                    "state": state_mapped,
                    "category": "GENERAL",
                    "description": result.get("description", ""),
                    "action_type": result.get("short_description", "")
                })
            return mapped
        else:
            try:
                SERVICENOW_FAILURES_TOTAL.labels(operation="get_all_requests", error_type=str(response.status_code)).inc()
            except Exception:
                pass
            logger.error("ServiceNow Audit: ServiceNow Errors - Operation: get_all_requests, Status: %d, Response: %s", response.status_code, response.text)
            raise RuntimeError(f"Failed to fetch ServiceNow catalog requests: {response.text}")
    except Exception as e:
        logger.error("ServiceNow Audit: ServiceNow Errors - Operation: get_all_requests, Exception: %s", e)
        try:
            SERVICENOW_FAILURES_TOTAL.labels(operation="get_all_requests", error_type=type(e).__name__).inc()
        except Exception:
            pass
        raise e
