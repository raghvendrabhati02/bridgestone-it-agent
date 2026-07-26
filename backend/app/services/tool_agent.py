"""
tool_agent.py
──────────────────────────────────────────────────────────────────────────────
Executes IT diagnostic tools by category and returns structured results.

Phase 3 additions
-----------------
  • TOOL_EXECUTION_TOTAL  — counter per tool_name × status (success/failure)
  • TOOL_EXECUTION_DURATION_SECONDS — latency histogram per tool_name
  • Correlation ID propagated in every structured log line
"""

import logging
import time
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


def _get_correlation_id() -> str:
    """Return the current correlation ID from context (or empty string)."""
    try:
        from app.core.logging_context import correlation_id_ctx
        return correlation_id_ctx.get() or ""
    except Exception:
        return ""


def _record_tool_metrics(tool_name: str, status: str, duration: float) -> None:
    """Safely increment Prometheus tool execution metrics."""
    try:
        from app.core.metrics import TOOL_EXECUTION_TOTAL, TOOL_EXECUTION_DURATION_SECONDS
        TOOL_EXECUTION_TOTAL.labels(tool_name=tool_name, status=status).inc()
        TOOL_EXECUTION_DURATION_SECONDS.labels(tool_name=tool_name).observe(duration)
    except Exception as exc:
        logger.warning("[tool_agent] Failed to record metrics for '%s': %s", tool_name, exc)


def execute_tools(category: str, user_message: str) -> dict:
    """
    Executes relevant tools based on category and returns a structured dictionary of results.

    Metrics emitted per call:
      - tool_execution_total{tool_name, status}
      - tool_execution_duration_seconds{tool_name}
    """
    category_upper = category.upper().strip()
    msg_lower = user_message.lower()
    corr_id = _get_correlation_id()

    logger.info(
        "Tool Agent: Running execute_tools | category=%s | correlation_id=%s",
        category_upper, corr_id,
    )

    t0 = time.monotonic()
    tool_name = "unknown_tools"
    status = "success"

    try:
        if category_upper == "VPN":
            tool_name = "vpn_tools"
            username = "employee_username"
            vpn_restore_keywords = [
                "disabled", "disable", "inactive",
                "reset", "restore", "vpn access", "vpn reset",
            ]
            if any(kw in msg_lower for kw in vpn_restore_keywords):
                username = "disabled_user"
            logger.info(
                "Tool Agent: VPN username resolved to '%s' | correlation_id=%s",
                username, corr_id,
            )

            gateway_res = check_vpn_gateway()
            access_res  = check_user_vpn_access(username)
            health_res  = check_vpn_health()
            user_access = access_res.get("vpn_access")

            result = {
                "tool_name": tool_name,
                "status":    "SUCCESS",
                "data": {
                    "vpn_gateway": gateway_res.get("vpn_gateway"),
                    "user_access": user_access,
                    "latency_ms":  health_res.get("latency_ms"),
                    "status":      health_res.get("status"),
                },
            }

        elif category_upper == "NETWORK":
            tool_name = "network_tools"
            net_res  = check_network_status()
            wifi_res = check_wifi_connectivity()

            result = {
                "tool_name": tool_name,
                "status":    "SUCCESS",
                "data": {
                    "network_status": net_res.get("network_status"),
                    "packet_loss":    net_res.get("packet_loss"),
                    "wifi_status":    wifi_res.get("wifi_status"),
                    "ssid":           wifi_res.get("ssid"),
                },
            }

        elif category_upper == "OUTLOOK":
            tool_name    = "outlook_tools"
            mailbox_res  = check_mailbox_status()
            exchange_res = check_exchange_connectivity()

            result = {
                "tool_name": tool_name,
                "status":    "SUCCESS",
                "data": {
                    "mailbox_status":   mailbox_res.get("mailbox_status"),
                    "exchange_server":  exchange_res.get("exchange_server"),
                    "exchange_latency": exchange_res.get("latency_ms"),
                },
            }

        elif category_upper == "SOFTWARE_INSTALLATION":
            tool_name = "software_tools"
            software_name = "Chrome"
            for word in user_message.split():
                clean_word = word.replace('"', "").replace("'", "").strip()
                if clean_word.lower() in ["chrome", "firefox", "outlook", "sap", "vpn", "zoom", "teams"]:
                    software_name = clean_word
                    break

            avail_res = check_software_availability(software_name)
            perm_res  = check_installation_permissions()

            result = {
                "tool_name": tool_name,
                "status":    "SUCCESS",
                "data": {
                    "software":    avail_res.get("software"),
                    "approved":    avail_res.get("approved"),
                    "permissions": "ALLOWED" if perm_res.get("has_permission") else "DENIED",
                },
            }

        else:
            tool_name = "system_tools"
            sys_res = get_system_info()

            result = {
                "tool_name": tool_name,
                "status":    "SUCCESS",
                "data": {
                    "system_info": sys_res.get("os"),
                    "hostname":    sys_res.get("hostname"),
                    "ip_address":  sys_res.get("ip_address"),
                },
            }

    except Exception as exc:
        status = "failure"
        duration = time.monotonic() - t0
        _record_tool_metrics(tool_name, status, duration)
        logger.error(
            "Tool Agent: Tool '%s' raised an exception | correlation_id=%s | error=%s",
            tool_name, corr_id, exc, exc_info=True,
        )
        raise

    duration = time.monotonic() - t0
    _record_tool_metrics(tool_name, status, duration)
    logger.info(
        "Tool Agent: '%s' completed in %.4fs | status=%s | correlation_id=%s",
        tool_name, duration, status, corr_id,
    )
    return result


def execute_tools_for_category(category: str, user_message: str) -> dict:
    """Wrapper for backward compatibility."""
    return execute_tools(category, user_message)
