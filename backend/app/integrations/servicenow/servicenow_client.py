from abc import ABC, abstractmethod
import logging
from .servicenow_mock import servicenow_mock_db

logger = logging.getLogger("it-agent-backend")

class ServiceNowClientInterface(ABC):
    @abstractmethod
    def create_incident(self, category: str, description: str, assignment_group: str) -> dict:
        """
        Creates an incident in ServiceNow.
        """
        pass

    @abstractmethod
    def update_incident(self, sys_id: str, updates: dict) -> dict:
        """
        Updates an incident in ServiceNow.
        """
        pass

    @abstractmethod
    def get_incident(self, sys_id: str) -> dict:
        """
        Retrieves a ServiceNow incident by sys_id.
        """
        pass

    @abstractmethod
    def close_incident(self, sys_id: str) -> dict:
        """
        Closes a ServiceNow incident.
        """
        pass

    @abstractmethod
    def create_request(self, category: str, description: str, action_type: str) -> dict:
        """
        Creates a catalog request in ServiceNow.
        """
        pass

    @abstractmethod
    def get_request(self, sys_id: str) -> dict:
        """
        Retrieves a catalog request by sys_id.
        """
        pass

    @abstractmethod
    def update_request(self, sys_id: str, updates: dict) -> dict:
        """
        Updates a catalog request in ServiceNow.
        """
        pass

    @abstractmethod
    def get_all_incidents(self) -> list:
        """
        Retrieves all incidents from ServiceNow.
        """
        pass

    @abstractmethod
    def get_all_requests(self) -> list:
        """
        Retrieves all catalog requests from ServiceNow.
        """
        pass


