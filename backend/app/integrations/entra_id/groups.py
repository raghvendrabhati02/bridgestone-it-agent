import logging
import time

logger = logging.getLogger("it-agent-backend")

def get_user_groups(client, user_id: str) -> list:
    from app.core.metrics import AD_REQUESTS_TOTAL, AD_FAILURES_TOTAL, AD_LATENCY_SECONDS
    url = f"https://graph.microsoft.com/v1.0/users/{user_id}/memberOf"
    start_time = time.time()
    try:
        try:
            AD_REQUESTS_TOTAL.labels(operation="get_user_groups").inc()
        except Exception:
            pass
            
        logger.info("Entra ID API: Fetching member groups of user %s", user_id)
        response = client._request("GET", url)
        latency = time.time() - start_time
        
        try:
            AD_LATENCY_SECONDS.labels(operation="get_user_groups").observe(latency)
        except Exception:
            pass
            
        if response.status_code == 200:
            return response.json().get("value", [])
        else:
            try:
                AD_FAILURES_TOTAL.labels(operation="get_user_groups", error_type=str(response.status_code)).inc()
            except Exception:
                pass
            logger.error("Entra ID Audit: API Error - Operation: get_user_groups, Status: %d, Response: %s", response.status_code, response.text)
            return []
            
    except Exception as e:
        logger.error("Entra ID Audit: API Error - Operation: get_user_groups, Exception: %s", e)
        try:
            AD_FAILURES_TOTAL.labels(operation="get_user_groups", error_type=type(e).__name__).inc()
        except Exception:
            pass
        return []

def check_group_membership(client, user_id: str, group_name_or_id: str) -> bool:
    from app.core.metrics import GROUP_CHECKS_TOTAL
    try:
        GROUP_CHECKS_TOTAL.inc()
    except Exception:
        pass
    groups = get_user_groups(client, user_id)
    return any(g.get("displayName") == group_name_or_id or g.get("id") == group_name_or_id for g in groups)

def get_group_details(client, group_id: str) -> dict:
    from app.core.metrics import AD_REQUESTS_TOTAL, AD_FAILURES_TOTAL, AD_LATENCY_SECONDS
    url = f"https://graph.microsoft.com/v1.0/groups/{group_id}"
    start_time = time.time()
    try:
        try:
            AD_REQUESTS_TOTAL.labels(operation="get_group_details").inc()
        except Exception:
            pass
            
        logger.info("Entra ID API: Fetching group details for group %s", group_id)
        response = client._request("GET", url)
        latency = time.time() - start_time
        
        try:
            AD_LATENCY_SECONDS.labels(operation="get_group_details").observe(latency)
        except Exception:
            pass
            
        if response.status_code == 200:
            return response.json()
        else:
            try:
                AD_FAILURES_TOTAL.labels(operation="get_group_details", error_type=str(response.status_code)).inc()
            except Exception:
                pass
            logger.error("Entra ID Audit: API Error - Operation: get_group_details, Status: %d, Response: %s", response.status_code, response.text)
            raise KeyError(f"Entra ID: Group {group_id} not found.")
            
    except Exception as e:
        logger.error("Entra ID Audit: API Error - Operation: get_group_details, Exception: %s", e)
        try:
            AD_FAILURES_TOTAL.labels(operation="get_group_details", error_type=type(e).__name__).inc()
        except Exception:
            pass
        raise e

def get_all_groups(client) -> list:
    from app.core.metrics import AD_REQUESTS_TOTAL, AD_FAILURES_TOTAL, AD_LATENCY_SECONDS
    url = "https://graph.microsoft.com/v1.0/groups"
    start_time = time.time()
    try:
        try:
            AD_REQUESTS_TOTAL.labels(operation="get_all_groups").inc()
        except Exception:
            pass
            
        logger.info("Entra ID API: Fetching all directory groups")
        response = client._request("GET", url)
        latency = time.time() - start_time
        
        try:
            AD_LATENCY_SECONDS.labels(operation="get_all_groups").observe(latency)
        except Exception:
            pass
            
        if response.status_code == 200:
            return response.json().get("value", [])
        else:
            try:
                AD_FAILURES_TOTAL.labels(operation="get_all_groups", error_type=str(response.status_code)).inc()
            except Exception:
                pass
            logger.error("Entra ID Audit: API Error - Operation: get_all_groups, Status: %d, Response: %s", response.status_code, response.text)
            return []
    except Exception as e:
        logger.error("Entra ID Audit: API Error - Operation: get_all_groups, Exception: %s", e)
        try:
            AD_FAILURES_TOTAL.labels(operation="get_all_groups", error_type=type(e).__name__).inc()
        except Exception:
            pass
        return []
