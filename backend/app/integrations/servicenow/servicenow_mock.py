import logging

logger = logging.getLogger("it-agent-backend")

class ServiceNowMock:
    def __init__(self):
        self.incidents = {}
        self.requests = {}
        self.counter = 0
        self.req_counter = 0

    def create(self, category: str, description: str, assignment_group: str, **kwargs) -> dict:
        self.counter += 1
        sys_id = f"SNOW{self.counter:03d}"
        number = f"INC{self.counter:06d}"
        incident = {
            "sys_id": sys_id,
            "number": number,
            "state": "OPEN",
            "category": category,
            "description": description,
            "assignment_group": assignment_group
        }
        if kwargs:
            filtered_extra = {k: v for k, v in kwargs.items() if v is not None}
            incident.update(filtered_extra)
        self.incidents[sys_id] = incident
        logger.info("ServiceNow Mock: Created incident %s (%s)", sys_id, number)
        return incident

    def create_request(self, category: str, description: str, action_type: str) -> dict:
        self.req_counter += 1
        sys_id = f"SNOW_REQ{self.req_counter:03d}"
        number = f"SR{self.req_counter:06d}"
        req = {
            "sys_id": sys_id,
            "number": number,
            "state": "OPEN",
            "category": category,
            "description": description,
            "action_type": action_type
        }
        self.requests[sys_id] = req
        logger.info("ServiceNow Mock: Created catalog request %s (%s) for %s", sys_id, number, action_type)
        return req

    def get_request(self, sys_id: str) -> dict | None:
        return self.requests.get(sys_id)

    def get_all_requests(self) -> list[dict]:
        return list(self.requests.values())

    def get(self, sys_id_or_number: str) -> dict | None:
        if sys_id_or_number in self.incidents:
            return self.incidents[sys_id_or_number]
        for inc in self.incidents.values():
            if inc.get("number") == sys_id_or_number or inc.get("sys_id") == sys_id_or_number:
                return inc
        return None

    def get_by_number(self, number: str) -> dict | None:
        return self.get(number)

    def get_all(self) -> list[dict]:
        return list(self.incidents.values())

    def update(self, sys_id: str, updates: dict) -> dict | None:
        if sys_id in self.incidents:
            # Clean up None updates
            filtered_updates = {k: v for k, v in updates.items() if v is not None}
            self.incidents[sys_id].update(filtered_updates)
            logger.info("ServiceNow Mock: Updated incident %s with %s", sys_id, filtered_updates)
            return self.incidents[sys_id]
        return None

    def close(self, sys_id: str) -> dict | None:
        if sys_id in self.incidents:
            self.incidents[sys_id]["state"] = "CLOSED"
            logger.info("ServiceNow Mock: Closed incident %s", sys_id)
            return self.incidents[sys_id]
        return None

    def update_request(self, sys_id: str, updates: dict) -> dict | None:
        if sys_id in self.requests:
            filtered_updates = {k: v for k, v in updates.items() if v is not None}
            if "state" in filtered_updates:
                # Map standard request closing updates
                filtered_updates["state"] = filtered_updates["state"]
            self.requests[sys_id].update(filtered_updates)
            logger.info("ServiceNow Mock: Updated request %s with %s", sys_id, filtered_updates)
            return self.requests[sys_id]
        return None

# Singleton mock instance to persist data across calls
servicenow_mock_db = ServiceNowMock()
