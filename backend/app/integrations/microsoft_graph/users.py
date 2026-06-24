import logging
import time

logger = logging.getLogger("it-agent-backend")

def get_user(client, user_id: str) -> dict:
    from app.core.metrics import GRAPH_REQUESTS_TOTAL, GRAPH_FAILURES_TOTAL, GRAPH_LATENCY_SECONDS
    url = f"https://graph.microsoft.com/v1.0/users/{user_id}"
    start_time = time.time()
    try:
        try:
            GRAPH_REQUESTS_TOTAL.labels(operation="get_user").inc()
        except Exception:
            pass
            
        logger.info("Microsoft Graph API: Fetching user %s", user_id)
        response = client._request("GET", url)
        latency = time.time() - start_time
        
        try:
            GRAPH_LATENCY_SECONDS.labels(operation="get_user").observe(latency)
        except Exception:
            pass
            
        if response.status_code == 200:
            return response.json()
        else:
            try:
                GRAPH_FAILURES_TOTAL.labels(operation="get_user", error_type=str(response.status_code)).inc()
            except Exception:
                pass
            logger.error("Microsoft Graph Audit: API Error - Operation: get_user, Status: %d, Response: %s", response.status_code, response.text)
            raise KeyError(f"Microsoft Graph: User {user_id} not found.")
            
    except Exception as e:
        logger.error("Microsoft Graph Audit: API Error - Operation: get_user, Exception: %s", e)
        try:
            GRAPH_FAILURES_TOTAL.labels(operation="get_user", error_type=type(e).__name__).inc()
        except Exception:
            pass
        raise e

def get_user_profile(client, user_id: str) -> dict:
    from app.core.metrics import GRAPH_REQUESTS_TOTAL, GRAPH_FAILURES_TOTAL, GRAPH_LATENCY_SECONDS
    url = f"https://graph.microsoft.com/v1.0/users/{user_id}"
    start_time = time.time()
    try:
        try:
            GRAPH_REQUESTS_TOTAL.labels(operation="get_user_profile").inc()
        except Exception:
            pass
            
        logger.info("Microsoft Graph API: Fetching profile of %s", user_id)
        response = client._request("GET", url)
        latency = time.time() - start_time
        
        try:
            GRAPH_LATENCY_SECONDS.labels(operation="get_user_profile").observe(latency)
        except Exception:
            pass
            
        if response.status_code == 200:
            return response.json()
        else:
            try:
                GRAPH_FAILURES_TOTAL.labels(operation="get_user_profile", error_type=str(response.status_code)).inc()
            except Exception:
                pass
            logger.error("Microsoft Graph Audit: API Error - Operation: get_user_profile, Status: %d, Response: %s", response.status_code, response.text)
            raise KeyError(f"Microsoft Graph: Profile for user {user_id} not found.")
            
    except Exception as e:
        logger.error("Microsoft Graph Audit: API Error - Operation: get_user_profile, Exception: %s", e)
        try:
            GRAPH_FAILURES_TOTAL.labels(operation="get_user_profile", error_type=type(e).__name__).inc()
        except Exception:
            pass
        raise e

def get_manager(client, user_id: str) -> dict:
    from app.core.metrics import GRAPH_REQUESTS_TOTAL, GRAPH_FAILURES_TOTAL, GRAPH_LATENCY_SECONDS
    url = f"https://graph.microsoft.com/v1.0/users/{user_id}/manager"
    start_time = time.time()
    try:
        try:
            GRAPH_REQUESTS_TOTAL.labels(operation="get_manager").inc()
        except Exception:
            pass
            
        logger.info("Microsoft Graph API: Fetching manager of %s", user_id)
        response = client._request("GET", url)
        latency = time.time() - start_time
        
        try:
            GRAPH_LATENCY_SECONDS.labels(operation="get_manager").observe(latency)
        except Exception:
            pass
            
        if response.status_code == 200:
            return response.json()
        else:
            try:
                GRAPH_FAILURES_TOTAL.labels(operation="get_manager", error_type=str(response.status_code)).inc()
            except Exception:
                pass
            logger.error("Microsoft Graph Audit: API Error - Operation: get_manager, Status: %d, Response: %s", response.status_code, response.text)
            raise KeyError(f"Microsoft Graph: Manager for user {user_id} not found.")
            
    except Exception as e:
        logger.error("Microsoft Graph Audit: API Error - Operation: get_manager, Exception: %s", e)
        try:
            GRAPH_FAILURES_TOTAL.labels(operation="get_manager", error_type=type(e).__name__).inc()
        except Exception:
            pass
        raise e

def get_user_groups(client, user_id: str) -> list:
    from app.core.metrics import GRAPH_REQUESTS_TOTAL, GRAPH_FAILURES_TOTAL, GRAPH_LATENCY_SECONDS
    url = f"https://graph.microsoft.com/v1.0/users/{user_id}/memberOf"
    start_time = time.time()
    try:
        try:
            GRAPH_REQUESTS_TOTAL.labels(operation="get_user_groups").inc()
        except Exception:
            pass
            
        logger.info("Microsoft Graph API: Fetching member groups of %s", user_id)
        response = client._request("GET", url)
        latency = time.time() - start_time
        
        try:
            GRAPH_LATENCY_SECONDS.labels(operation="get_user_groups").observe(latency)
        except Exception:
            pass
            
        if response.status_code == 200:
            return response.json().get("value", [])
        else:
            try:
                GRAPH_FAILURES_TOTAL.labels(operation="get_user_groups", error_type=str(response.status_code)).inc()
            except Exception:
                pass
            logger.error("Microsoft Graph Audit: API Error - Operation: get_user_groups, Status: %d, Response: %s", response.status_code, response.text)
            raise RuntimeError(f"Microsoft Graph: Failed to fetch user groups: {response.text}")
            
    except Exception as e:
        logger.error("Microsoft Graph Audit: API Error - Operation: get_user_groups, Exception: %s", e)
        try:
            GRAPH_FAILURES_TOTAL.labels(operation="get_user_groups", error_type=type(e).__name__).inc()
        except Exception:
            pass
        raise e

def get_all_users(client) -> list:
    from app.core.metrics import GRAPH_REQUESTS_TOTAL, GRAPH_FAILURES_TOTAL, GRAPH_LATENCY_SECONDS
    url = "https://graph.microsoft.com/v1.0/users"
    start_time = time.time()
    try:
        try:
            GRAPH_REQUESTS_TOTAL.labels(operation="get_all_users").inc()
        except Exception:
            pass
            
        logger.info("Microsoft Graph API: Fetching all users")
        response = client._request("GET", url)
        latency = time.time() - start_time
        
        try:
            GRAPH_LATENCY_SECONDS.labels(operation="get_all_users").observe(latency)
        except Exception:
            pass
            
        if response.status_code == 200:
            return response.json().get("value", [])
        else:
            try:
                GRAPH_FAILURES_TOTAL.labels(operation="get_all_users", error_type=str(response.status_code)).inc()
            except Exception:
                pass
            logger.error("Microsoft Graph Audit: API Error - Operation: get_all_users, Status: %d, Response: %s", response.status_code, response.text)
            raise RuntimeError(f"Microsoft Graph: Failed to fetch users: {response.text}")
    except Exception as e:
        logger.error("Microsoft Graph Audit: API Error - Operation: get_all_users, Exception: %s", e)
        try:
            GRAPH_FAILURES_TOTAL.labels(operation="get_all_users", error_type=type(e).__name__).inc()
        except Exception:
            pass
        raise e