class ServiceNowMockClient(ServiceNowClientInterface):
    is_mock = True

    def __init__(self):
        self.db = servicenow_mock_db

    def create_incident(self, category: str, description: str, assignment_group: str) -> dict:
        from app.core.metrics import SERVICENOW_REQUESTS_TOTAL, SERVICENOW_LATENCY_SECONDS, INCIDENTS_CREATED_TOTAL
        import time
        start_time = time.time()
        try:
            SERVICENOW_REQUESTS_TOTAL.labels(operation="create_incident").inc()
        except Exception:
            pass
        logger.info("ServiceNowMockClient: Creating mock ServiceNow incident")
        res = self.db.create(category, description, assignment_group)
        try:
            SERVICENOW_LATENCY_SECONDS.labels(operation="create_incident").observe(time.time() - start_time)
            INCIDENTS_CREATED_TOTAL.inc()
        except Exception:
            pass
        return res

    def update_incident(self, sys_id: str, updates: dict) -> dict:
        from app.core.metrics import SERVICENOW_REQUESTS_TOTAL, SERVICENOW_LATENCY_SECONDS
        import time
        start_time = time.time()
        try:
            SERVICENOW_REQUESTS_TOTAL.labels(operation="update_incident").inc()
        except Exception:
            pass
        logger.info("ServiceNowMockClient: Updating mock ServiceNow incident %s", sys_id)
        result = self.db.update(sys_id, updates)
        if not result:
            from app.core.metrics import SERVICENOW_FAILURES_TOTAL
            try:
                SERVICENOW_FAILURES_TOTAL.labels(operation="update_incident", error_type="KeyError").inc()
            except Exception:
                pass
            raise KeyError(f"ServiceNow Incident {sys_id} not found.")
        try:
            SERVICENOW_LATENCY_SECONDS.labels(operation="update_incident").observe(time.time() - start_time)
        except Exception:
            pass
        return result

    def get_incident(self, sys_id: str) -> dict:
        from app.core.metrics import SERVICENOW_REQUESTS_TOTAL, SERVICENOW_LATENCY_SECONDS
        import time
        start_time = time.time()
        try:
            SERVICENOW_REQUESTS_TOTAL.labels(operation="get_incident").inc()
        except Exception:
            pass
        logger.info("ServiceNowMockClient: Fetching mock ServiceNow incident %s", sys_id)
        result = self.db.get(sys_id)
        if not result:
            from app.core.metrics import SERVICENOW_FAILURES_TOTAL
            try:
                SERVICENOW_FAILURES_TOTAL.labels(operation="get_incident", error_type="KeyError").inc()
            except Exception:
                pass
            raise KeyError(f"ServiceNow Incident {sys_id} not found.")
        try:
            SERVICENOW_LATENCY_SECONDS.labels(operation="get_incident").observe(time.time() - start_time)
        except Exception:
            pass
        return result

    def close_incident(self, sys_id: str) -> dict:
        from app.core.metrics import SERVICENOW_REQUESTS_TOTAL, SERVICENOW_LATENCY_SECONDS
        import time
        start_time = time.time()
        try:
            SERVICENOW_REQUESTS_TOTAL.labels(operation="close_incident").inc()
        except Exception:
            pass
        logger.info("ServiceNowMockClient: Closing mock ServiceNow incident %s", sys_id)
        result = self.db.close(sys_id)
        if not result:
            from app.core.metrics import SERVICENOW_FAILURES_TOTAL
            try:
                SERVICENOW_FAILURES_TOTAL.labels(operation="close_incident", error_type="KeyError").inc()
            except Exception:
                pass
            raise KeyError(f"ServiceNow Incident {sys_id} not found.")
        try:
            SERVICENOW_LATENCY_SECONDS.labels(operation="close_incident").observe(time.time() - start_time)
        except Exception:
            pass
        return result

    def create_request(self, category: str, description: str, action_type: str) -> dict:
        from app.core.metrics import SERVICENOW_REQUESTS_TOTAL, SERVICENOW_LATENCY_SECONDS, SERVICE_REQUESTS_CREATED_TOTAL
        import time
        start_time = time.time()
        try:
            SERVICENOW_REQUESTS_TOTAL.labels(operation="create_request").inc()
        except Exception:
            pass
        logger.info("ServiceNowMockClient: Creating mock ServiceNow catalog request")
        res = self.db.create_request(category, description, action_type)
        try:
            SERVICENOW_LATENCY_SECONDS.labels(operation="create_request").observe(time.time() - start_time)
            SERVICE_REQUESTS_CREATED_TOTAL.inc()
        except Exception:
            pass
        return res

    def get_request(self, sys_id: str) -> dict:
        from app.core.metrics import SERVICENOW_REQUESTS_TOTAL, SERVICENOW_LATENCY_SECONDS
        import time
        start_time = time.time()
        try:
            SERVICENOW_REQUESTS_TOTAL.labels(operation="get_request").inc()
        except Exception:
            pass
        logger.info("ServiceNowMockClient: Fetching mock ServiceNow catalog request %s", sys_id)
        result = self.db.get_request(sys_id)
        if not result:
            from app.core.metrics import SERVICENOW_FAILURES_TOTAL
            try:
                SERVICENOW_FAILURES_TOTAL.labels(operation="get_request", error_type="KeyError").inc()
            except Exception:
                pass
            raise KeyError(f"ServiceNow Catalog Request {sys_id} not found.")
        try:
            SERVICENOW_LATENCY_SECONDS.labels(operation="get_request").observe(time.time() - start_time)
        except Exception:
            pass
        return result

    def update_request(self, sys_id: str, updates: dict) -> dict:
        from app.core.metrics import SERVICENOW_REQUESTS_TOTAL, SERVICENOW_LATENCY_SECONDS
        import time
        start_time = time.time()
        try:
            SERVICENOW_REQUESTS_TOTAL.labels(operation="update_request").inc()
        except Exception:
            pass
        logger.info("ServiceNowMockClient: Updating mock ServiceNow catalog request %s", sys_id)
        result = self.db.update_request(sys_id, updates)
        if not result:
            from app.core.metrics import SERVICENOW_FAILURES_TOTAL
            try:
                SERVICENOW_FAILURES_TOTAL.labels(operation="update_request", error_type="KeyError").inc()
            except Exception:
                pass
            raise KeyError(f"ServiceNow Catalog Request {sys_id} not found.")
        try:
            SERVICENOW_LATENCY_SECONDS.labels(operation="update_request").observe(time.time() - start_time)
        except Exception:
            pass
        return result

    def get_all_incidents(self) -> list:
        from app.core.metrics import SERVICENOW_REQUESTS_TOTAL, SERVICENOW_LATENCY_SECONDS
        import time
        start_time = time.time()
        try:
            SERVICENOW_REQUESTS_TOTAL.labels(operation="get_all_incidents").inc()
        except Exception:
            pass
        logger.info("ServiceNowMockClient: Fetching all mock ServiceNow incidents")
        res = self.db.get_all()
        try:
            SERVICENOW_LATENCY_SECONDS.labels(operation="get_all_incidents").observe(time.time() - start_time)
        except Exception:
            pass
        return res

    def get_all_requests(self) -> list:
        from app.core.metrics import SERVICENOW_REQUESTS_TOTAL, SERVICENOW_LATENCY_SECONDS
        import time
        start_time = time.time()
        try:
            SERVICENOW_REQUESTS_TOTAL.labels(operation="get_all_requests").inc()
        except Exception:
            pass
        logger.info("ServiceNowMockClient: Fetching all mock ServiceNow catalog requests")
        res = self.db.get_all_requests()
        try:
            SERVICENOW_LATENCY_SECONDS.labels(operation="get_all_requests").observe(time.time() - start_time)
        except Exception:
            pass
        return res


class ServiceNowRealClient(ServiceNowClientInterface):
    """
    Production implementation calling the actual ServiceNow JSON REST APIs / Table API.
    To be configured with base URL, username, and password/tokens.
    """
    def __init__(self, base_url: str = None, username: str = None, password: str = None):
        self.base_url = base_url
        self.username = username
        self.password = password

    def create_incident(self, category: str, description: str, assignment_group: str) -> dict:
        raise NotImplementedError("Real client integration is not configured.")

    def update_incident(self, sys_id: str, updates: dict) -> dict:
        raise NotImplementedError("Real client integration is not configured.")

    def get_incident(self, sys_id: str) -> dict:
        raise NotImplementedError("Real client integration is not configured.")

    def close_incident(self, sys_id: str) -> dict:
        raise NotImplementedError("Real client integration is not configured.")

    def create_request(self, category: str, description: str, action_type: str) -> dict:
        raise NotImplementedError("Real client integration is not configured.")

    def get_request(self, sys_id: str) -> dict:
        raise NotImplementedError("Real client integration is not configured.")

    def update_request(self, sys_id: str, updates: dict) -> dict:
        raise NotImplementedError("Real client integration is not configured.")

    def get_all_incidents(self) -> list:
        raise NotImplementedError("Real client integration is not configured.")

    def get_all_requests(self) -> list:
        raise NotImplementedError("Real client integration is not configured.")
