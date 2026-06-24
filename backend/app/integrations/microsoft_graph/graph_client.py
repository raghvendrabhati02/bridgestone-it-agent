from abc import ABC, abstractmethod
import logging
import time
from .graph_mock import microsoft_graph_mock_db

logger = logging.getLogger("it-agent-backend")

class MicrosoftGraphClientInterface(ABC):
    @abstractmethod
    def get_user(self, user_id: str) -> dict:
        pass

    @abstractmethod
    def get_user_profile(self, user_id: str) -> dict:
        pass

    @abstractmethod
    def get_manager(self, user_id: str) -> dict:
        pass

    @abstractmethod
    def get_user_groups(self, user_id: str) -> list:
        pass

    @abstractmethod
    def get_mailbox_status(self, user_id: str) -> dict:
        pass

    @abstractmethod
    def get_mailbox_settings(self, user_id: str) -> dict:
        pass

    @abstractmethod
    def check_exchange_connectivity(self) -> dict:
        pass

    @abstractmethod
    def get_assigned_licenses(self, user_id: str) -> list:
        pass

    @abstractmethod
    def check_office_license(self, user_id: str) -> dict:
        pass

    @abstractmethod
    def check_exchange_license(self, user_id: str) -> dict:
        pass

    @abstractmethod
    def get_group_membership(self, group_id: str) -> list:
        pass

    @abstractmethod
    def check_vpn_group(self, user_id: str) -> dict:
        pass

    @abstractmethod
    def check_security_group(self, user_id: str, group_name: str) -> dict:
        pass

    @abstractmethod
    def get_all_users(self) -> list:
        pass

    @abstractmethod
    def get_all_groups(self) -> list:
        pass

    @abstractmethod
    def check_connectivity(self) -> dict:
        pass


