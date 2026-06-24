import logging
import time

logger = logging.getLogger("it-agent-backend")

def get_assigned_licenses(client, user_id: str) -> list:
    from app.core.metrics import GRAPH_REQUESTS_TOTAL, GRAPH_FAILURES_TOTAL, GRAPH_LATENCY_SECONDS
    url = f"https://graph.microsoft.com/v1.0/users/{user_id}?$select=assignedLicenses"
    start_time = time.time()
    try:
        try:
            GRAPH_REQUESTS_TOTAL.labels(operation="get_assigned_licenses").inc()
        except Exception:
            pass
            
        logger.info("Microsoft Graph API: Fetching assigned licenses for %s", user_id)
        response = client._request("GET", url)
        latency = time.time() - start_time
        
        try:
            GRAPH_LATENCY_SECONDS.labels(operation="get_assigned_licenses").observe(latency)
        except Exception:
            pass
            
        if response.status_code == 200:
            return response.json().get("assignedLicenses", [])
        else:
            try:
                GRAPH_FAILURES_TOTAL.labels(operation="get_assigned_licenses", error_type=str(response.status_code)).inc()
            except Exception:
                pass
            logger.error("Microsoft Graph Audit: API Error - Operation: get_assigned_licenses, Status: %d, Response: %s", response.status_code, response.text)
            raise RuntimeError(f"Microsoft Graph: Failed to fetch user licenses: {response.text}")
            
    except Exception as e:
        logger.error("Microsoft Graph Audit: API Error - Operation: get_assigned_licenses, Exception: %s", e)
        try:
            GRAPH_FAILURES_TOTAL.labels(operation="get_assigned_licenses", error_type=type(e).__name__).inc()
        except Exception:
            pass
        raise e

def check_office_license(client, user_id: str) -> dict:
    from app.core.metrics import GRAPH_REQUESTS_TOTAL, GRAPH_FAILURES_TOTAL, GRAPH_LATENCY_SECONDS, GRAPH_LICENSE_CHECKS_TOTAL
    start_time = time.time()
    try:
        try:
            GRAPH_REQUESTS_TOTAL.labels(operation="check_office_license").inc()
            GRAPH_LICENSE_CHECKS_TOTAL.inc()
        except Exception:
            pass
            
        logger.info("Microsoft Graph API: Verifying Office license status for %s", user_id)
        licenses = get_assigned_licenses(client, user_id)
        # Search for common E3/E5 SKU ids or skuPartNumber mocks
        # In real client, we might need to map skuId to displayName.
        # Standard SKU IDs:
        # SPE_E5 (Microsoft 365 E5) = 06371584-c816-4af5-bc91-ae0e2d6349c2
        # ENTERPRISEPACK (Office 365 E3) = c7ad517e-7c09-42b0-844d-d18309f68590
        # SPE_E3 (Microsoft 365 E3) = 18181a46-0d4e-45cd-891e-60aabd171b4e
        office_skus = {
            "06371584-c816-4af5-bc91-ae0e2d6349c2": "Microsoft 365 E5",
            "c7ad517e-7c09-42b0-844d-d18309f68590": "Office 365 E3",
            "18181a46-0d4e-45cd-891e-60aabd171b4e": "Microsoft 365 E3"
        }
        
        has_license = False
        license_name = "None"
        for lic in licenses:
            sku_id = lic.get("skuId")
            if sku_id in office_skus:
                has_license = True
                license_name = office_skus[sku_id]
                break
                
        latency = time.time() - start_time
        try:
            GRAPH_LATENCY_SECONDS.labels(operation="check_office_license").observe(latency)
        except Exception:
            pass
            
        return {
            "license": license_name,
            "status": "ASSIGNED" if has_license else "UNASSIGNED"
        }
    except Exception as e:
        logger.error("Microsoft Graph Audit: API Error - Operation: check_office_license, Exception: %s", e)
        try:
            GRAPH_FAILURES_TOTAL.labels(operation="check_office_license", error_type=type(e).__name__).inc()
        except Exception:
            pass
        raise e

def check_exchange_license(client, user_id: str) -> dict:
    from app.core.metrics import GRAPH_REQUESTS_TOTAL, GRAPH_FAILURES_TOTAL, GRAPH_LATENCY_SECONDS, GRAPH_LICENSE_CHECKS_TOTAL
    start_time = time.time()
    try:
        try:
            GRAPH_REQUESTS_TOTAL.labels(operation="check_exchange_license").inc()
            GRAPH_LICENSE_CHECKS_TOTAL.inc()
        except Exception:
            pass
            
        logger.info("Microsoft Graph API: Verifying Exchange license status for %s", user_id)
        licenses = get_assigned_licenses(client, user_id)
        
        # Check standard exchange license IDs
        exchange_skus = {
            "06371584-c816-4af5-bc91-ae0e2d6349c2": "Microsoft 365 E5 (includes Exchange)",
            "c7ad517e-7c09-42b0-844d-d18309f68590": "Office 365 E3 (includes Exchange)",
            "18181a46-0d4e-45cd-891e-60aabd171b4e": "Microsoft 365 E3 (includes Exchange)",
            "4b581e5b-2476-47ef-aeaa-a735c053359d": "Exchange Online Plan 2",
            "90f23f67-d9e4-475f-afbe-6e47d100db50": "Exchange Online Plan 1"
        }
        
        has_license = False
        license_name = "None"
        for lic in licenses:
            sku_id = lic.get("skuId")
            if sku_id in exchange_skus:
                has_license = True
                license_name = exchange_skus[sku_id]
                break
                
        latency = time.time() - start_time
        try:
            GRAPH_LATENCY_SECONDS.labels(operation="check_exchange_license").observe(latency)
        except Exception:
            pass
            
        return {
            "license": license_name,
            "status": "ASSIGNED" if has_license else "UNASSIGNED"
        }
    except Exception as e:
        logger.error("Microsoft Graph Audit: API Error - Operation: check_exchange_license, Exception: %s", e)
        try:
            GRAPH_FAILURES_TOTAL.labels(operation="check_exchange_license", error_type=type(e).__name__).inc()
        except Exception:
            pass
        raise e
