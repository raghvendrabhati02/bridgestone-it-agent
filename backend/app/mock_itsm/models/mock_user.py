from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Boolean
from app.database.base import Base

class MockUser(Base):
    __tablename__ = "mock_users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(100), unique=True, index=True, nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=False)
    role = Column(String(50), default="EMPLOYEE", nullable=False)  # EMPLOYEE, MANAGER, ENGINEER, ADMIN
    manager_username = Column(String(100), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
