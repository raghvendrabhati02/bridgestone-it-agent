import os
import logging
from app.adapters.base_adapter import BaseAdapter

logger = logging.getLogger("it-agent-backend")

from app.core.retry_helper import with_retry

class MicrosoftGraphAdapter(BaseAdapter):
    def __init__(self):
        use_mock = os.getenv("USE_MOCK_GRAPH", "true").lower() == "true"
        if use_mock:
            from app.integrations.microsoft_graph.graph_client import MicrosoftGraphMockClient
            self.client = MicrosoftGraphMockClient()
            logger.info("MicrosoftGraphAdapter: Initialized in MOCK Mode.")
        else:
            from app.integrations.microsoft_graph.client import MicrosoftGraphRealClient
            self.client = MicrosoftGraphRealClient(
                tenant_id=os.getenv("AZURE_TENANT_ID"),
                client_id=os.getenv("AZURE_CLIENT_ID"),
                client_secret=os.getenv("AZURE_CLIENT_SECRET")
            )
            logger.info("MicrosoftGraphAdapter: Initialized in REAL Production Mode.")
        self.connected_state = False

    def connect(self) -> bool:
        logger.info("MicrosoftGraphAdapter: Connected successfully")
        self.connected_state = True
        return True

    def health_check(self) -> bool:
        if not getattr(self.client, "is_mock", True):
            res = self.client.check_connectivity()
            is_healthy = res.get("status") == "healthy"
            logger.info("MicrosoftGraphAdapter: Real health check returned status=%s", res.get("status"))
            return is_healthy
        logger.info("MicrosoftGraphAdapter: Mock health check OK")
        return True

    @with_retry(retries=3, backoff_factor=2.0)
    def execute(self, action: str, **kwargs) -> any:
        logger.info("MicrosoftGraphAdapter: Executing action '%s'", action)
        
        user_id = kwargs.get("user_id", "graph-user-12345")
        group_id = kwargs.get("group_id")
        group_name = kwargs.get("group_name")
        
        if action == "get_user":
            return self.get_user(user_id)
        elif action == "get_user_profile":
            return self.get_user_profile(user_id)
        elif action == "get_manager":
            return self.get_manager(user_id)
        elif action == "get_user_groups":
            return self.get_user_groups(user_id)
        elif action == "get_mailbox_status":
            return self.get_mailbox_status(user_id)
        elif action == "get_mailbox_settings":
            return self.get_mailbox_settings(user_id)
        elif action == "check_exchange_connectivity":
            return self.check_exchange_connectivity()
        elif action == "get_assigned_licenses":
            return self.get_assigned_licenses(user_id)
        elif action == "check_office_license":
            return self.check_office_license(user_id)
        elif action == "check_exchange_license":
            return self.check_exchange_license(user_id)
        elif action == "get_group_membership":
            return self.get_group_membership(group_id)
        elif action == "check_vpn_group":
            return self.check_vpn_group(user_id)
        elif action == "check_security_group":
            return self.check_security_group(user_id, group_name)
        elif action == "get_all_users":
            return self.get_all_users()
        elif action == "get_all_groups":
            return self.get_all_groups()
        elif action == "check_license_status":  # backwards compatibility
            return self.check_office_license(user_id)
            
        raise NotImplementedError(f"Action '{action}' not supported by MicrosoftGraphAdapter")

    def disconnect(self) -> bool:
        logger.info("MicrosoftGraphAdapter: Disconnected successfully")
        self.connected_state = False
        return True

    def get_user(self, user_id: str) -> dict:
        return self.client.get_user(user_id)

    def get_user_profile(self, user_id: str = "graph-user-12345") -> dict:
        return self.client.get_user_profile(user_id)

    def get_manager(self, user_id: str) -> dict:
        return self.client.get_manager(user_id)

    def get_user_groups(self, user_id: str = "graph-user-12345") -> list:
        return self.client.get_user_groups(user_id)

    def get_mailbox_status(self, user_id: str = "graph-user-12345") -> dict:
        return self.client.get_mailbox_status(user_id)

    def get_mailbox_settings(self, user_id: str) -> dict:
        return self.client.get_mailbox_settings(user_id)

    def check_exchange_connectivity(self) -> dict:
        return self.client.check_exchange_connectivity()

    def get_assigned_licenses(self, user_id: str) -> list:
        return self.client.get_assigned_licenses(user_id)

    def check_office_license(self, user_id: str) -> dict:
        return self.client.check_office_license(user_id)

    def check_exchange_license(self, user_id: str) -> dict:
        return self.client.check_exchange_license(user_id)

    def get_group_membership(self, group_id: str) -> list:
        return self.client.get_group_membership(group_id)

    def check_vpn_group(self, user_id: str) -> dict:
        return self.client.check_vpn_group(user_id)

    def check_security_group(self, user_id: str, group_name: str) -> dict:
        return self.client.check_security_group(user_id, group_name)

    def get_all_users(self) -> list:
        return self.client.get_all_users()

    def get_all_groups(self) -> list:
        return self.client.get_all_groups()
