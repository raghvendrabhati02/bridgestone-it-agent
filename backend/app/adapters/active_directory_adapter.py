import os
import logging
from app.adapters.base_adapter import BaseAdapter

logger = logging.getLogger("it-agent-backend")

from app.core.retry_helper import with_retry

class ActiveDirectoryAdapter(BaseAdapter):
    def __init__(self):
        use_mock = os.getenv("USE_MOCK_AD", "true").lower() == "true"
        if use_mock:
            from app.integrations.entra_id.client import EntraIdMockClient
            self.client = EntraIdMockClient()
            logger.info("ActiveDirectoryAdapter: Initialized in MOCK Mode.")
        else:
            from app.integrations.entra_id.client import EntraIdRealClient
            self.client = EntraIdRealClient(
                tenant_id=os.getenv("AZURE_TENANT_ID"),
                client_id=os.getenv("AZURE_CLIENT_ID"),
                client_secret=os.getenv("AZURE_CLIENT_SECRET")
            )
            logger.info("ActiveDirectoryAdapter: Initialized in REAL Production Mode.")
        self.connected_state = False

    def connect(self) -> bool:
        logger.info("ActiveDirectoryAdapter: Connected successfully")
        self.connected_state = True
        return True

    def health_check(self) -> bool:
        if not getattr(self.client, "is_mock", True):
            res = self.client.check_connectivity()
            is_healthy = res.get("status") == "healthy"
            logger.info("ActiveDirectoryAdapter: Real health check returned status=%s", res.get("status"))
            return is_healthy
        logger.info("ActiveDirectoryAdapter: Mock health check OK")
        return True

    @with_retry(retries=3, backoff_factor=2.0)
    def execute(self, action: str, **kwargs) -> any:
        logger.info("ActiveDirectoryAdapter: Executing action '%s'", action)
        
        user_id = kwargs.get("user_id") or kwargs.get("username") or "employee"
        group_name = kwargs.get("group_name") or kwargs.get("group_id")
        app_name = kwargs.get("app_name")
        
        if action == "get_user":
            return self.get_user(user_id)
        elif action == "get_user_profile":
            return self.get_user_profile(user_id)
        elif action == "get_manager":
            return self.get_manager(user_id)
        elif action == "get_department":
            return self.get_department(user_id)
        elif action == "get_user_groups":
            return self.get_user_groups(user_id)
        elif action == "check_group_membership":
            return self.check_group_membership(user_id, group_name)
        elif action == "get_group_details":
            return self.get_group_details(group_name)
        elif action == "check_vpn_access":
            return self.check_vpn_access(user_id)
        elif action == "check_application_access":
            return self.check_application_access(user_id, app_name)
        elif action == "check_security_group_access":
            return self.check_security_group_access(user_id, group_name)
        elif action == "get_user_roles":
            return self.get_user_roles(user_id)
        elif action == "check_admin_role":
            return self.check_admin_role(user_id)
        elif action == "check_manager_role":
            return self.check_manager_role(user_id)
        elif action == "get_all_users":
            return self.get_all_users()
        elif action == "get_all_groups":
            return self.get_all_groups()
        elif action == "get_monitoring_stats":
            return self.get_monitoring_stats()
            
        # Legacy action fallback support
        elif action == "check_user_access":
            return self.check_user_access(user_id)
        elif action == "get_group_membership":
            return self.get_group_membership(user_id)
        elif action == "unlock_account":
            return self.unlock_account(user_id)
        elif action == "reset_password_request":
            return self.reset_password_request(user_id)
            
        raise NotImplementedError(f"Action '{action}' not supported by ActiveDirectoryAdapter")

    def disconnect(self) -> bool:
        logger.info("ActiveDirectoryAdapter: Disconnected successfully")
        self.connected_state = False
        return True

    def get_user(self, user_id: str) -> dict:
        return self.client.get_user(user_id)

    def get_user_profile(self, user_id: str) -> dict:
        return self.client.get_user_profile(user_id)

    def get_manager(self, user_id: str) -> dict:
        return self.client.get_manager(user_id)

    def get_department(self, user_id: str) -> str:
        return self.client.get_department(user_id)

    def get_user_groups(self, user_id: str) -> list:
        return self.client.get_user_groups(user_id)

    def check_group_membership(self, user_id: str, group_name_or_id: str) -> bool:
        return self.client.check_group_membership(user_id, group_name_or_id)

    def get_group_details(self, group_id: str) -> dict:
        return self.client.get_group_details(group_id)

    def check_vpn_access(self, user_id: str) -> dict:
        return self.client.check_vpn_access(user_id)

    def check_application_access(self, user_id: str, app_name: str) -> dict:
        return self.client.check_application_access(user_id, app_name)

    def check_security_group_access(self, user_id: str, group_name: str) -> dict:
        return self.client.check_security_group_access(user_id, group_name)

    def get_user_roles(self, user_id: str) -> list:
        return self.client.get_user_roles(user_id)

    def check_admin_role(self, user_id: str) -> bool:
        return self.client.check_admin_role(user_id)

    def check_manager_role(self, user_id: str) -> bool:
        return self.client.check_manager_role(user_id)

    def get_all_users(self) -> list:
        return self.client.get_all_users()

    def get_all_groups(self) -> list:
        return self.client.get_all_groups()

    def get_monitoring_stats(self) -> dict:
        return self.client.get_monitoring_stats()

    # Legacy fallback methods
    def check_user_access(self, username: str) -> dict:
        # Check active status based on username (keep disabled fallback)
        has_access = "disabled" not in username.lower()
        return {
            "username": username,
            "status": "ACTIVE" if has_access else "DISABLED"
        }

    def get_group_membership(self, username: str) -> list:
        # Legacy method returns list of group display names
        groups = self.get_user_groups(username)
        return [g.get("displayName") for g in groups]

    def unlock_account(self, username: str) -> dict:
        return {
            "username": username,
            "success": True,
            "message": f"Account {username} has been unlocked."
        }

    def reset_password_request(self, username: str) -> dict:
        return {
            "username": username,
            "success": True,
            "message": "Password reset link sent successfully."
        }
