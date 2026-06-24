import logging
import time

logger = logging.getLogger("it-agent-backend")

def get_mailbox_status(client, user_id: str) -> dict:
    from app.core.metrics import GRAPH_REQUESTS_TOTAL, GRAPH_FAILURES_TOTAL, GRAPH_LATENCY_SECONDS, GRAPH_MAILBOX_CHECKS_TOTAL
    url = f"https://graph.microsoft.com/v1.0/users/{user_id}/mailboxSettings"
    start_time = time.time()
    try:
        try:
            GRAPH_REQUESTS_TOTAL.labels(operation="get_mailbox_status").inc()
            GRAPH_MAILBOX_CHECKS_TOTAL.inc()
        except Exception:
            pass
            
        logger.info("Microsoft Graph API: Fetching mailbox status for %s", user_id)
        response = client._request("GET", url)
        latency = time.time() - start_time
        
        try:
            GRAPH_LATENCY_SECONDS.labels(operation="get_mailbox_status").observe(latency)
        except Exception:
            pass
            
        if response.status_code == 200:
            return {
                "mailbox_status": "ACTIVE",
                "exchange_server": "ONLINE",
                "exchange_latency": int(latency * 1000)
            }
        else:
            try:
                GRAPH_FAILURES_TOTAL.labels(operation="get_mailbox_status", error_type=str(response.status_code)).inc()
            except Exception:
                pass
            logger.error("Microsoft Graph Audit: API Error - Operation: get_mailbox_status, Status: %d, Response: %s", response.status_code, response.text)
            raise KeyError(f"Microsoft Graph: Mailbox for user {user_id} not found.")
            
    except Exception as e:
        logger.error("Microsoft Graph Audit: API Error - Operation: get_mailbox_status, Exception: %s", e)
        try:
            GRAPH_FAILURES_TOTAL.labels(operation="get_mailbox_status", error_type=type(e).__name__).inc()
        except Exception:
            pass
        raise e

def get_mailbox_settings(client, user_id: str) -> dict:
    from app.core.metrics import GRAPH_REQUESTS_TOTAL, GRAPH_FAILURES_TOTAL, GRAPH_LATENCY_SECONDS
    url = f"https://graph.microsoft.com/v1.0/users/{user_id}/mailboxSettings"
    start_time = time.time()
    try:
        try:
            GRAPH_REQUESTS_TOTAL.labels(operation="get_mailbox_settings").inc()
        except Exception:
            pass
            
        logger.info("Microsoft Graph API: Fetching mailbox settings for %s", user_id)
        response = client._request("GET", url)
        latency = time.time() - start_time
        
        try:
            GRAPH_LATENCY_SECONDS.labels(operation="get_mailbox_settings").observe(latency)
        except Exception:
            pass
            
        if response.status_code == 200:
            return response.json()
        else:
            try:
                GRAPH_FAILURES_TOTAL.labels(operation="get_mailbox_settings", error_type=str(response.status_code)).inc()
            except Exception:
                pass
            logger.error("Microsoft Graph Audit: API Error - Operation: get_mailbox_settings, Status: %d, Response: %s", response.status_code, response.text)
            raise KeyError(f"Microsoft Graph: Mailbox settings for user {user_id} not found.")
            
    except Exception as e:
        logger.error("Microsoft Graph Audit: API Error - Operation: get_mailbox_settings, Exception: %s", e)
        try:
            GRAPH_FAILURES_TOTAL.labels(operation="get_mailbox_settings", error_type=type(e).__name__).inc()
        except Exception:
            pass
        raise e

def check_exchange_connectivity(client) -> dict:
    from app.core.metrics import GRAPH_REQUESTS_TOTAL, GRAPH_FAILURES_TOTAL, GRAPH_LATENCY_SECONDS
    # Check general users query as a health validator
    url = "https://graph.microsoft.com/v1.0/users?$top=1"
    start_time = time.time()
    try:
        try:
            GRAPH_REQUESTS_TOTAL.labels(operation="check_exchange_connectivity").inc()
        except Exception:
            pass
            
        logger.info("Microsoft Graph API: Checking Exchange connectivity")
        response = client._request("GET", url)
        latency = time.time() - start_time
        
        try:
            GRAPH_LATENCY_SECONDS.labels(operation="check_exchange_connectivity").observe(latency)
        except Exception:
            pass
            
        if response.status_code == 200:
            return {
                "exchange_server": "ONLINE",
                "protocol": "MAPI/HTTP",
                "latency_ms": int(latency * 1000)
            }
        else:
            try:
                GRAPH_FAILURES_TOTAL.labels(operation="check_exchange_connectivity", error_type=str(response.status_code)).inc()
            except Exception:
                pass
            return {
                "exchange_server": "OFFLINE",
                "protocol": "MAPI/HTTP",
                "latency_ms": int(latency * 1000)
            }
    except Exception as e:
        logger.error("Microsoft Graph Audit: API Error - Operation: check_exchange_connectivity, Exception: %s", e)
        try:
            GRAPH_FAILURES_TOTAL.labels(operation="check_exchange_connectivity", error_type=type(e).__name__).inc()
        except Exception:
            pass
        return {
            "exchange_server": "OFFLINE",
            "protocol": "MAPI/HTTP",
            "latency_ms": 0
        }
