from sqlalchemy import Column, String, Float, DateTime, JSON
from datetime import datetime
from app.database.base import Base

class Device(Base):
    __tablename__ = "devices"

    id = Column(String(100), primary_key=True, index=True)
    hostname = Column(String(100), index=True, nullable=False)
    serial_number = Column(String(100), nullable=True)
    manufacturer = Column(String(100), nullable=True)
    model = Column(String(100), nullable=True)
    operating_system = Column(String(200), nullable=True)
    ram = Column(Float, nullable=True)  # RAM Total in GB
    cpu = Column(Float, nullable=True)  # CPU usage or count
    disk = Column(Float, nullable=True)  # Disk space Total or usage
    ip_address = Column(String(50), nullable=True)
    mac_address = Column(String(100), nullable=True)
    agent_version = Column(String(50), nullable=True)
    status = Column(String(50), default="Offline", nullable=False)  # Online, Offline, Updating, Error, Inactive
    last_heartbeat = Column(DateTime, default=datetime.utcnow, nullable=True)
    last_seen = Column(DateTime, default=datetime.utcnow, nullable=True)
    username = Column(String(100), nullable=True)
    department = Column(String(100), nullable=True)
    
    # Store dynamic software lists, active process lists and interface information
    installed_software = Column(JSON, nullable=True)
    running_processes = Column(JSON, nullable=True)
    network_interfaces = Column(JSON, nullable=True)
