import logging
from app.tools import (
    # VPN tools
    check_vpn_connection_status,
    restart_vpn_client,
    get_vpn_client_version,
    check_vpn_gateway,
    check_user_vpn_access,
    check_vpn_health,
    # Software tools
    check_admin_privileges,
    check_software_installed,
    install_software,
    check_software_availability,
    check_installation_permissions,
    # Outlook tools
    check_email_sync_status,
    repair_outlook_profile,
    clear_outlook_cache,
    check_mailbox_status,
    check_exchange_connectivity,
    # Printer tools
    check_printer_status,
    restart_print_spooler,
    clear_print_queue,
    # System / Network tools
    check_internet_connection,
    restart_system,
    get_system_info,
    check_network_status,
    check_wifi_connectivity
)

logger = logging.getLogger("it-agent-backend")

def execute_tools(category: str, user_message: str) -> dict:
    """
    Executes relevant tools based on category and returns a structured dictionary of results.
    """
    category_upper = category.upper().strip()
    msg_lower = user_message.lower()
    
    logger.info("Tool Agent: Running execute_tools for category: %s", category_upper)
    
    if category_upper == "VPN":
        # Mock username checking based on query or default
        username = "employee_username"
        # FIX #1: Expanded trigger list — "reset" and "restore" are VPN access-restoration
        # requests and must simulate a disabled account so the approval flow is exercised.
        vpn_restore_keywords = [
            "disabled", "disable", "inactive",
            "reset", "restore", "vpn access", "vpn reset",
        ]
        if any(kw in msg_lower for kw in vpn_restore_keywords):
            username = "disabled_user"
        logger.info("DEBUG MESSAGE=%s", user_message)
        logger.info("Tool Agent: VPN username resolved to '%s'", username)

        gateway_res = check_vpn_gateway()
        access_res = check_user_vpn_access(username)
        health_res = check_vpn_health()

        user_access = access_res.get("vpn_access")
        logger.info("DEBUG USER_ACCESS=%s", user_access)

        return {
            "tool_name": "vpn_tools",
            "status": "SUCCESS",
            "data": {
                "vpn_gateway": gateway_res.get("vpn_gateway"),
                "user_access": user_access,
                "latency_ms": health_res.get("latency_ms"),
                "status": health_res.get("status")
            }
        }
        
    elif category_upper == "NETWORK":
        net_res = check_network_status()
        wifi_res = check_wifi_connectivity()
        
        return {
            "tool_name": "network_tools",
            "status": "SUCCESS",
            "data": {
                "network_status": net_res.get("network_status"),
                "packet_loss": net_res.get("packet_loss"),
                "wifi_status": wifi_res.get("wifi_status"),
                "ssid": wifi_res.get("ssid")
            }
        }
        
    elif category_upper == "OUTLOOK":
        mailbox_res = check_mailbox_status()
        exchange_res = check_exchange_connectivity()
        
        return {
            "tool_name": "outlook_tools",
            "status": "SUCCESS",
            "data": {
                "mailbox_status": mailbox_res.get("mailbox_status"),
                "exchange_server": exchange_res.get("exchange_server"),
                "exchange_latency": exchange_res.get("latency_ms")
            }
        }
        
    elif category_upper == "SOFTWARE_INSTALLATION":
        # Extract software name from the message (e.g. Chrome, Firefox)
        software_name = "Chrome"
        for word in user_message.split():
            clean_word = word.replace('"', '').replace("'", "").strip()
            if clean_word.lower() in ["chrome", "firefox", "outlook", "sap", "vpn", "zoom", "teams"]:
                software_name = clean_word
                break
                
        avail_res = check_software_availability(software_name)
        perm_res = check_installation_permissions()
        
        return {
            "tool_name": "software_tools",
            "status": "SUCCESS",
            "data": {
                "software": avail_res.get("software"),
                "approved": avail_res.get("approved"),
                "permissions": "ALLOWED" if perm_res.get("has_permission") else "DENIED"
            }
        }
        
    else:
        # Default fallback: system info
        sys_res = get_system_info()
        return {
            "tool_name": "system_tools",
            "status": "SUCCESS",
            "data": {
                "system_info": sys_res.get("os"),
                "hostname": sys_res.get("hostname"),
                "ip_address": sys_res.get("ip_address")
            }
        }

def execute_tools_for_category(category: str, user_message: str) -> dict:
    """
    Wrapper for backward compatibility.
    """
    return execute_tools(category, user_message)
