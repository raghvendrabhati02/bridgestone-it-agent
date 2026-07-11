import time
import logging
from sqlalchemy.orm import Session
from app.services.device_agent_client import DeviceAgentClient

logger = logging.getLogger("it-agent-backend")

class DeviceAgentService:
    _cached_status = None
    _cached_time = 0
    CACHE_DURATION = 10.0  # Cache status for 10 seconds

    def __init__(self):
        self.client = DeviceAgentClient()

    def get_status(self) -> dict:
        """
        Calls Health API and caches the status.
        """
        now = time.time()
        if DeviceAgentService._cached_status is not None and (now - DeviceAgentService._cached_time < DeviceAgentService.CACHE_DURATION):
            logger.info("[DeviceAgentService] Returning cached agent status")
            return DeviceAgentService._cached_status
        
        health_data = self.client.health()
        DeviceAgentService._cached_status = health_data
        DeviceAgentService._cached_time = now
        return health_data

    def get_system_info(self) -> dict:
        """
        Retrieves system information from the connected agent.
        """
        return self.client.system_info()

    def get_history(self) -> dict:
        """
        Retrieves action execution history from the agent.
        """
        return self.client.history()

    def execute_action(self, action: str, parameters: dict = None) -> dict:
        """
        Sends execute action requests to the agent.
        """
        return self.client.execute(action, parameters)

    def register_agent(self, db: Session, device_id: str, hostname: str, username: str, os_name: str, ip: str, agent_version: str) -> dict:
        """
        Registers a connected agent in the local database registry.
        """
        from app.database.models.device import Device
        from datetime import datetime
        try:
            device = db.query(Device).filter(Device.id == device_id).first()
            if not device:
                device = Device(id=device_id)
                db.add(device)
            device.hostname = hostname
            device.username = username
            device.operating_system = os_name
            device.ip_address = ip
            device.agent_version = agent_version
            device.status = "Online"
            device.last_heartbeat = datetime.utcnow()
            device.last_seen = datetime.utcnow()
            db.commit()
            logger.info("[DeviceAgentService] Successfully registered agent device: %s", device_id)
            return {"success": True, "message": f"Agent registered successfully for {device_id}"}
        except Exception as e:
            logger.error("[DeviceAgentService] Failed to register agent in DB: %s", e)
            return {"success": False, "message": str(e)}
