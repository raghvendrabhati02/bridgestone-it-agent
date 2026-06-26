from sqlalchemy import Column, Integer, String, Text, Boolean
from app.database.base import Base

class ServiceCatalogItem(Base):
    __tablename__ = "service_catalog"

    id = Column(Integer, primary_key=True, index=True)
    service_id = Column(String(50), unique=True, index=True, nullable=False)  # e.g., SRV001
    name = Column(String(100), nullable=False)
    category = Column(String(55), nullable=False)  # Hardware, Software, Network, Identity, Collaboration, Security, ERP, HR IT
    description = Column(Text, nullable=True)
    business_owner = Column(String(100), nullable=True)
    fulfillment_team = Column(String(100), nullable=True)
    approval_required = Column(Boolean, default=False)
    sla_hours = Column(Integer, default=24)
    estimated_completion = Column(String(50), nullable=True)
    icon = Column(String(50), nullable=True)
    status = Column(String(50), default="ACTIVE")