class MicrosoftGraphMockClient(MicrosoftGraphClientInterface):
    is_mock = True

    def __init__(self):
        self.db = microsoft_graph_mock_db

    def get_user(self, user_id: str) -> dict:
        from app.core.metrics import GRAPH_REQUESTS_TOTAL, GRAPH_LATENCY_SECONDS
        start = time.time()
        try:
            GRAPH_REQUESTS_TOTAL.labels(operation="get_user").inc()
        except Exception:
            pass
        logger.info("MicrosoftGraphMockClient: Fetching user %s", user_id)
        res = self.db.get_user(user_id)
        if not res:
            from app.core.metrics import GRAPH_FAILURES_TOTAL
            try:
                GRAPH_FAILURES_TOTAL.labels(operation="get_user", error_type="KeyError").inc()
            except Exception:
                pass
            raise KeyError(f"User {user_id} not found.")
        try:
            GRAPH_LATENCY_SECONDS.labels(operation="get_user").observe(time.time() - start)
        except Exception:
            pass
        return res

    def get_user_profile(self, user_id: str) -> dict:
        from app.core.metrics import GRAPH_REQUESTS_TOTAL, GRAPH_LATENCY_SECONDS
        start = time.time()
        try:
            GRAPH_REQUESTS_TOTAL.labels(operation="get_user_profile").inc()
        except Exception:
            pass
        logger.info("MicrosoftGraphMockClient: Fetching user profile %s", user_id)
        res = self.db.get_user_profile(user_id)
        if not res:
            from app.core.metrics import GRAPH_FAILURES_TOTAL
            try:
                GRAPH_FAILURES_TOTAL.labels(operation="get_user_profile", error_type="KeyError").inc()
            except Exception:
                pass
            raise KeyError(f"User {user_id} not found.")
        try:
            GRAPH_LATENCY_SECONDS.labels(operation="get_user_profile").observe(time.time() - start)
        except Exception:
            pass
        return res

    def get_manager(self, user_id: str) -> dict:
        from app.core.metrics import GRAPH_REQUESTS_TOTAL, GRAPH_LATENCY_SECONDS
        start = time.time()
        try:
            GRAPH_REQUESTS_TOTAL.labels(operation="get_manager").inc()
        except Exception:
            pass
        logger.info("MicrosoftGraphMockClient: Fetching manager of %s", user_id)
        res = self.db.get_manager(user_id)
        if not res:
            from app.core.metrics import GRAPH_FAILURES_TOTAL
            try:
                GRAPH_FAILURES_TOTAL.labels(operation="get_manager", error_type="KeyError").inc()
            except Exception:
                pass
            raise KeyError(f"Manager for {user_id} not found.")
        try:
            GRAPH_LATENCY_SECONDS.labels(operation="get_manager").observe(time.time() - start)
        except Exception:
            pass
        return res

    def get_user_groups(self, user_id: str) -> list:
        from app.core.metrics import GRAPH_REQUESTS_TOTAL, GRAPH_LATENCY_SECONDS
        start = time.time()
        try:
            GRAPH_REQUESTS_TOTAL.labels(operation="get_user_groups").inc()
        except Exception:
            pass
        logger.info("MicrosoftGraphMockClient: Fetching groups of user %s", user_id)
        res = self.db.get_user_groups(user_id)
        try:
            GRAPH_LATENCY_SECONDS.labels(operation="get_user_groups").observe(time.time() - start)
        except Exception:
            pass
        return res

    def get_mailbox_status(self, user_id: str) -> dict:
        from app.core.metrics import GRAPH_REQUESTS_TOTAL, GRAPH_LATENCY_SECONDS, GRAPH_MAILBOX_CHECKS_TOTAL
        start = time.time()
        try:
            GRAPH_REQUESTS_TOTAL.labels(operation="get_mailbox_status").inc()
            GRAPH_MAILBOX_CHECKS_TOTAL.inc()
        except Exception:
            pass
        logger.info("MicrosoftGraphMockClient: Fetching mailbox status for %s", user_id)
        res = self.db.get_mailbox_status(user_id)
        if not res:
            from app.core.metrics import GRAPH_FAILURES_TOTAL
            try:
                GRAPH_FAILURES_TOTAL.labels(operation="get_mailbox_status", error_type="KeyError").inc()
            except Exception:
                pass
            raise KeyError(f"Mailbox for user {user_id} not found.")
        try:
            GRAPH_LATENCY_SECONDS.labels(operation="get_mailbox_status").observe(time.time() - start)
        except Exception:
            pass
        return res

    def get_mailbox_settings(self, user_id: str) -> dict:
        from app.core.metrics import GRAPH_REQUESTS_TOTAL, GRAPH_LATENCY_SECONDS
        start = time.time()
        try:
            GRAPH_REQUESTS_TOTAL.labels(operation="get_mailbox_settings").inc()
        except Exception:
            pass
        logger.info("MicrosoftGraphMockClient: Fetching mailbox settings for %s", user_id)
        res = self.db.get_mailbox_settings(user_id)
        if res is None:
            from app.core.metrics import GRAPH_FAILURES_TOTAL
            try:
                GRAPH_FAILURES_TOTAL.labels(operation="get_mailbox_settings", error_type="KeyError").inc()
            except Exception:
                pass
            raise KeyError(f"Mailbox settings for user {user_id} not found.")
        try:
            GRAPH_LATENCY_SECONDS.labels(operation="get_mailbox_settings").observe(time.time() - start)
        except Exception:
            pass
        return res

    def check_exchange_connectivity(self) -> dict:
        from app.core.metrics import GRAPH_REQUESTS_TOTAL, GRAPH_LATENCY_SECONDS
        start = time.time()
        try:
            GRAPH_REQUESTS_TOTAL.labels(operation="check_exchange_connectivity").inc()
        except Exception:
            pass
        logger.info("MicrosoftGraphMockClient: Checking Exchange connectivity")
        try:
            GRAPH_LATENCY_SECONDS.labels(operation="check_exchange_connectivity").observe(time.time() - start)
        except Exception:
            pass
        return {
            "exchange_server": "ONLINE",
            "protocol": "MAPI/HTTP",
            "latency_ms": 20
        }

    def get_assigned_licenses(self, user_id: str) -> list:
        from app.core.metrics import GRAPH_REQUESTS_TOTAL, GRAPH_LATENCY_SECONDS
        start = time.time()
        try:
            GRAPH_REQUESTS_TOTAL.labels(operation="get_assigned_licenses").inc()
        except Exception:
            pass
        logger.info("MicrosoftGraphMockClient: Fetching licenses for %s", user_id)
        res = self.db.get_assigned_licenses(user_id)
        try:
            GRAPH_LATENCY_SECONDS.labels(operation="get_assigned_licenses").observe(time.time() - start)
        except Exception:
            pass
        return res

    def check_office_license(self, user_id: str) -> dict:
        from app.core.metrics import GRAPH_REQUESTS_TOTAL, GRAPH_LATENCY_SECONDS, GRAPH_LICENSE_CHECKS_TOTAL
        start = time.time()
        try:
            GRAPH_REQUESTS_TOTAL.labels(operation="check_office_license").inc()
            GRAPH_LICENSE_CHECKS_TOTAL.inc()
        except Exception:
            pass
        logger.info("MicrosoftGraphMockClient: Checking Office license for %s", user_id)
        licenses = self.db.get_assigned_licenses(user_id)
        has_license = any(l.get("skuPartNumber") in ("ENTERPRISEPACK", "SPE_E5", "SPE_E3") for l in licenses)
        status = "ASSIGNED" if has_license else "UNASSIGNED"
        license_name = "Microsoft 365 E5" if has_license else "None"
        try:
            GRAPH_LATENCY_SECONDS.labels(operation="check_office_license").observe(time.time() - start)
        except Exception:
            pass
        return {
            "license": license_name,
            "status": status
        }

    def check_exchange_license(self, user_id: str) -> dict:
        from app.core.metrics import GRAPH_REQUESTS_TOTAL, GRAPH_LATENCY_SECONDS, GRAPH_LICENSE_CHECKS_TOTAL
        start = time.time()
        try:
            GRAPH_REQUESTS_TOTAL.labels(operation="check_exchange_license").inc()
            GRAPH_LICENSE_CHECKS_TOTAL.inc()
        except Exception:
            pass
        logger.info("MicrosoftGraphMockClient: Checking Exchange license for %s", user_id)
        licenses = self.db.get_assigned_licenses(user_id)
        has_license = any(l.get("skuPartNumber") in ("ENTERPRISEPACK", "SPE_E5", "SPE_E3") for l in licenses)
        status = "ASSIGNED" if has_license else "UNASSIGNED"
        license_name = "Exchange Online Plan 2" if has_license else "None"
        try:
            GRAPH_LATENCY_SECONDS.labels(operation="check_exchange_license").observe(time.time() - start)
        except Exception:
            pass
        return {
            "license": license_name,
            "status": status
        }

    def get_group_membership(self, group_id: str) -> list:
        from app.core.metrics import GRAPH_REQUESTS_TOTAL, GRAPH_LATENCY_SECONDS
        start = time.time()
        try:
            GRAPH_REQUESTS_TOTAL.labels(operation="get_group_membership").inc()
        except Exception:
            pass
        logger.info("MicrosoftGraphMockClient: Fetching members of group %s", group_id)
        res = self.db.get_group_membership(group_id)
        try:
            GRAPH_LATENCY_SECONDS.labels(operation="get_group_membership").observe(time.time() - start)
        except Exception:
            pass
        return res

    def check_vpn_group(self, user_id: str) -> dict:
        from app.core.metrics import GRAPH_REQUESTS_TOTAL, GRAPH_LATENCY_SECONDS
        start = time.time()
        try:
            GRAPH_REQUESTS_TOTAL.labels(operation="check_vpn_group").inc()
        except Exception:
            pass
        logger.info("MicrosoftGraphMockClient: Checking VPN group membership for user %s", user_id)
        groups = self.db.get_user_groups(user_id)
        is_member = any(g.get("displayName") == "VPN Users" for g in groups)
        try:
            GRAPH_LATENCY_SECONDS.labels(operation="check_vpn_group").observe(time.time() - start)
        except Exception:
            pass
        return {
            "user_id": user_id,
            "group_name": "VPN Users",
            "is_member": is_member
        }

    def check_security_group(self, user_id: str, group_name: str) -> dict:
        from app.core.metrics import GRAPH_REQUESTS_TOTAL, GRAPH_LATENCY_SECONDS
        start = time.time()
        try:
            GRAPH_REQUESTS_TOTAL.labels(operation="check_security_group").inc()
        except Exception:
            pass
        logger.info("MicrosoftGraphMockClient: Checking security group '%s' for user %s", group_name, user_id)
        groups = self.db.get_user_groups(user_id)
        is_member = any(g.get("displayName") == group_name or g.get("id") == group_name for g in groups)
        try:
            GRAPH_LATENCY_SECONDS.labels(operation="check_security_group").observe(time.time() - start)
        except Exception:
            pass
        return {
            "user_id": user_id,
            "group_name": group_name,
            "is_member": is_member
        }

    def get_all_users(self) -> list:
        from app.core.metrics import GRAPH_REQUESTS_TOTAL, GRAPH_LATENCY_SECONDS
        start = time.time()
        try:
            GRAPH_REQUESTS_TOTAL.labels(operation="get_all_users").inc()
        except Exception:
            pass
        logger.info("MicrosoftGraphMockClient: Fetching all mock users")
        res = self.db.get_all_users()
        try:
            GRAPH_LATENCY_SECONDS.labels(operation="get_all_users").observe(time.time() - start)
        except Exception:
            pass
        return res

    def get_all_groups(self) -> list:
        from app.core.metrics import GRAPH_REQUESTS_TOTAL, GRAPH_LATENCY_SECONDS
        start = time.time()
        try:
            GRAPH_REQUESTS_TOTAL.labels(operation="get_all_groups").inc()
        except Exception:
            pass
        logger.info("MicrosoftGraphMockClient: Fetching all mock groups")
        res = self.db.get_all_groups()
        try:
            GRAPH_LATENCY_SECONDS.labels(operation="get_all_groups").observe(time.time() - start)
        except Exception:
            pass
        return res

    def check_connectivity(self) -> dict:
        logger.info("MicrosoftGraphMockClient: Connectivity check OK")
        return {
            "status": "healthy",
            "latency": 0.0,
            "details": "Mock Mode active.",
            "token_expiry": 9999999999
        }
