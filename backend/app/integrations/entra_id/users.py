import logging
import time

logger = logging.getLogger("it-agent-backend")

def get_user(client, user_id: str) -> dict:
    from app.core.metrics import AD_REQUESTS_TOTAL, AD_FAILURES_TOTAL, AD_LATENCY_SECONDS
    url = f"https://graph.microsoft.com/v1.0/users/{user_id}"
    start_time = time.time()
    try:
        try:
            AD_REQUESTS_TOTAL.labels(operation="get_user").inc()
        except Exception:
            pass
            
        logger.info("Entra ID API: Fetching user %s", user_id)
        response = client._request("GET", url)
        latency = time.time() - start_time
        
        try:
            AD_LATENCY_SECONDS.labels(operation="get_user").observe(latency)
        except Exception:
            pass
            
        if response.status_code == 200:
            return response.json()
        else:
            try:
                AD_FAILURES_TOTAL.labels(operation="get_user", error_type=str(response.status_code)).inc()
            except Exception:
                pass
            logger.error("Entra ID Audit: API Error - Operation: get_user, Status: %d, Response: %s", response.status_code, response.text)
            raise KeyError(f"Entra ID: User {user_id} not found.")
            
    except Exception as e:
        logger.error("Entra ID Audit: API Error - Operation: get_user, Exception: %s", e)
        try:
            AD_FAILURES_TOTAL.labels(operation="get_user", error_type=type(e).__name__).inc()
        except Exception:
            pass
        raise e

def get_user_profile(client, user_id: str) -> dict:
    from app.core.metrics import AD_REQUESTS_TOTAL, AD_FAILURES_TOTAL, AD_LATENCY_SECONDS
    url = f"https://graph.microsoft.com/v1.0/users/{user_id}"
    start_time = time.time()
    try:
        try:
            AD_REQUESTS_TOTAL.labels(operation="get_user_profile").inc()
        except Exception:
            pass
            
        logger.info("Entra ID API: Fetching user profile of %s", user_id)
        response = client._request("GET", url)
        latency = time.time() - start_time
        
        try:
            AD_LATENCY_SECONDS.labels(operation="get_user_profile").observe(latency)
        except Exception:
            pass
            
        if response.status_code == 200:
            return response.json()
        else:
            try:
                AD_FAILURES_TOTAL.labels(operation="get_user_profile", error_type=str(response.status_code)).inc()
            except Exception:
                pass
            logger.error("Entra ID Audit: API Error - Operation: get_user_profile, Status: %d, Response: %s", response.status_code, response.text)
            raise KeyError(f"Entra ID: Profile for user {user_id} not found.")
            
    except Exception as e:
        logger.error("Entra ID Audit: API Error - Operation: get_user_profile, Exception: %s", e)
        try:
            AD_FAILURES_TOTAL.labels(operation="get_user_profile", error_type=type(e).__name__).inc()
        except Exception:
            pass
        raise e

def get_manager(client, user_id: str) -> dict:
    from app.core.metrics import AD_REQUESTS_TOTAL, AD_FAILURES_TOTAL, AD_LATENCY_SECONDS
    url = f"https://graph.microsoft.com/v1.0/users/{user_id}/manager"
    start_time = time.time()
    try:
        try:
            AD_REQUESTS_TOTAL.labels(operation="get_manager").inc()
        except Exception:
            pass
            
        logger.info("Entra ID API: Fetching manager of %s", user_id)
        response = client._request("GET", url)
        latency = time.time() - start_time
        
        try:
            AD_LATENCY_SECONDS.labels(operation="get_manager").observe(latency)
        except Exception:
            pass
            
        if response.status_code == 200:
            return response.json()
        else:
            try:
                AD_FAILURES_TOTAL.labels(operation="get_manager", error_type=str(response.status_code)).inc()
            except Exception:
                pass
            logger.error("Entra ID Audit: API Error - Operation: get_manager, Status: %d, Response: %s", response.status_code, response.text)
            raise KeyError(f"Entra ID: Manager for user {user_id} not found.")
            
    except Exception as e:
        logger.error("Entra ID Audit: API Error - Operation: get_manager, Exception: %s", e)
        try:
            AD_FAILURES_TOTAL.labels(operation="get_manager", error_type=type(e).__name__).inc()
        except Exception:
            pass
        raise e

def get_department(client, user_id: str) -> str:
    from app.core.metrics import AD_REQUESTS_TOTAL, AD_FAILURES_TOTAL, AD_LATENCY_SECONDS
    url = f"https://graph.microsoft.com/v1.0/users/{user_id}?$select=department"
    start_time = time.time()
    try:
        try:
            AD_REQUESTS_TOTAL.labels(operation="get_department").inc()
        except Exception:
            pass
            
        logger.info("Entra ID API: Fetching department of %s", user_id)
        response = client._request("GET", url)
        latency = time.time() - start_time
        
        try:
            AD_LATENCY_SECONDS.labels(operation="get_department").observe(latency)
        except Exception:
            pass
            
        if response.status_code == 200:
            return response.json().get("department", "Unknown")
        else:
            try:
                AD_FAILURES_TOTAL.labels(operation="get_department", error_type=str(response.status_code)).inc()
            except Exception:
                pass
            logger.error("Entra ID Audit: API Error - Operation: get_department, Status: %d, Response: %s", response.status_code, response.text)
            return "Unknown"
            
    except Exception as e:
        logger.error("Entra ID Audit: API Error - Operation: get_department, Exception: %s", e)
        try:
            AD_FAILURES_TOTAL.labels(operation="get_department", error_type=type(e).__name__).inc()
        except Exception:
            pass
        return "Unknown"

def get_all_users(client) -> list:
    from app.core.metrics import AD_REQUESTS_TOTAL, AD_FAILURES_TOTAL, AD_LATENCY_SECONDS
    url = "https://graph.microsoft.com/v1.0/users"
    start_time = time.time()
    try:
        try:
            AD_REQUESTS_TOTAL.labels(operation="get_all_users").inc()
        except Exception:
            pass
            
        logger.info("Entra ID API: Fetching all directory users")
        response = client._request("GET", url)
        latency = time.time() - start_time
        
        try:
            AD_LATENCY_SECONDS.labels(operation="get_all_users").observe(latency)
        except Exception:
            pass
            
        if response.status_code == 200:
            return response.json().get("value", [])
        else:
            try:
                AD_FAILURES_TOTAL.labels(operation="get_all_users", error_type=str(response.status_code)).inc()
            except Exception:
                pass
            logger.error("Entra ID Audit: API Error - Operation: get_all_users, Status: %d, Response: %s", response.status_code, response.text)
            return []
    except Exception as e:
        logger.error("Entra ID Audit: API Error - Operation: get_all_users, Exception: %s", e)
        try:
            AD_FAILURES_TOTAL.labels(operation="get_all_users", error_type=type(e).__name__).inc()
        except Exception:
            pass
        return []
