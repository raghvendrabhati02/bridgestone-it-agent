import os
import logging
from app.adapters.base_adapter import BaseAdapter

logger = logging.getLogger("it-agent-backend")

from app.core.retry_helper import with_retry

class ServiceNowAdapter(BaseAdapter):
    def __init__(self):
        use_mock = os.getenv("USE_MOCK_SERVICENOW", "true").lower() == "true"
        if use_mock:
            from app.integrations.servicenow.servicenow_client import ServiceNowMockClient
            self.client = ServiceNowMockClient()
            logger.info("ServiceNowAdapter: Initialized in MOCK Mode.")
        else:
            from app.integrations.servicenow.client import ServiceNowRealClient
            self.client = ServiceNowRealClient(
                instance_url=os.getenv("SERVICENOW_INSTANCE_URL") or os.getenv("SERVICENOW_URL"),
                username=os.getenv("SERVICENOW_USERNAME"),
                password=os.getenv("SERVICENOW_PASSWORD"),
                client_id=os.getenv("SERVICENOW_CLIENT_ID"),
                client_secret=os.getenv("SERVICENOW_CLIENT_SECRET")
            )
            logger.info("ServiceNowAdapter: Initialized in REAL Production Mode.")
        self.connected_state = False

    def connect(self) -> bool:
        logger.info("ServiceNowAdapter: Connected successfully")
        self.connected_state = True
        return True

    def health_check(self) -> bool:
        if not getattr(self.client, "is_mock", True):
            res = self.client.check_connectivity()
            is_healthy = res.get("status") == "healthy"
            logger.info("ServiceNowAdapter: Real health check returned status=%s", res.get("status"))
            return is_healthy
        logger.info("ServiceNowAdapter: Mock health check OK")
        return True

    @with_retry(retries=3, backoff_factor=2.0)
    def execute(self, action: str, **kwargs) -> any:
        logger.info("ServiceNowAdapter: Executing action '%s'", action)
        if action == "create_incident":
            return self.create_incident(
                category=kwargs.get("category"),
                description=kwargs.get("description"),
                assignment_group=kwargs.get("assignment_group")
            )
        elif action == "create_service_request":
            return self.create_service_request(
                category=kwargs.get("category"),
                description=kwargs.get("description"),
                action_type=kwargs.get("action_type")
            )
        elif action == "get_incident":
            return self.get_incident(sys_id=kwargs.get("sys_id"))
        elif action == "update_incident":
            return self.update_incident(
                sys_id=kwargs.get("sys_id"),
                updates=kwargs.get("updates")
            )
        elif action == "close_incident":
            return self.close_incident(sys_id=kwargs.get("sys_id"))
        elif action == "get_request":
            return self.get_request(sys_id=kwargs.get("sys_id"))
        elif action == "update_request":
            return self.update_request(
                sys_id=kwargs.get("sys_id"),
                updates=kwargs.get("updates")
            )
        elif action == "get_all_incidents":
            return self.get_all_incidents()
        elif action == "get_all_requests":
            return self.get_all_requests()
        raise NotImplementedError(f"Action '{action}' not supported by ServiceNowAdapter")

    def disconnect(self) -> bool:
        logger.info("ServiceNowAdapter: Disconnected successfully")
        self.connected_state = False
        return True

    def create_incident(self, category: str, description: str, assignment_group: str) -> dict:
        return self.client.create_incident(category, description, assignment_group)

    def create_service_request(self, category: str, description: str, action_type: str) -> dict:
        return self.client.create_request(category, description, action_type)

    def get_incident(self, sys_id: str) -> dict:
        return self.client.get_incident(sys_id)

    def update_incident(self, sys_id: str, updates: dict) -> dict:
        return self.client.update_incident(sys_id, updates)

    def close_incident(self, sys_id: str) -> dict:
        return self.client.close_incident(sys_id)

    def get_request(self, sys_id: str) -> dict:
        return self.client.get_request(sys_id)

    def update_request(self, sys_id: str, updates: dict) -> dict:
        return self.client.update_request(sys_id, updates)

    def get_all_incidents(self) -> list:
        return self.client.get_all_incidents()

    def get_all_requests(self) -> list:
        return self.client.get_all_requests()
