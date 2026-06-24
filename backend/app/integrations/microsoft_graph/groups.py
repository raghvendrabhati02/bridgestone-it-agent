import logging
import time

logger = logging.getLogger("it-agent-backend")

def get_group_membership(client, group_id: str) -> list:
    from app.core.metrics import GRAPH_REQUESTS_TOTAL, GRAPH_FAILURES_TOTAL, GRAPH_LATENCY_SECONDS
    url = f"https://graph.microsoft.com/v1.0/groups/{group_id}/members"
    start_time = time.time()
    try:
        try:
            GRAPH_REQUESTS_TOTAL.labels(operation="get_group_membership").inc()
        except Exception:
            pass
            
        logger.info("Microsoft Graph API: Fetching members of group %s", group_id)
        response = client._request("GET", url)
        latency = time.time() - start_time
        
        try:
            GRAPH_LATENCY_SECONDS.labels(operation="get_group_membership").observe(latency)
        except Exception:
            pass
            
        if response.status_code == 200:
            return response.json().get("value", [])
        else:
            try:
                GRAPH_FAILURES_TOTAL.labels(operation="get_group_membership", error_type=str(response.status_code)).inc()
            except Exception:
                pass
            logger.error("Microsoft Graph Audit: API Error - Operation: get_group_membership, Status: %d, Response: %s", response.status_code, response.text)
            raise RuntimeError(f"Microsoft Graph: Failed to fetch group membership: {response.text}")
            
    except Exception as e:
        logger.error("Microsoft Graph Audit: API Error - Operation: get_group_membership, Exception: %s", e)
        try:
            GRAPH_FAILURES_TOTAL.labels(operation="get_group_membership", error_type=type(e).__name__).inc()
        except Exception:
            pass
        raise e

def check_vpn_group(client, user_id: str) -> dict:
    from app.core.metrics import GRAPH_REQUESTS_TOTAL, GRAPH_FAILURES_TOTAL, GRAPH_LATENCY_SECONDS
    # Use members query or list user's groups to find VPN Users
    start_time = time.time()
    try:
        try:
            GRAPH_REQUESTS_TOTAL.labels(operation="check_vpn_group").inc()
        except Exception:
            pass
            
        logger.info("Microsoft Graph API: Checking VPN group membership for user %s", user_id)
        from .users import get_user_groups
        groups = get_user_groups(client, user_id)
        is_member = any(g.get("displayName") == "VPN Users" for g in groups)
        latency = time.time() - start_time
        
        try:
            GRAPH_LATENCY_SECONDS.labels(operation="check_vpn_group").observe(latency)
        except Exception:
            pass
            
        return {
            "user_id": user_id,
            "group_name": "VPN Users",
            "is_member": is_member
        }
    except Exception as e:
        logger.error("Microsoft Graph Audit: API Error - Operation: check_vpn_group, Exception: %s", e)
        try:
            GRAPH_FAILURES_TOTAL.labels(operation="check_vpn_group", error_type=type(e).__name__).inc()
        except Exception:
            pass
        raise e

def check_security_group(client, user_id: str, group_name: str) -> dict:
    from app.core.metrics import GRAPH_REQUESTS_TOTAL, GRAPH_FAILURES_TOTAL, GRAPH_LATENCY_SECONDS
    start_time = time.time()
    try:
        try:
            GRAPH_REQUESTS_TOTAL.labels(operation="check_security_group").inc()
        except Exception:
            pass
            
        logger.info("Microsoft Graph API: Checking security group '%s' for user %s", group_name, user_id)
        from .users import get_user_groups
        groups = get_user_groups(client, user_id)
        is_member = any(g.get("displayName") == group_name or g.get("id") == group_name for g in groups)
        latency = time.time() - start_time
        
        try:
            GRAPH_LATENCY_SECONDS.labels(operation="check_security_group").observe(latency)
        except Exception:
            pass
            
        return {
            "user_id": user_id,
            "group_name": group_name,
            "is_member": is_member
        }
    except Exception as e:
        logger.error("Microsoft Graph Audit: API Error - Operation: check_security_group, Exception: %s", e)
        try:
            GRAPH_FAILURES_TOTAL.labels(operation="check_security_group", error_type=type(e).__name__).inc()
        except Exception:
            pass
        raise e

def get_all_groups(client) -> list:
    from app.core.metrics import GRAPH_REQUESTS_TOTAL, GRAPH_FAILURES_TOTAL, GRAPH_LATENCY_SECONDS
    url = "https://graph.microsoft.com/v1.0/groups"
    start_time = time.time()
    try:
        try:
            GRAPH_REQUESTS_TOTAL.labels(operation="get_all_groups").inc()
        except Exception:
            pass
            
        logger.info("Microsoft Graph API: Fetching all groups")
        response = client._request("GET", url)
        latency = time.time() - start_time
        
        try:
            GRAPH_LATENCY_SECONDS.labels(operation="get_all_groups").observe(latency)
        except Exception:
            pass
            
        if response.status_code == 200:
            return response.json().get("value", [])
        else:
            try:
                GRAPH_FAILURES_TOTAL.labels(operation="get_all_groups", error_type=str(response.status_code)).inc()
            except Exception:
                pass
            logger.error("Microsoft Graph Audit: API Error - Operation: get_all_groups, Status: %d, Response: %s", response.status_code, response.text)
            raise RuntimeError(f"Microsoft Graph: Failed to fetch groups: {response.text}")
    except Exception as e:
        logger.error("Microsoft Graph Audit: API Error - Operation: get_all_groups, Exception: %s", e)
        try:
            GRAPH_FAILURES_TOTAL.labels(operation="get_all_groups", error_type=type(e).__name__).inc()
        except Exception:
            pass
        raise e
