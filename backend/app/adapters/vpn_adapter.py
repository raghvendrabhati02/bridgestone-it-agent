import logging
from app.adapters.base_adapter import BaseAdapter

logger = logging.getLogger("it-agent-backend")

class VPNAdapter(BaseAdapter):
    def __init__(self):
        self.connected_state = False

    def connect(self) -> bool:
        logger.info("VPNAdapter: Connected successfully")
        self.connected_state = True
        return True

    def health_check(self) -> bool:
        logger.info("VPNAdapter: Health check OK")
        return True

    def execute(self, action: str, **kwargs) -> any:
        logger.info("VPNAdapter: Executing action '%s'", action)
        if action == "check_gateway_status":
            return self.check_gateway_status()
        elif action == "check_user_vpn_access":
            return self.check_user_vpn_access(username=kwargs.get("username"))
        elif action == "create_access_restoration_request":
            return self.create_access_restoration_request(username=kwargs.get("username"))
        raise NotImplementedError(f"Action '{action}' not supported by VPNAdapter")

    def disconnect(self) -> bool:
        logger.info("VPNAdapter: Disconnected successfully")
        self.connected_state = False
        return True

    def check_gateway_status(self) -> dict:
        return {
            "vpn_gateway": "ONLINE",
            "gateway_ip": "172.16.254.1",
            "load_factor": "45%",
            "latency_ms": 18,
            "status": "HEALTHY"
        }

    def check_user_vpn_access(self, username: str) -> dict:
        has_access = "disabled" not in username.lower()
        return {
            "username": username,
            "vpn_access": "ACTIVE" if has_access else "DISABLED"
        }

    def create_access_restoration_request(self, username: str) -> dict:
        return {
            "username": username,
            "success": True,
            "message": "Restoration request submitted."
        }
